"""Expose un bouton pour forcer une mise à jour immédiate du Flipr (Cloud et BLE)."""

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinators = hass.data[DOMAIN][entry.entry_id]
    merged = coordinators["merged"]

    async_add_entities([FliprForceUpdateButton(merged, coordinators)])


class FliprForceUpdateButton(CoordinatorEntity, ButtonEntity):
    """Bouton pour déclencher une analyse et récupération de données immédiates."""

    def __init__(self, coordinator, coordinators):
        super().__init__(coordinator)
        self._coordinators = coordinators
        self._attr_name = "Flipr Analyse Immédiate"
        self._attr_unique_id = f"flipr_{coordinator.config_entry.entry_id}_force_update"
        self._attr_icon = "mdi:sync"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name=f"Flipr Pool ({self.coordinator.flipr_id})",
            manufacturer="Flipr",
        )

    async def async_press(self) -> None:
        """Déclenche la mise à jour forcée sur tous les coordinateurs actifs."""
        _LOGGER.info("Flipr : Demande d'analyse et mise à jour forcée demandée par le bouton")

        # 1. Mettre à jour le Cloud immédiatement
        cloud = self._coordinators.get("cloud")
        if cloud:
            try:
                _LOGGER.debug("Flipr : Forçage de la mise à jour Cloud...")
                await cloud.async_refresh()
            except Exception as err:
                _LOGGER.warning("Flipr : Échec du refresh forcé Cloud (%s)", err)

        # 2. Mettre à jour le BLE immédiatement (si activé)
        ble = self._coordinators.get("ble")
        if ble and ble.update_interval is not None:
            try:
                _LOGGER.debug("Flipr : Forçage de la mise à jour BLE...")
                await ble.async_refresh()
            except Exception as err:
                _LOGGER.warning("Flipr : Échec du refresh forcé BLE (%s)", err)
