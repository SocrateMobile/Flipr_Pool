"""Flipr Pool — Double Coordinateur Cloud + BLE avec fusion automatique.

Architecture :
- cloud_coordinator  : API REST GoFlipr, toutes les 15 minutes
- ble_coordinator    : Bluetooth BLE local, toutes les 60 minutes (si activé)
- merged_coordinator : fusionne les deux, garde le plus récent, alimente les entités
"""

import logging
from datetime import timedelta, datetime, timezone
import async_timeout
import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

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
)
from .chemistry import (
    compute_isl,
    compute_ph_equilibrium,
    estimate_free_chlorine,
    compute_active_chlorine_from_fc,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "select", "switch", "number", "button"]
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


def _safe_timestamp(dt_val) -> datetime | None:
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

def _compute_pool_data(m, s, entry, data_source="cloud"):
    """Calcule toutes les valeurs dérivées à partir des mesures brutes.

    Fonctionne avec les données Cloud (API JSON) ou BLE (dict décodé).
    Le paramètre `data_source` est injecté dans le résultat.
    """

    # ── Mesures brutes ───────────────────────────────────────
    ph_raw      = m.get("PH") or m.get("ph")
    redox_raw   = m.get("OxydoReductionPotentiel") or m.get("oxydoReductionPotentiel") or m.get("redox")
    battery_raw = m.get("Battery") or m.get("battery")
    cond_raw    = m.get("Conductivity") or m.get("conductivity")
    desinf_raw  = m.get("Desinfectant") or m.get("desinfectant") or m.get("chlorine")

    ph_val      = ph_raw.get("Value")            if isinstance(ph_raw, dict)      else ph_raw
    redox_val   = redox_raw.get("Value")         if isinstance(redox_raw, dict)   else redox_raw
    battery_val = round(battery_raw.get("Deviation", 0) * 100, 1) if isinstance(battery_raw, dict) else battery_raw
    cond_val    = cond_raw.get("Value")          if isinstance(cond_raw, dict)    else cond_raw

    # ── Statuts pH & Chlore ─────────────────────────────────
    ph_sector   = ph_raw.get("DeviationSector")  if isinstance(ph_raw, dict) else None
    ph_status   = "OK" if ph_sector == "OK" else (ph_raw.get("Message", "Inconnu") if isinstance(ph_raw, dict) else None)

    cl_val      = round(desinf_raw.get("Value"), 3) if isinstance(desinf_raw, dict) and desinf_raw.get("Value") is not None else desinf_raw
    cl_sector   = desinf_raw.get("DeviationSector") if isinstance(desinf_raw, dict) else None
    cl_status   = "OK" if cl_sector == "OK" else (desinf_raw.get("Message", "Inconnu") if isinstance(desinf_raw, dict) else None)

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

    # ── Température Air ─────────────────────────────────────
    air_temp = None
    water_state = None
    if isinstance(s, dict):
        air_temp = s.get("AirTemperature") or s.get("airTemperature")
        water_state = s.get("WaterState") or s.get("waterState")
    elif isinstance(s, list) and len(s) > 0:
        first_s = s[0]
        if isinstance(first_s, dict):
            air_temp = first_s.get("AirTemperature") or first_s.get("airTemperature")
            water_state = first_s.get("WaterState") or first_s.get("waterState")

    if air_temp is None:
        air_temp = m.get("AirTemperature") or m.get("airTemperature")

    # ── Durée de pompage & Conseil ──────────────────────────
    water_temp = m.get("Temperature")
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
        "redox":               redox_val,
        "battery":             battery_val,
        "conductivity":        cond_val,
        "uv_index":            m.get("UvIndex"),
        "air_temp":            air_temp,
        "water_state":         water_state,
        "chlorine":            cl_val,
        "chlorine_status":     cl_status,
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
    }


def _compute_ble_pool_data(ble_raw: dict, entry) -> dict:
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
#  FliprMergedCoordinator — Fusion Cloud + BLE
# ═══════════════════════════════════════════════════════════════

class FliprMergedCoordinator(DataUpdateCoordinator):
    """Coordinateur factice qui fusionne les données Cloud et BLE.

    N'a pas de `update_method` propre — il est alimenté par les listeners
    des deux coordinateurs enfants. Il sert de source unique pour toutes
    les entités (CoordinatorEntity).
    """

    def __init__(self, hass, logger, name, cloud_coord, ble_coord, store, entry):
        # Pas d'update_method ni d'update_interval — c'est un coordinateur passif
        super().__init__(hass, logger, name=name)
        self.cloud_coord = cloud_coord
        self.ble_coord = ble_coord
        self._store = store
        self._entry = entry

        # Données internes par source
        self._cloud_data: dict | None = None
        self._ble_data: dict | None = None

        # Attributs publics hérités de l'ancien coordinateur
        self.flipr_id = cloud_coord.flipr_id
        self.place_id = cloud_coord.place_id
        self.token = cloud_coord.token

        # S'abonner aux mises à jour des deux coordinateurs
        self._unsub_cloud = cloud_coord.async_add_listener(self._on_cloud_update)
        if ble_coord is not None:
            self._unsub_ble = ble_coord.async_add_listener(self._on_ble_update)
        else:
            self._unsub_ble = None

    @callback
    def _on_cloud_update(self) -> None:
        """Appelé chaque fois que le coordinateur Cloud reçoit de nouvelles données."""
        if self.cloud_coord.data is not None:
            self._cloud_data = self.cloud_coord.data
            # Synchroniser token et place_id
            self.token = getattr(self.cloud_coord, "token", self.token)
            self.place_id = getattr(self.cloud_coord, "place_id", self.place_id)
        self._merge_and_publish()

    @callback
    def _on_ble_update(self) -> None:
        """Appelé chaque fois que le coordinateur BLE reçoit de nouvelles données."""
        if self.ble_coord is not None and self.ble_coord.data is not None:
            self._ble_data = self.ble_coord.data
        self._merge_and_publish()

    def _merge_and_publish(self) -> None:
        """Fusionne les données Cloud et BLE : le plus récent gagne."""
        cloud_ts = _safe_timestamp(
            self._cloud_data.get("last_update") if self._cloud_data else None
        )
        ble_ts = _safe_timestamp(
            self._ble_data.get("last_update") if self._ble_data else None
        )

        # Choisir la source la plus récente
        if cloud_ts and ble_ts:
            if ble_ts > cloud_ts:
                merged = dict(self._ble_data)
                merged["data_source"] = "bluetooth"
            else:
                merged = dict(self._cloud_data)
                merged["data_source"] = "cloud"
        elif self._ble_data and not self._cloud_data:
            merged = dict(self._ble_data)
            merged["data_source"] = "bluetooth"
        elif self._cloud_data:
            merged = dict(self._cloud_data)
            merged["data_source"] = "cloud"
        else:
            return  # Rien à publier

        # Toujours garder les infos Hub (cloud only)
        if self._cloud_data:
            merged.setdefault("hub_mode", self._cloud_data.get("hub_mode"))
            merged.setdefault("hub_state", self._cloud_data.get("hub_state"))
            merged.setdefault("thresholds", self._cloud_data.get("thresholds"))
            merged.setdefault("last_alert", self._cloud_data.get("last_alert"))

        # Toujours garder les infos BLE (ble only)
        if self._ble_data:
            merged.setdefault("ble_rssi", self._ble_data.get("ble_rssi"))
            merged.setdefault("ble_status", self._ble_data.get("ble_status"))
        else:
            merged.setdefault("ble_rssi", None)
            merged.setdefault("ble_status", "disabled")

        # Publier vers toutes les entités (via async_set_updated_data)
        self.async_set_updated_data(merged)

        # Sauvegarde locale asynchrone
        self.hass.async_create_task(self._async_save(merged))

    async def _async_save(self, data: dict) -> None:
        """Sauvegarde les données fusionnées sur le disque."""
        try:
            # Convertir les datetime en string pour la sérialisation JSON
            saveable = {}
            for k, v in data.items():
                if isinstance(v, datetime):
                    saveable[k] = v.isoformat()
                else:
                    saveable[k] = v
            await self._store.async_save(saveable)
        except Exception as e:
            _LOGGER.debug("Impossible de sauvegarder localement: %s", e)

    def attach_ble_coordinator(self, ble_coord) -> None:
        """Attache un coordinateur BLE après coup (si activé dynamiquement)."""
        if self._unsub_ble:
            self._unsub_ble()
        self.ble_coord = ble_coord
        if ble_coord is not None:
            self._unsub_ble = ble_coord.async_add_listener(self._on_ble_update)
        else:
            self._unsub_ble = None

    def detach_ble_coordinator(self) -> None:
        """Détache le coordinateur BLE (quand le switch BLE est désactivé)."""
        if self._unsub_ble:
            self._unsub_ble()
            self._unsub_ble = None
        self.ble_coord = None
        self._ble_data = None
        # Re-publier avec cloud seulement
        if self._cloud_data:
            self._merge_and_publish()


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

    # ─────────────────────────────────────────────────────────
    #  1. Coordinateur CLOUD (15 min)
    # ─────────────────────────────────────────────────────────
    async def _async_fetch_cloud():
        try:
            async with async_timeout.timeout(60):
                # Authentification
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
                    cloud_coordinator.token = token

                headers = {"Authorization": f"Bearer {token}"}

                # Mesures réelles
                measure_url = f"https://apis.goflipr.com/modules/{flipr_id}/survey/last"
                async with session.get(measure_url, headers=headers) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"Erreur API lastmeasure ({resp.status})")
                    m = await resp.json()

                # Prévisions (ShortTerm)
                short_url = f"https://apis.goflipr.com/modules/{flipr_id}/shortterm"
                async with session.get(short_url, headers=headers) as resp:
                    s = await resp.json() if resp.status == 200 else {}

                # État du Hub (Filtration)
                hub_url = f"https://apis.goflipr.com/hub/{flipr_id}"
                async with session.get(hub_url, headers=headers) as resp:
                    h = await resp.json() if resp.status == 200 else {}

                # Découverte du place_id
                if not cloud_coordinator.place_id:
                    async with session.get(PLACES_URL, headers=headers) as resp_p:
                        if resp_p.status == 200:
                            places = await resp_p.json()
                            if places:
                                cloud_coordinator.place_id = places[0].get("Id")

                # Alertes
                alerts = []
                if cloud_coordinator.place_id:
                    alert_url = ALERTS_URL.format(api_base="https://apis.goflipr.com", place_id=cloud_coordinator.place_id)
                    async with session.get(alert_url, headers=headers) as resp:
                        if resp.status == 200:
                            alerts = await resp.json()

                # Seuils
                thresholds = {}
                threshold_url = THRESHOLDS_URL.format(api_base="https://apis.goflipr.com", flipr_id=flipr_id)
                async with session.get(threshold_url, headers=headers) as resp:
                    if resp.status == 200:
                        thresholds = await resp.json()

                m["alerts_raw"] = alerts
                m["thresholds_raw"] = thresholds

                data = _compute_pool_data(m, s, entry, data_source="cloud")
                data["hub_mode"] = h.get("Mode")
                data["hub_state"] = h.get("Status")
                return data

        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Erreur Flipr Cloud: {err}")

    cloud_coordinator = DataUpdateCoordinator(
        hass, _LOGGER, name="flipr_pool_cloud",
        update_method=_async_fetch_cloud,
        update_interval=timedelta(minutes=CLOUD_UPDATE_INTERVAL_MIN),
    )
    cloud_coordinator.flipr_id = flipr_id
    cloud_coordinator.place_id = None
    cloud_coordinator.token = None

    # ─────────────────────────────────────────────────────────
    #  2. Coordinateur BLE (60 min, si activé)
    # ─────────────────────────────────────────────────────────
    ble_coordinator = None

    if ble_enabled and ble_address:
        async def _async_fetch_ble():
            try:
                from .ble_client import read_flipr_ble, FliprBleError
                ble_raw = await read_flipr_ble(ble_address, hass=hass)
                data = _compute_ble_pool_data(ble_raw, entry)
                _LOGGER.info(
                    "Flipr BLE: mesure OK (pH=%.2f, T=%.1f°C, RSSI=%s)",
                    data.get("ph") or 0, data.get("temperature") or 0, data.get("ble_rssi")
                )
                return data
            except Exception as err:
                _LOGGER.warning("Flipr BLE: échec de la lecture (%s)", err)
                raise UpdateFailed(f"Erreur Flipr BLE: {err}")

        ble_coordinator = DataUpdateCoordinator(
            hass, _LOGGER, name="flipr_pool_ble",
            update_method=_async_fetch_ble,
            update_interval=timedelta(minutes=BLE_UPDATE_INTERVAL_DEFAULT),
        )
        _LOGGER.info("Flipr: coordinateur BLE activé (adresse: %s, intervalle: %d min)", ble_address, BLE_UPDATE_INTERVAL_DEFAULT)

    # ─────────────────────────────────────────────────────────
    #  3. Coordinateur Fusionné (passif, alimenté par les listeners)
    # ─────────────────────────────────────────────────────────
    merged_coordinator = FliprMergedCoordinator(
        hass, _LOGGER, name="flipr_pool",
        cloud_coord=cloud_coordinator,
        ble_coord=ble_coordinator,
        store=store,
        entry=entry,
    )

    # ── Restauration locale au démarrage ────────────────────
    restored = await store.async_load()
    if restored:
        _LOGGER.debug("Flipr: données restaurées depuis le disque local.")
        merged_coordinator.async_set_updated_data(restored)

    # ── Enregistrement ──────────────────────────────────────
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "cloud": cloud_coordinator,
        "ble": ble_coordinator,
        "merged": merged_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Premier refresh des coordinateurs ───────────────────
    try:
        await cloud_coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Flipr Cloud: premier refresh échoué (%s)", err)

    if ble_coordinator is not None:
        try:
            await ble_coordinator.async_config_entry_first_refresh()
        except Exception as err:
            _LOGGER.warning("Flipr BLE: premier refresh échoué (%s)", err)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok