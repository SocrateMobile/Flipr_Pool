from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["flipr_pool"][entry.entry_id]
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
        ("Température Air",  "air_temp",        "°C",    SensorDeviceClass.TEMPERATURE, "mdi:cloud-sun"),
        ("État de l'eau",    "water_state",     None,    None,                          "mdi:pool"),
        ("Chlore",           "chlorine",        "mg/L",  None,                          "mdi:water-check"),
        ("Statut Chlore",    "chlorine_status", None,    None,                          "mdi:water-check-outline"),
        ("Dernière Mesure",  "last_update",     None,    SensorDeviceClass.TIMESTAMP,   "mdi:clock-outline"),
        # ── Calculés (v2.0) ────────────────────────────────────
        ("Volume Piscine",   "pool_volume",     "L",     None,                          "mdi:pool"),
        ("Dose pH−",         "dose_ph_minus",   "g",     None,                          "mdi:minus-circle-outline"),
        ("Dose pH+",         "dose_ph_plus",    "g",     None,                          "mdi:plus-circle-outline"),
        ("Dose Chlore",      "dose_chlorine",   "g",     None,                          "mdi:water-plus"),
        ("Durée Pompe",      "pump_hours",      "h",     None,                          "mdi:pump"),
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
        return self.coordinator.data.get(self._data_key)