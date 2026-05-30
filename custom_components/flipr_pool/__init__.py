import logging
from datetime import timedelta, datetime, timezone
import async_timeout
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN, 
    AUTH_URL, 
    PH_TARGET, 
    PH_MINUS_DOSE, 
    PH_PLUS_DOSE, 
    CHLORINE_TARGET, 
    CHLORINE_SHOCK_TARGET,
    CHLORINE_DOSE, 
    PUMP_MIN_HOURS, 
    PUMP_MAX_HOURS,
    PLACES_URL,
    ALERTS_URL,
    THRESHOLDS_URL
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "select", "switch", "number"]


def _compute_pool_data(m, s, entry):
    """Calcule toutes les valeurs dérivées à partir des mesures et des options V1."""

    # ── Mesures brutes ───────────────────────────────────────
    ph_raw      = m.get("PH")
    redox_raw   = m.get("OxydoReductionPotentiel")
    battery_raw = m.get("Battery")
    cond_raw    = m.get("Conductivity")
    desinf_raw  = m.get("Desinfectant")

    ph_val      = ph_raw.get("Value")            if isinstance(ph_raw, dict)      else ph_raw
    redox_val   = redox_raw.get("Value")         if isinstance(redox_raw, dict)   else redox_raw
    battery_val = round(battery_raw.get("Deviation", 0) * 100, 1) if isinstance(battery_raw, dict) else battery_raw
    cond_val    = cond_raw.get("Value")          if isinstance(cond_raw, dict)    else cond_raw

    # ── Statuts pH & Chlore ─────────────────────────────────
    ph_sector   = ph_raw.get("DeviationSector")  if isinstance(ph_raw, dict) else None
    ph_status   = "OK" if ph_sector == "OK" else (ph_raw.get("Message", "Inconnu") if isinstance(ph_raw, dict) else None)

    cl_val      = round(desinf_raw.get("Value"), 3) if isinstance(desinf_raw, dict) and desinf_raw.get("Value") is not None else None
    cl_sector   = desinf_raw.get("DeviationSector") if isinstance(desinf_raw, dict) else None
    cl_status   = "OK" if cl_sector == "OK" else (desinf_raw.get("Message", "Inconnu") if isinstance(desinf_raw, dict) else None)

    # ── Horodatage ──────────────────────────────────────────
    dt_raw = m.get("DateTime")
    try:
        last_update = datetime.fromisoformat(dt_raw.replace("Z", "+00:00")) if dt_raw else None
    except (ValueError, AttributeError):
        last_update = None

    # ── Dimensions piscine (data = config flow, options = options flow) ──
    opts          = {**entry.data, **entry.options}
    pool_length   = float(opts.get("pool_length", 0))
    pool_width    = float(opts.get("pool_width", 0))
    pool_depth    = float(opts.get("pool_depth", 0))
    pool_volume_m3 = pool_length * pool_width * pool_depth
    pool_volume_l  = round(pool_volume_m3 * 1000) if pool_volume_m3 > 0 else None

    # ── Doses de correction pH ──────────────────────────────
    if ph_val is not None and pool_volume_m3 > 0:
        ph_diff = ph_val - PH_TARGET
        if ph_diff > 0:
            dose_ph_minus = round(ph_diff * pool_volume_m3 * PH_MINUS_DOSE)
            dose_ph_plus  = 0
        elif ph_diff < 0:
            dose_ph_minus = 0
            dose_ph_plus  = round(abs(ph_diff) * pool_volume_m3 * PH_PLUS_DOSE)
        else:
            dose_ph_minus = dose_ph_plus = 0
    else:
        dose_ph_minus = dose_ph_plus = None

    # ── Doses de correction chlore ───────────────────────────
    if cl_val is not None and pool_volume_m3 > 0:
        cl_diff_maint = CHLORINE_TARGET - cl_val
        cl_diff_shock = CHLORINE_SHOCK_TARGET - cl_val
        
        dose_cl_maint = round(cl_diff_maint * pool_volume_m3 * CHLORINE_DOSE) if cl_diff_maint > 0 else 0
        dose_cl_shock = round(cl_diff_shock * pool_volume_m3 * CHLORINE_DOSE) if cl_diff_shock > 0 else 0
    else:
        dose_cl_maint = dose_cl_shock = None

    # ── Température Air (fix) ───────────────────────────────
    air_temp = s.get("AirTemperature")
    if air_temp is None:
        air_temp = m.get("AirTemperature")

    # ── Durée de pompage & Conseil ──────────────────────────
    water_temp = m.get("Temperature")
    conseil_filtration = None
    
    if water_temp is not None:
        if cl_val is not None and cl_val < 0.5:
            # Recommandation choc
            pump_hours = 24.0
            conseil_filtration = "24h (Choc recommandé)"
        else:
            base_h = water_temp / 2
            malus  = 0
            if ph_val is not None:
                if ph_val < 7.0 or ph_val > 8.0:
                    malus += 2
                elif ph_val < 7.2 or ph_val > 7.6:
                    malus += 1
            if cl_val is not None:
                if cl_val < 1.0:
                    malus += 1
            
            pump_hours = round(max(PUMP_MIN_HOURS, min(PUMP_MAX_HOURS, base_h + malus)), 1)
            conseil_filtration = f"{pump_hours}h"
    else:
        pump_hours = None

    # ── Données brutes (pour number.py etc) ─────────────────
    thresholds = m.get("thresholds_raw")
    alerts = m.get("alerts_raw")

    return {
        "temperature":    water_temp,
        "ph":             ph_val,
        "ph_status":      ph_status,
        "redox":          redox_val,
        "battery":        battery_val,
        "conductivity":   cond_val,
        "uv_index":       m.get("UvIndex"),
        "air_temp":       air_temp,
        "water_state":    s.get("WaterState"),
        "chlorine":       cl_val,
        "chlorine_status": cl_status,
        "last_update":    last_update,
        "pool_volume":    pool_volume_l,
        "dose_ph_minus":  dose_ph_minus,
        "dose_ph_plus":   dose_ph_plus,
        "dose_cl_maint":  dose_cl_maint,
        "dose_cl_shock":  dose_cl_shock,
        "pump_hours":     pump_hours,
        "conseil_filtration": conseil_filtration,
        "thresholds":     thresholds,
        "last_alert":     alerts[0].get("Title") if alerts and isinstance(alerts, list) else None,
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    email    = entry.data.get("email")
    password = entry.data.get("password")
    flipr_id = entry.data.get("flipr_id")
    session  = async_get_clientsession(hass)

    async def _async_update_data():
        try:
            async with async_timeout.timeout(60):
                # 1. Authentification
                auth_data = {
                    "grant_type": "password", 
                    "username": str(email or "").strip(), 
                    "password": str(password or "").strip()
                }
                async with session.post(AUTH_URL, data=auth_data) as resp:
                    if resp.status != 200:
                        resp_text = await resp.text()
                        raise UpdateFailed(f"Erreur d'authentification Flipr ({resp.status}): {resp_text}")
                    token = (await resp.json()).get("access_token")
                    coordinator.token = token 

                headers = {"Authorization": f"Bearer {token}"}

                # 2. Mesures réelles
                measure_url = f"https://apis.goflipr.com/modules/{flipr_id}/survey/last"
                async with session.get(measure_url, headers=headers) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"Erreur API lastmeasure ({resp.status})")
                    m = await resp.json()

                # 3. Prévisions (ShortTerm)
                short_url = f"https://apis.goflipr.com/modules/{flipr_id}/shortterm"
                async with session.get(short_url, headers=headers) as resp:
                    s = await resp.json() if resp.status == 200 else {}

                # 4. État du Hub (Filtration)
                hub_url = f"https://apis.goflipr.com/hub/{flipr_id}"
                async with session.get(hub_url, headers=headers) as resp:
                    h = await resp.json() if resp.status == 200 else {}

                # 5. Découverte du place_id si manquant
                if not coordinator.place_id:
                    async with session.get(PLACES_URL, headers=headers) as resp_p:
                        if resp_p.status == 200:
                            places = await resp_p.json()
                            if places:
                                coordinator.place_id = places[0].get("Id")

                # 6. Alertes (nécessite place_id)
                alerts = []
                if coordinator.place_id:
                    alert_url = ALERTS_URL.format(api_base="https://apis.goflipr.com", place_id=coordinator.place_id)
                    async with session.get(alert_url, headers=headers) as resp:
                        if resp.status == 200:
                            alerts = await resp.json()

                # 7. Seuils (Thresholds)
                thresholds = {}
                threshold_url = THRESHOLDS_URL.format(api_base="https://apis.goflipr.com", flipr_id=flipr_id)
                async with session.get(threshold_url, headers=headers) as resp:
                    if resp.status == 200:
                        thresholds = await resp.json()

                m["alerts_raw"] = alerts
                m["thresholds_raw"] = thresholds

                data = _compute_pool_data(m, s, entry)
                data["hub_mode"] = h.get("Mode")
                data["hub_state"] = h.get("Status") # "on" or "off"
                return data

        except Exception as err:
            raise UpdateFailed(f"Erreur Flipr: {err}")

    coordinator = DataUpdateCoordinator(
        hass, _LOGGER, name="flipr_pool",
        update_method=_async_update_data,
        update_interval=timedelta(minutes=15),
    )
    
    # On attache l'ID au coordinateur pour que select.py puisse l'utiliser
    coordinator.flipr_id = flipr_id
    coordinator.place_id = None
    coordinator.token = None # Sera mis à jour lors du premier refresh

    # On démarre les plateformes avant le refresh pour que les entités existent
    hass.data.setdefault("flipr_pool", {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Premier refresh : on l'enveloppe pour ne pas bloquer HA si l'API est indisponible au démarrage
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Flipr: premier refresh échoué (%s) — les capteurs seront disponibles à la prochaine tentative.", err)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data["flipr_pool"].pop(entry.entry_id)
    return unload_ok