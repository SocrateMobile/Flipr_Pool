"""Flipr Pool Control — Double Coordinateur Cloud + BLE avec fusion automatique.

Architecture :
- cloud_coordinator  : API REST GoFlipr, toutes les 15 minutes
- ble_coordinator    : Bluetooth BLE local, toutes les 60 minutes (si activé)
- merged_coordinator : fusionne les deux, garde le plus récent, alimente les entités
"""

import logging
from datetime import timedelta, datetime, timezone
import async_timeout
import aiohttp
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers import device_registry as dr
from homeassistant.core import ServiceCall

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
    THRESHOLDS_URL,
    CONF_TAC, CONF_TH, CONF_CYA, CONF_TDS,
    DEFAULT_TAC, DEFAULT_TH, DEFAULT_CYA, DEFAULT_TDS,
    CONF_BLE_ENABLED,
    CONF_BLE_ADDRESS,
    CLOUD_UPDATE_INTERVAL_MIN,
    BLE_UPDATE_INTERVAL_DEFAULT,
    VERSION,
)
from .chemistry import (
    compute_isl,
    compute_ph_equilibrium,
    estimate_free_chlorine,
    compute_active_chlorine_from_fc,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "select", "switch", "number", "button", "binary_sensor"]
STORE_VERSION = 1


# ═══════════════════════════════════════════════════════════════
#  Utilitaires
# ═══════════════════════════════════════════════════════════════

def _store_key(entry_id: str) -> str:
    return f"{DOMAIN}_{entry_id}"


def _get_water_params(entry: ConfigEntry) -> tuple[float, float, float, float]:
    """Récupère TAC, TH, CYA, TDS depuis les options ou les données."""
    opts = {**entry.data, **entry.options}
    tac = float(opts.get(CONF_TAC, DEFAULT_TAC))
    th  = float(opts.get(CONF_TH,  DEFAULT_TH))
    cya = float(opts.get(CONF_CYA, DEFAULT_CYA))
    tds = float(opts.get(CONF_TDS, DEFAULT_TDS))
    return tac, th, cya, tds


def _safe_timestamp(dt_val: Any) -> datetime | None:
    """Convertit un objet en datetime UTC comparable, ou None."""
    if dt_val is None:
        return None
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val
    if isinstance(dt_val, str):
        try:
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
    return None


# ═══════════════════════════════════════════════════════════════
#  Calculs de données piscine (communs Cloud & BLE)
# ═══════════════════════════════════════════════════════════════

def _compute_pool_data(m: dict[str, Any], s: Any, entry: ConfigEntry, data_source: str = "cloud") -> dict[str, Any]:
    """Calcule toutes les valeurs dérivées à partir des mesures brutes.

    Fonctionne avec les données Cloud (API JSON) ou BLE (dict décodé).
    Le paramètre `data_source` est injecté dans le résultat.
    """

    # ── Déballage de "Current" si présent (API NewResume / JSON imbriqué) ──
    if isinstance(m, dict) and "Current" in m and isinstance(m["Current"], dict):
        current_dict = m["Current"]
        m = {**m, **current_dict}

    # ── Mesures brutes ───────────────────────────────────────
    ph_raw      = m.get("PH") or m.get("ph")
    redox_raw   = m.get("OxydoReductionPotentiel") or m.get("oxydoReductionPotentiel") or m.get("redox")
    cond_raw    = m.get("Conductivity") or m.get("conductivity")
    desinf_raw  = m.get("Desinfectant") or m.get("desinfectant") or m.get("chlorine")

    ph_val = ph_raw.get("Value") if isinstance(ph_raw, dict) else ph_raw
    if ph_val is not None:
        try:
            ph_val = float(ph_val)
        except (ValueError, TypeError):
            ph_val = None

    redox_val = redox_raw.get("Value") if isinstance(redox_raw, dict) else redox_raw
    if redox_val is not None:
        try:
            redox_val = float(redox_val)
        except (ValueError, TypeError):
            redox_val = None

    # Batterie : BatteryLevel (float %, NewResume) ou Battery.Deviation (fraction 0-1, survey/last)
    battery_level_direct = m.get("BatteryLevel") or m.get("batteryLevel")
    battery_raw = m.get("Battery") or m.get("battery")

    if battery_level_direct is not None:
        # NewResume retourne BatteryLevel directement en pourcentage
        try:
            battery_val = float(battery_level_direct)
        except (ValueError, TypeError):
            battery_val = None
    elif isinstance(battery_raw, dict):
        # survey/last retourne Battery: { Deviation: 0.85 } → 85%
        try:
            battery_val = round(float(battery_raw.get("Deviation", 0)) * 100, 1)
        except (ValueError, TypeError):
            battery_val = None
    elif battery_raw is not None:
        # BLE retourne un float direct
        try:
            battery_val = float(battery_raw)
        except (ValueError, TypeError):
            battery_val = None
    else:
        battery_val = None

    cond_val = cond_raw.get("Value") if isinstance(cond_raw, dict) else cond_raw
    if cond_val is not None:
        try:
            cond_val = float(cond_val)
        except (ValueError, TypeError):
            cond_val = None

    # ── Helper for Status ───────────────────────────────────
    def _is_ok(status_val):
        if not isinstance(status_val, str):
            return False
        return status_val.lower() in [
            "ok", "perfect", "good", "excellent", "none", "parfait", "bon",
            "medium", "mediumlow", "mediumhigh", "optimal", "correct"
        ]

    def _compute_status(sector, msg, val):
        if _is_ok(sector) or _is_ok(msg):
            return "OK"
        if msg:
            return msg
        if sector:
            return sector
        if val is not None:
            return "OK"
        return "Inconnu"

    # ── Statuts pH & Chlore ─────────────────────────────────
    ph_sector = ph_raw.get("DeviationSector") if isinstance(ph_raw, dict) else None
    ph_msg    = ph_raw.get("Message") if isinstance(ph_raw, dict) else None
    ph_status = _compute_status(ph_sector, ph_msg, ph_val)

    cl_val = round(desinf_raw.get("Value"), 3) if isinstance(desinf_raw, dict) and desinf_raw.get("Value") is not None else (desinf_raw if not isinstance(desinf_raw, dict) else None)
    if cl_val is not None:
        try:
            cl_val = float(cl_val)
        except (ValueError, TypeError):
            cl_val = None

    cl_sector = desinf_raw.get("DeviationSector") if isinstance(desinf_raw, dict) else None
    cl_msg    = desinf_raw.get("Message") if isinstance(desinf_raw, dict) else None
    cl_status = _compute_status(cl_sector, cl_msg, cl_val)

    # ── Horodatage ──────────────────────────────────────────
    dt_raw = m.get("DateTime")
    try:
        last_update = datetime.fromisoformat(dt_raw.replace("Z", "+00:00")) if dt_raw else None
    except (ValueError, AttributeError):
        last_update = None

    # ── Dimensions piscine ──────────────────────────────────
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

    # ── Météo (Weather) ─────────────────────────────────────
    weather = m.get("Weather") or m.get("weather") or {}
    if not isinstance(weather, dict):
        weather = {}

    def _first_not_none(*args):
        for arg in args:
            if arg is not None:
                return arg
        return None

    # ── Température Air ─────────────────────────────────────
    air_temp = None
    water_state = None
    if isinstance(s, dict):
        air_temp = _first_not_none(s.get("AirTemperature"), s.get("airTemperature"), s.get("AirTemp"), s.get("airTemp"))
        water_state = _first_not_none(s.get("WaterState"), s.get("waterState"))
    elif isinstance(s, list) and len(s) > 0:
        first_s = s[0]
        if isinstance(first_s, dict):
            air_temp = _first_not_none(first_s.get("AirTemperature"), first_s.get("airTemperature"), first_s.get("AirTemp"), first_s.get("airTemp"))
            water_state = _first_not_none(first_s.get("WaterState"), first_s.get("waterState"))

    if air_temp is None:
        air_temp = _first_not_none(
            weather.get("CurrentTemperature"), weather.get("currentTemperature"),
            weather.get("AirTemperature"), weather.get("airTemperature"),
            weather.get("AirTemp"), weather.get("airTemp"),
            weather.get("Temperature"), weather.get("temperature")
        )

    if air_temp is None:
        air_temp = _first_not_none(
            m.get("AirTemperature"), m.get("airTemperature"),
            m.get("AirTemp"), m.get("airTemp")
        )

    if air_temp is not None:
        try:
            air_temp = float(air_temp)
        except (ValueError, TypeError):
            air_temp = None

    # ── Indice UV ───────────────────────────────────────────
    uv_index = _first_not_none(
        weather.get("UvIndex"), weather.get("uvIndex"), weather.get("UV"), weather.get("uv"),
        m.get("UvIndex"), m.get("uvIndex"), m.get("UV"), m.get("uv")
    )
    if uv_index is not None:
        try:
            uv_index = float(uv_index)
        except (ValueError, TypeError):
            uv_index = None

    # ── Durée de pompage & Conseil ──────────────────────────
    water_temp_raw = m.get("Temperature") or m.get("temperature")
    water_temp = water_temp_raw.get("Value") if isinstance(water_temp_raw, dict) else water_temp_raw
    if water_temp is not None:
        try:
            water_temp = float(water_temp)
        except (ValueError, TypeError):
            water_temp = None
    conseil_filtration = None

    if water_temp is not None:
        if cl_val is not None and cl_val < 0.5:
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

    # ── Chimie avancée (LSI, pH équilibre, Chlore Actif) ────
    tac, th, cya, tds = _get_water_params(entry)

    lsi = compute_isl(water_temp, ph_val, tac, th, tds)
    if lsi is None:
        lsi_status = None
    elif lsi < -0.3:
        lsi_status = "corrosive"
    elif lsi > 0.3:
        lsi_status = "entartrante"
    else:
        lsi_status = "équilibrée"

    ph_equilibre = compute_ph_equilibrium(water_temp, tac, th, tds)

    free_cl = estimate_free_chlorine(redox_val, ph_val, cya) if (redox_val is not None and ph_val is not None) else None
    active_cl = compute_active_chlorine_from_fc(free_cl, ph_val, water_temp if water_temp is not None else 25.0, cya) if free_cl is not None else None

    # ── Données brutes (pour number.py etc) ─────────────────
    thresholds = m.get("thresholds_raw")
    alerts = m.get("alerts_raw")

    # ── Extraction Alerte ──────────────────────────────────
    last_alert = None
    if alerts and isinstance(alerts, list) and len(alerts) > 0:
        first_alert = alerts[0]
        if isinstance(first_alert, dict):
            last_alert = (
                first_alert.get("Title")
                or first_alert.get("title")
                or first_alert.get("Description")
                or first_alert.get("description")
                or first_alert.get("Message")
                or first_alert.get("message")
            )

    return {
        "temperature":         water_temp,
        "ph":                  ph_val,
        "ph_status":           ph_status,
        "ph_simple":           "OK" if ph_status == "OK" else "KO",
        "redox":               redox_val,
        "battery":             battery_val,
        "conductivity":        cond_val,
        "uv_index":            uv_index,
        "air_temp":            air_temp,
        "water_state":         water_state,
        "chlorine":            cl_val,
        "chlorine_status":     cl_status,
        "chlorine_simple":     "OK" if cl_status == "OK" else "KO",
        "last_update":         last_update,
        "pool_volume":         pool_volume_l,
        "dose_ph_minus":       dose_ph_minus,
        "dose_ph_plus":        dose_ph_plus,
        "dose_cl_maint":       dose_cl_maint,
        "dose_cl_shock":       dose_cl_shock,
        "pump_hours":          pump_hours,
        "conseil_filtration":  conseil_filtration,
        "thresholds":          thresholds,
        "last_alert":          last_alert,
        # ── Chimie avancée ─────────────────────────────────
        "lsi":                 lsi,
        "lsi_status":          lsi_status,
        "ph_equilibre":        ph_equilibre,
        "free_chlorine":       free_cl,
        "active_chlorine":     active_cl,
        # ── Métadonnées source ─────────────────────────────
        "data_source":         data_source,
        "version":             VERSION,
    }


def _compute_ble_pool_data(ble_raw: dict[str, Any], entry: ConfigEntry) -> dict[str, Any]:
    """Convertit les données brutes BLE dans le format attendu par _compute_pool_data.

    Le BLE retourne des valeurs simples (pas de dicts imbriqués comme l'API Cloud).
    On construit un faux `m` et `s` compatibles.
    """
    m = {
        "PH": ble_raw.get("ph"),
        "OxydoReductionPotentiel": ble_raw.get("redox"),
        "Battery": ble_raw.get("battery"),
        "Conductivity": ble_raw.get("conductivity"),
        "Desinfectant": {"Value": ble_raw.get("chlorine")} if ble_raw.get("chlorine") is not None else None,
        "Temperature": ble_raw.get("temperature"),
        "UvIndex": None,
        "DateTime": ble_raw.get("last_update_ble").isoformat() if ble_raw.get("last_update_ble") else None,
        # Pas de thresholds/alerts en BLE
        "thresholds_raw": None,
        "alerts_raw": None,
    }
    s = {}  # Pas de ShortTerm en BLE

    data = _compute_pool_data(m, s, entry, data_source="bluetooth")

    # Ajouter les métadonnées BLE spécifiques
    data["ble_rssi"] = ble_raw.get("ble_rssi")
    data["ble_status"] = ble_raw.get("ble_status", "unknown")

    return data


# ═══════════════════════════════════════════════════════════════
#  Coordinateur Unique (Cloud + BLE passif)
# ═══════════════════════════════════════════════════════════════

class FliprDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinateur principal pour Flipr. Gère le Cloud en actif et le BLE en passif."""

    def __init__(self, hass: HomeAssistant, api_client: FliprApiClient, flipr_id: str, entry: ConfigEntry, store):
        super().__init__(
            hass, 
            _LOGGER, 
            name="flipr_pool",
            update_interval=None  # Désactivation du polling automatique HA pour gérer notre propre boucle
        )
        self.api_client = api_client
        self.flipr_id = flipr_id
        self.config_entry = entry
        self._store = store
        
        self.place_id = None
        self.hub_id = flipr_id if flipr_id.upper().startswith("G") else None
        self.token = None

    async def _async_update_data(self):
        """Fetch données du Cloud (uniquement appelé lors d'un Forcer Actualisation ou au 1er démarrage)."""
        try:
            async with async_timeout.timeout(60):
                data_raw = await self.api_client.get_pool_data(self.flipr_id, self.place_id, self.hub_id)
                
                if data_raw.get("place_id") and not self.place_id:
                    self.place_id = data_raw["place_id"]
                if data_raw.get("hub_id") and not self.hub_id:
                    self.hub_id = data_raw["hub_id"]
                
                try:
                    import json
                    debug_path = self.hass.config.path("flipr_debug.json")
                    debug_content = json.dumps(data_raw, indent=2, default=str)
                    await self.hass.async_add_executor_job(
                        lambda: open(debug_path, "w").write(debug_content)
                    )
                except Exception as e:
                    _LOGGER.debug("Erreur écriture flipr_debug.json: %s", e)

                m = data_raw.get("module_last_measure")
                s = data_raw.get("module_shortterm")
                
                if not m:
                    raise UpdateFailed("Aucune mesure (last_measure) reçue du Cloud.")
                # NewResume imbrique les données dans Current, vérifier les deux niveaux
                check = m.get("Current", m) if isinstance(m.get("Current"), dict) else m
                if (check.get("Temperature") is None and check.get("temperature") is None) and (check.get("PH") is None and check.get("ph") is None):
                    raise UpdateFailed("L'API a retourné des valeurs nulles/vides.")

                m["alerts_raw"] = data_raw.get("alerts", [])
                m["thresholds_raw"] = data_raw.get("thresholds", {})

                data = _compute_pool_data(m, s, self.config_entry, data_source="cloud")
                hub_state = data_raw.get("hub_state", {})
                data["hub_mode"] = hub_state.get("Mode")
                data["hub_state"] = hub_state.get("Status")
                
                # Conserver les propriétés BLE existantes s'il y en a
                if self.data:
                    data["ble_rssi"] = self.data.get("ble_rssi")
                    data["ble_status"] = self.data.get("ble_status")

                self.hass.async_create_task(self._async_save(data))
                return data
        except Exception as err:
            if self.data:
                _LOGGER.warning("Erreur inattendue Flipr Cloud (%s). Conservation des dernières données.", err)
                return self.data
            raise UpdateFailed(f"Erreur inattendue Flipr Cloud: {err}")

    async def async_update_cloud_data_safe(self):
        """Boucle de polling interne qui esquive les Timeouts de Home Assistant."""
        try:
            data = await self._async_update_data()
            if data:
                self.async_set_updated_data(data)
        except Exception as err:
            _LOGGER.warning("Erreur lors de la mise à jour périodique Cloud : %s", err)

    @callback
    def async_update_ble_data(self, ble_raw: dict):
        """Reçoit de nouvelles données du Bluetooth et les fusionne."""
        ble_data = _compute_ble_pool_data(ble_raw, self.config_entry)
        
        merged = dict(self.data) if self.data else {}
        
        # Surcharge le Cloud par le BLE, mais ignore les valeurs "None" du BLE
        # (car le BLE ne transmet pas l'UV, la météo, etc.)
        for k, v in ble_data.items():
            if v is not None:
                merged[k] = v
        
        self.async_set_updated_data(merged)
        self.hass.async_create_task(self._async_save(merged))

    async def _async_save(self, data: dict) -> None:
        """Sauvegarde les données sur le disque."""
        try:
            saveable = {}
            for k, v in data.items():
                if isinstance(v, datetime):
                    saveable[k] = v.isoformat()
                else:
                    saveable[k] = v
            await self._store.async_save(saveable)
        except Exception as e:
            _LOGGER.debug("Impossible de sauvegarder localement: %s", e)


# ═══════════════════════════════════════════════════════════════
#  Setup de l'intégration
# ═══════════════════════════════════════════════════════════════

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    email    = entry.data.get("email")
    password = entry.data.get("password")
    flipr_id = entry.data.get("flipr_id")
    session  = async_get_clientsession(hass)

    opts = {**entry.data, **entry.options}
    ble_enabled = opts.get(CONF_BLE_ENABLED, False)
    ble_address = opts.get(CONF_BLE_ADDRESS, "")

    # ── Persistance locale ──────────────────────────────────
    store = Store(hass, STORE_VERSION, _store_key(entry.entry_id))

    # ── Initialisation API & Coordinateur ───────────────────
    api_client = None
    coordinator = None

    if email and password:
        from .api import FliprApiClient
        api_client = FliprApiClient(session, email, password)
        coordinator = FliprDataUpdateCoordinator(hass, api_client, flipr_id, entry, store)

    if not coordinator:
        _LOGGER.error("Impossible de configurer l'intégration Flipr (Cloud manquant).")
        return False

    # ── Initialisation du Polling BLE ────────────────────────
    if ble_enabled and ble_address:
        from homeassistant.helpers.event import async_track_time_interval

        async def _async_poll_ble(now=None):
            try:
                from .ble_client import read_flipr_ble
                ble_raw = await read_flipr_ble(ble_address, hass=hass)
                coordinator.async_update_ble_data(ble_raw)
                _LOGGER.info(
                    "Flipr BLE: mesure OK (pH=%.2f, T=%.1f°C, RSSI=%s)",
                    ble_raw.get("ph") or 0, ble_raw.get("temperature") or 0, ble_raw.get("ble_rssi")
                )
            except Exception as err:
                _LOGGER.warning("Flipr BLE: échec de la lecture (%s)", err)
                
        # Démarrage immédiat en tâche de fond
        hass.async_create_task(_async_poll_ble())
        
        # Programmation périodique
        entry.async_on_unload(
            async_track_time_interval(
                hass, _async_poll_ble, timedelta(minutes=BLE_UPDATE_INTERVAL_DEFAULT)
            )
        )
        _LOGGER.info("Flipr: Polling BLE activé (adresse: %s, intervalle: %d min)", ble_address, BLE_UPDATE_INTERVAL_DEFAULT)

    # ── Initialisation du Polling Cloud (Custom) ─────────────
    if coordinator:
        from homeassistant.helpers.event import async_track_time_interval
        async def _async_poll_cloud(now=None):
            await coordinator.async_update_cloud_data_safe()
        
        entry.async_on_unload(
            async_track_time_interval(
                hass, _async_poll_cloud, timedelta(minutes=CLOUD_UPDATE_INTERVAL_MIN)
            )
        )

    # ── Restauration locale au démarrage ────────────────────
    restored = await store.async_load()
    if restored:
        _LOGGER.debug("Flipr: données restaurées depuis le disque local.")
        coordinator.async_set_updated_data(restored)

    # ── Enregistrement ──────────────────────────────────────
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,  # Le coordinateur unique
    }

    # ── Services Personnalisés ──────────────────────────────
    async def handle_force_cloud_sync(call: ServiceCall):
        device_id = call.data.get("device_id")
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if device:
            for eid in device.config_entries:
                if eid in hass.data.get(DOMAIN, {}):
                    c = hass.data[DOMAIN][eid]["coordinator"]
                    await c.async_request_refresh()
                    break

    async def handle_update_dimensions(call: ServiceCall):
        device_id = call.data.get("device_id")
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if device:
            for eid in device.config_entries:
                c_entry = hass.config_entries.async_get_entry(eid)
                if c_entry and c_entry.domain == DOMAIN:
                    new_options = dict(c_entry.options)
                    if call.data.get("length") is not None:
                        new_options["pool_length"] = call.data.get("length")
                    if call.data.get("width") is not None:
                        new_options["pool_width"] = call.data.get("width")
                    if call.data.get("depth") is not None:
                        new_options["pool_depth"] = call.data.get("depth")
                    hass.config_entries.async_update_entry(c_entry, options=new_options)
                    if eid in hass.data.get(DOMAIN, {}):
                        c = hass.data[DOMAIN][eid]["coordinator"]
                        await c.async_request_refresh()
                    break

    if not hass.services.has_service(DOMAIN, "force_cloud_sync"):
        hass.services.async_register(DOMAIN, "force_cloud_sync", handle_force_cloud_sync)
    if not hass.services.has_service(DOMAIN, "update_dimensions"):
        hass.services.async_register(DOMAIN, "update_dimensions", handle_update_dimensions)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Premier refresh (Cloud) ──────────────────────────────
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Flipr: premier refresh Cloud échoué (%s)", err)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok