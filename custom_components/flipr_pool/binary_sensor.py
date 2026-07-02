"""Binary sensors for Flipr Pool."""

import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinators = hass.data[DOMAIN][entry.entry_id]
    coordinator = coordinators["coordinator"]

    entities = [
        FliprProblemBinarySensor(coordinator, "ph_simple", "ph_status", "Statut pH"),
        FliprProblemBinarySensor(coordinator, "chlorine_simple", "chlorine_status", "Statut Chlore"),
    ]

    async_add_entities(entities)

class FliprProblemBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor to report problems (KO = ON, OK = OFF)."""
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: DataUpdateCoordinator, data_key: str, translation_key: str, default_name: str) -> None:
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_translation_key = translation_key
        self._attr_name = default_name
        self._attr_unique_id = f"flipr_{coordinator.flipr_id}_{translation_key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, getattr(self.coordinator, "flipr_id", ""))},
            name="Flipr Piscine",
            manufacturer="Flipr",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if there is a problem (KO)."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._data_key)
        # "KO" -> True (Problem), "OK" -> False (No problem)
        return val == "KO"

    @property
    def extra_state_attributes(self):
        """Include the detailed message from the original status."""
        if not self.coordinator.data:
            return {}
        
        # Le _data_key est "ph_simple", le status détaillé est "ph_status"
        detail_key = self._data_key.replace("_simple", "_status")
        msg = self.coordinator.data.get(detail_key)
        
        return {
            "Message": msg if msg != "OK" else "Aucun problème"
        }
