"""Expose un bouton pour forcer une mise à jour immédiate du Flipr (Cloud et BLE)."""

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([FliprForceUpdateButton(coordinator)])


class FliprForceUpdateButton(CoordinatorEntity, ButtonEntity):
    """Bouton pour déclencher une analyse et récupération de données immédiates."""
    _attr_has_entity_name = True
    _attr_translation_key = "force_refresh"

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"flipr_{coordinator.flipr_id}_force_update"
        self._attr_icon = "mdi:sync"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name="Flipr Piscine",
            manufacturer="Flipr",
        )

    async def async_press(self) -> None:
        """Déclenche la mise à jour forcée du Cloud."""
        _LOGGER.info("Flipr : Demande d'analyse et mise à jour forcée demandée par le bouton")
        try:
            await self.coordinator.async_refresh()
        except Exception as err:
            _LOGGER.warning("Flipr : Échec du refresh forcé (%s)", err)
