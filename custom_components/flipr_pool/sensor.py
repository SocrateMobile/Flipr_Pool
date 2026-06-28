from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from typing import Any
from .const import (
    DOMAIN,
    PH_TARGET,
    PH_MINUS_DOSE,
    PH_PLUS_DOSE,
    CHLORINE_TARGET,
    CHLORINE_SHOCK_TARGET
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Configuration des capteurs (sensors) Flipr."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    flipr_id = entry.data.get("flipr_id", "flipr")

    sensors_config = [
        # (translation_key, data_key, unit, device_class, icon, category)
        # ── Mesures capteur ────────────────────────────────────
        ("temperature",     "temperature",     "°C",    SensorDeviceClass.TEMPERATURE, "mdi:thermometer", None),
        ("ph",              "ph",              "pH",    None,                          "mdi:ph", None),
        ("ph_status",       "ph_status",       None,    None,                          "mdi:ph", None),
        ("redox",           "redox",           "mV",    None,                          "mdi:flask-outline", None),
        ("battery",         "battery",         "%",     SensorDeviceClass.BATTERY,     "mdi:battery", EntityCategory.DIAGNOSTIC),
        ("conductivity",    "conductivity",    "µS/cm", None,                          "mdi:lightning-bolt", None),
        ("uv_index",        "uv_index",        "UV",    None,                          "mdi:sun-wireless", None),
        ("air_temp",        "air_temp",        "°C",    SensorDeviceClass.TEMPERATURE, "mdi:thermometer-lines", None),
        ("water_state",     "water_state",     None,    None,                          "mdi:pool", None),
        ("chlorine",        "chlorine",        "mg/L",  None,                          "mdi:water-check", None),
        ("chlorine_status", "chlorine_status", None,    None,                          "mdi:water-check-outline", None),
        ("last_update",     "last_update",     None,    SensorDeviceClass.TIMESTAMP,   "mdi:clock-outline", EntityCategory.DIAGNOSTIC),
        # ── Calculés (v2.0) ────────────────────────────────────
        ("pool_volume",     "pool_volume",     "L",     None,                          "mdi:pool", EntityCategory.DIAGNOSTIC),
        ("dose_ph_minus",   "dose_ph_minus",   "g",     None,                          "mdi:minus-circle-outline", None),
        ("dose_ph_plus",    "dose_ph_plus",    "g",     None,                          "mdi:plus-circle-outline", None),
        ("dose_cl_maint",   "dose_cl_maint",   "g",     None,                          "mdi:water-plus", None),
        ("dose_cl_shock",   "dose_cl_shock",   "g",     None,                          "mdi:flash", None),
        ("pump_hours",      "pump_hours",      "h",     None,                          "mdi:pump", None),
        ("conseil_filtration", "conseil_filtration", None,  None,                          "mdi:information-outline", None),
        ("last_alert",      "last_alert",      None,    None,                          "mdi:alert-circle-outline", None),
        # ── Chimie avancée (LSI & Chlore Actif) ───────────────
        ("lsi",             "lsi",             None,    None,                          "mdi:water-percent", None),
        ("lsi_status",      "lsi_status",      None,    None,                          "mdi:water-check", None),
        ("ph_equilibre",    "ph_equilibre",    "pH",    None,                          "mdi:water-opacity", None),
        ("free_chlorine",   "free_chlorine",   "mg/L",  None,                          "mdi:water-check", None),
        ("active_chlorine", "active_chlorine", "mg/L",  None,                          "mdi:chemical-weapon", None),
        # ── Double Coordinateur ────────────────────────────────
        ("data_source",     "data_source",     None,    None,                          "mdi:swap-horizontal", EntityCategory.DIAGNOSTIC),
        ("ble_rssi",        "ble_rssi",        "dBm",   None,                          "mdi:bluetooth-connect", EntityCategory.DIAGNOSTIC),
        ("ble_status",      "ble_status",      None,    None,                          "mdi:bluetooth-settings", EntityCategory.DIAGNOSTIC),
        ("version",         "version",         None,    None,                          "mdi:information-outline", EntityCategory.DIAGNOSTIC),
    ]

    entities = [FliprFullSensor(coordinator, flipr_id, *config) for config in sensors_config]
    async_add_entities(entities)


class FliprFullSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, flipr_id: str, translation_key: str, data_key: str, unit: str | None, device_class: SensorDeviceClass | None, icon: str, category: EntityCategory | None) -> None:
        super().__init__(coordinator)
        self._flipr_id = flipr_id
        self._attr_translation_key = translation_key
        self._data_key = data_key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_entity_category = category
        self._attr_unique_id = f"flipr_{coordinator.config_entry.entry_id}_{data_key}"

        # MEASUREMENT uniquement pour les capteurs numériques avec unité
        if device_class != SensorDeviceClass.TIMESTAMP and unit is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> DeviceInfo:
        """Regroupe tous les capteurs sous un appareil Flipr dans la page Appareils."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._flipr_id)},
            name=f"Flipr Pool ({self._flipr_id})",
            manufacturer="Flipr",
            model="Flipr Analyser",
            configuration_url="https://app.goflipr.com",
        )

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._data_key)
        if self._attr_device_class == SensorDeviceClass.TIMESTAMP and isinstance(val, str):
            try:
                from homeassistant.util.dt import parse_datetime
                return parse_datetime(val)
            except Exception:
                pass
        return val

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Attributs additionnels pour donner plus de contexte (ex: cible pH)."""
        attrs = {}
        if self._data_key == "dose_ph_minus":
            attrs["Cible"] = PH_TARGET
            attrs["Note"] = "Calculé sur base de granulés (100g/m³/unité pH)"
        elif self._data_key == "dose_ph_plus":
            attrs["Cible"] = PH_TARGET
            attrs["Note"] = "Calculé sur base de granulés (150g/m³/unité pH)"
        elif self._data_key == "dose_cl_maint":
            attrs["Cible"] = f"{CHLORINE_TARGET} mg/L"
            attrs["Usage"] = "Maintien du taux idéal"
        elif self._data_key == "dose_cl_shock":
            attrs["Cible"] = f"{CHLORINE_SHOCK_TARGET} mg/L"
            attrs["Usage"] = "Rattrapage eau trouble/algues"
        elif self._data_key == "lsi":
            attrs["Interprétation"] = (
                "< -0.3 → eau corrosive | -0.3 à +0.3 → équilibrée | > +0.3 → entartrante"
            )
            lsi_stat = self.coordinator.data.get("lsi_status") if self.coordinator.data else None
            if lsi_stat:
                attrs["Statut"] = lsi_stat
        elif self._data_key == "active_chlorine":
            attrs["Note"] = "HOCl (forme biocide) estimée à partir du chlore libre et du pH"
        elif self._data_key == "free_chlorine":
            attrs["Note"] = "Estimé à partir du Redox, pH et stabilisant (CYA)"
        elif self._data_key == "data_source":
            attrs["Cloud"] = "API REST GoFlipr (15 min)"
            attrs["Bluetooth"] = "BLE local (60 min)"
        return attrs