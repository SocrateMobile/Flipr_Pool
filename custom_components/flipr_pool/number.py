import logging
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from .const import DOMAIN, API_BASE_URL, THRESHOLDS_URL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        FliprThresholdNumber(coordinator, "ph_min", "target_ph_min", 6.0, 8.0, 0.1, "mdi:ph", 7.0),
        FliprThresholdNumber(coordinator, "ph_max", "target_ph_max", 7.0, 9.0, 0.1, "mdi:ph", 7.4),
        FliprThresholdNumber(coordinator, "cl_min", "target_chlorine_min", 0.0, 2.0, 0.1, "mdi:water-minus", 1.0),
        FliprThresholdNumber(coordinator, "cl_max", "target_chlorine_max", 1.0, 5.0, 0.1, "mdi:water-plus", 3.0),
    ]

    # On ajoute 3 entités pour les dimensions de la piscine
    entities.extend([
        FliprDimensionNumber(coordinator, "pool_length", "mdi:arrow-expand-horizontal"),
        FliprDimensionNumber(coordinator, "pool_width", "mdi:arrow-expand-vertical"),
        FliprDimensionNumber(coordinator, "pool_depth", "mdi:arrow-down-bold"),
    ])

    async_add_entities(entities)

class FliprThresholdNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key, translation_key, min_val, max_val, step, icon, default_val):
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"flipr_{coordinator.flipr_id}_{key}"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_icon = icon
        self._default_val = default_val

    @property
    def native_value(self):
        if not self.coordinator.data:
            return self._default_val
        t = self.coordinator.data.get("thresholds", {})
        if not t:
            return self._default_val

        if self._key == "ph_min": return t.get("PHMin", self._default_val)
        if self._key == "ph_max": return t.get("PHMax", self._default_val)
        if self._key == "cl_min": return t.get("ChlorineMin", self._default_val)
        if self._key == "cl_max": return t.get("ChlorineMax", self._default_val)
        return self._default_val

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name="Flipr Piscine",
            manufacturer="Flipr",
        )

    async def async_set_native_value(self, value: float):
        serial = self.coordinator.flipr_id
        api_client = getattr(self.coordinator, "api_client", None)
        
        if not api_client:
            _LOGGER.warning("La modification des seuils n'est pas disponible en mode local uniquement.")
            return
        if not self.coordinator.data:
            return
            
        # On récupère les seuils actuels. S'ils sont absents, on met des valeurs par défaut
        # pour éviter d'envoyer un JSON incomplet à l'API Flipr.
        t = dict(self.coordinator.data.get("thresholds", {}) or {})
        
        t.setdefault("PHMin", 7.0)
        t.setdefault("PHMax", 7.4)
        t.setdefault("ChlorineMin", 1.0)
        t.setdefault("ChlorineMax", 3.0)

        if self._key == "ph_min": t["PHMin"] = value
        elif self._key == "ph_max": t["PHMax"] = value
        elif self._key == "cl_min": t["ChlorineMin"] = value
        elif self._key == "cl_max": t["ChlorineMax"] = value

        url = THRESHOLDS_URL.format(api_base=API_BASE_URL, flipr_id=serial)
        
        try:
            await api_client._request("PUT", url, json=t)
            self.coordinator.data["thresholds"] = t
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Erreur lors de la modification des seuils Flipr : %s", err)

class FliprDimensionNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, translation_key, icon):
        super().__init__(coordinator)
        self._key = translation_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"flipr_{coordinator.flipr_id}_{translation_key}"
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
            name="Flipr Piscine",
            manufacturer="Flipr",
        )

    async def async_set_native_value(self, value: float):
        entry = self.coordinator.config_entry
        new_options = dict(entry.options)
        new_options[self._key] = value

        # On met à jour les options de l'entrée de configuration en préservant les données (credentials)
        self.coordinator.hass.config_entries.async_update_entry(entry, data=dict(entry.data), options=new_options)

        # On force un rafraîchissement des calculs via le coordinateur
        await self.coordinator.async_request_refresh()
