from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import (
    DOMAIN,
    PH_TARGET,
    PH_MINUS_DOSE,
    PH_PLUS_DOSE,
    CHLORINE_TARGET,
    CHLORINE_SHOCK_TARGET
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["merged"]
    flipr_id = entry.data.get("flipr_id", "flipr")

    sensors_config = [
        # (Nom, Clé Data, Unité, DeviceClass, Icône)
        # ── Mesures capteur ────────────────────────────────────
        ("Température Eau",  "temperature",     "°C",    SensorDeviceClass.TEMPERATURE, "mdi:thermometer"),
        ("pH",               "ph",              "pH",    None,                          "mdi:ph"),
        ("Statut pH",        "ph_status",       None,    None,                          "mdi:ph"),
        ("Redox",            "redox",           "mV",    None,                          "mdi:flask-outline"),
        ("Batterie",         "battery",         "%",     SensorDeviceClass.BATTERY,     "mdi:battery"),
        ("Conductivité",     "conductivity",    "µS/cm", None,                          "mdi:lightning-bolt"),
        ("Indice UV",        "uv_index",        "UV",    None,                          "mdi:sun-wireless"),
        ("Température Air",  "air_temp",        "°C",    SensorDeviceClass.TEMPERATURE, "mdi:thermometer-lines"),
        ("État de l'eau",    "water_state",     None,    None,                          "mdi:pool"),
        ("Chlore",           "chlorine",        "mg/L",  None,                          "mdi:water-check"),
        ("Statut Chlore",    "chlorine_status", None,    None,                          "mdi:water-check-outline"),
        ("Dernière Mesure",  "last_update",     None,    SensorDeviceClass.TIMESTAMP,   "mdi:clock-outline"),
        # ── Calculés (v2.0) ────────────────────────────────────
        ("Volume Piscine",   "pool_volume",     "L",     None,                          "mdi:pool"),
        ("Dose pH−",         "dose_ph_minus",   "g",     None,                          "mdi:minus-circle-outline"),
        ("Dose pH+",         "dose_ph_plus",    "g",     None,                          "mdi:plus-circle-outline"),
        ("Dose Chlore (Entretien)", "dose_cl_maint", "g",   None,                          "mdi:water-plus"),
        ("Dose Chlore (Choc)",      "dose_cl_shock", "g",   None,                          "mdi:flash"),
        ("Durée Pompe",      "pump_hours",      "h",     None,                          "mdi:pump"),
        ("Conseil Filtration", "conseil_filtration", None,  None,                          "mdi:information-outline"),
        ("Dernière Alerte",  "last_alert",      None,    None,                          "mdi:alert-circle-outline"),
        # ── Chimie avancée (LSI & Chlore Actif) ───────────────
        ("Indice LSI",        "lsi",             None,    None,                          "mdi:water-percent"),
        ("Statut Eau (LSI)",  "lsi_status",      None,    None,                          "mdi:water-check"),
        ("pH Équilibre",      "ph_equilibre",    "pH",    None,                          "mdi:water-opacity"),
        ("Chlore Libre Est.", "free_chlorine",   "mg/L",  None,                          "mdi:water-check"),
        ("Chlore Actif HOCl","active_chlorine", "mg/L",  None,                          "mdi:chemical-weapon"),
        # ── Double Coordinateur ────────────────────────────────
        ("Source Active",     "data_source",     None,    None,                          "mdi:swap-horizontal"),
        ("BLE Signal",        "ble_rssi",        "dBm",   None,                          "mdi:bluetooth-connect"),
        ("BLE Statut",        "ble_status",      None,    None,                          "mdi:bluetooth-settings"),
    ]

    entities = [FliprFullSensor(coordinator, flipr_id, *config) for config in sensors_config]
    async_add_entities(entities)


class FliprFullSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, flipr_id, name, data_key, unit, device_class, icon):
        super().__init__(coordinator)
        self._flipr_id = flipr_id
        self._attr_name = f"Flipr {name}"
        self._data_key = data_key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = icon
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
    def native_value(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._data_key)

    @property
    def extra_state_attributes(self):
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