from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import aiohttp
from .const import DOMAIN, API_BASE_URL, THRESHOLDS_URL

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["merged"]

    # On ajoute 4 entités pour les seuils
    entities = [
        FliprThresholdNumber(coordinator, "pH Min", "ph_min", 6.0, 8.0, 0.1, "mdi:ph"),
        FliprThresholdNumber(coordinator, "pH Max", "ph_max", 7.0, 9.0, 0.1, "mdi:ph"),
        FliprThresholdNumber(coordinator, "Chlore Min", "cl_min", 0.0, 2.0, 0.1, "mdi:water-minus"),
        FliprThresholdNumber(coordinator, "Chlore Max", "cl_max", 1.0, 5.0, 0.1, "mdi:water-plus"),
    ]

    # On ajoute 3 entités pour les dimensions de la piscine
    entities.extend([
        FliprDimensionNumber(coordinator, "Longueur", "pool_length", "mdi:arrow-expand-horizontal"),
        FliprDimensionNumber(coordinator, "Largeur", "pool_width", "mdi:arrow-expand-vertical"),
        FliprDimensionNumber(coordinator, "Profondeur", "pool_depth", "mdi:arrow-down-bold"),
    ])

    async_add_entities(entities)

class FliprThresholdNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, name, key, min_val, max_val, step, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Flipr Seuil {name}"
        self._attr_unique_id = f"flipr_{coordinator.config_entry.entry_id}_{key}"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_icon = icon

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        t = self.coordinator.data.get("thresholds", {})
        if not t: return None

        if self._key == "ph_min": return t.get("PHMin")
        if self._key == "ph_max": return t.get("PHMax")
        if self._key == "cl_min": return t.get("ChlorineMin")
        if self._key == "cl_max": return t.get("ChlorineMax")
        return None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name=f"Flipr Pool ({self.coordinator.flipr_id})",
            manufacturer="Flipr",
        )

    async def async_set_native_value(self, value: float):
        serial = self.coordinator.flipr_id
        token = self.coordinator.token
        if not self.coordinator.data:
            return
        # On récupère les seuils actuels pour ne modifier que celui-ci
        t = dict(self.coordinator.data.get("thresholds", {}) or {})

        if self._key == "ph_min": t["PHMin"] = value
        elif self._key == "ph_max": t["PHMax"] = value
        elif self._key == "cl_min": t["ChlorineMin"] = value
        elif self._key == "cl_max": t["ChlorineMax"] = value

        url = THRESHOLDS_URL.format(api_base=API_BASE_URL, flipr_id=serial)
        headers = {"Authorization": f"Bearer {token}"}
        session = async_get_clientsession(self.coordinator.hass)
        async with session.put(url, headers=headers, json=t) as resp:
            if resp.status == 200:
                self.coordinator.data["thresholds"] = t
                self.async_write_ha_state()

class FliprDimensionNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, name, key, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Flipr {name} (m)"
        self._attr_unique_id = f"flipr_{coordinator.config_entry.entry_id}_{key}"
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 50.0
        self._attr_native_step = 0.1
        self._attr_native_unit_of_measurement = "m"
        self._attr_icon = icon

    @property
    def native_value(self):
        entry = self.coordinator.config_entry
        opts = {**entry.data, **entry.options}
        return float(opts.get(self._key, 0))

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name=f"Flipr Pool ({self.coordinator.flipr_id})",
            manufacturer="Flipr",
        )

    async def async_set_native_value(self, value: float):
        entry = self.coordinator.config_entry
        new_options = dict(entry.options)
        new_options[self._key] = value

        # On met à jour les options de l'entrée de configuration en préservant les données (credentials)
        self.coordinator.hass.config_entries.async_update_entry(entry, data=dict(entry.data), options=new_options)

        # On force un rafraîchissement des calculs via le coordinateur Cloud
        cloud_coord = self.coordinator.cloud_coord
        if cloud_coord:
            await cloud_coord.async_request_refresh()
