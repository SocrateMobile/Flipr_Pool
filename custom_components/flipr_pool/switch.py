"""Switches pour Flipr Pool : pompe filtration + activation BLE."""

import logging
from datetime import timedelta
import aiohttp
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from typing import Any
from .const import (
    DOMAIN,
    API_BASE_URL,
    CONF_BLE_ENABLED,
    CONF_BLE_ADDRESS,
    BLE_UPDATE_INTERVAL_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinators = hass.data[DOMAIN][entry.entry_id]
    coordinator = coordinators["coordinator"]

    entities = [FliprPumpSwitch(coordinator)]

    # Toujours ajouter le switch BLE (il montre "désactivé" si pas d'adresse)
    entities.append(FliprBleSwitch(hass, entry, coordinator))

    async_add_entities(entities)


class FliprPumpSwitch(CoordinatorEntity, SwitchEntity):
    """Switch pour contrôler la marche forcée de la pompe."""
    _attr_has_entity_name = True
    _attr_translation_key = "pump_filtration"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"flipr_{coordinator.config_entry.entry_id}_pump"
        self._attr_icon = "mdi:pump"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name=f"Flipr Pool ({self.coordinator.flipr_id})",
            manufacturer="Flipr",
        )

    @property
    def is_on(self) -> bool | None:
        """Retourne True si le mode est 'manual' ou si l'état est 'on'."""
        if not self.coordinator.data:
            return None
        state = self.coordinator.data.get("hub_state")
        return state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Active la marche forcée (mode manual + pompe ON)."""
        await self._async_set_pump_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Désactive la filtration (mode manual + pompe OFF)."""
        await self._async_set_pump_state(False)

    async def _async_set_pump_state(self, state: bool) -> None:
        hub_id = getattr(self.coordinator, "hub_id", None) or self.coordinator.flipr_id
        api_client = getattr(self.coordinator, "api_client", None)
        
        if not api_client:
            _LOGGER.warning("Le contrôle de la pompe n'est pas disponible en mode local uniquement.")
            return

        try:
            # 1. Mettre le Hub en mode manuel d'abord (indispensable pour forcer la marche)
            mode_url = f"{API_BASE_URL}/hub/{hub_id}/mode/manual"
            await api_client._request("PUT", mode_url)

            # 2. Envoyer la commande ON/OFF
            state_str = "True" if state else "False"
            state_url = f"{API_BASE_URL}/hub/{hub_id}/Manual/{state_str}"
            await api_client._request("POST", state_url)

            # 3. Mettre à jour l'état localement pour une réactivité immédiate de l'interface HA
            if self.coordinator.data:
                self.coordinator.data["hub_mode"] = "manual"
                self.coordinator.data["hub_state"] = "on" if state else "off"
            self.async_write_ha_state()
            _LOGGER.info("Flipr Hub %s: Pompe filtration changée en %s", hub_id, "ON" if state else "OFF")

        except Exception as e:
            _LOGGER.error("Erreur lors du contrôle de la pompe du Hub %s: %s", hub_id, e)


class FliprBleSwitch(SwitchEntity):
    """Switch pour activer/désactiver le coordinateur BLE."""
    _attr_has_entity_name = True
    _attr_translation_key = "ble_scan"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator: DataUpdateCoordinator) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        
        self._attr_unique_id = f"flipr_{entry.entry_id}_ble_switch"
        self._attr_icon = "mdi:bluetooth-connect"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name=f"Flipr Pool ({self.coordinator.flipr_id})",
            manufacturer="Flipr",
        )

    @property
    def is_on(self) -> bool:
        """Le switch est ON si le BLE est activé dans les options."""
        opts = {**self.entry.data, **self.entry.options}
        return bool(opts.get(CONF_BLE_ENABLED, False))

    @property
    def available(self) -> bool:
        """Disponible seulement si une adresse BLE est configurée."""
        opts = {**self.entry.data, **self.entry.options}
        return bool(opts.get(CONF_BLE_ADDRESS, ""))

    @property
    def extra_state_attributes(self):
        opts = {**self.entry.data, **self.entry.options}
        attrs = {
            "Adresse BLE": opts.get(CONF_BLE_ADDRESS, "Non configurée"),
            "Intervalle": f"{BLE_UPDATE_INTERVAL_DEFAULT} min",
        }
        if self.coordinator.data and self.coordinator.data.get("ble_rssi"):
            attrs["Statut MAJ BLE"] = "Succès"
        return attrs

    async def async_turn_on(self, **kwargs):
        """Active le polling BLE et recharge l'intégration."""
        opts = {**self.entry.data, **self.entry.options}
        ble_address = opts.get(CONF_BLE_ADDRESS, "")
        if not ble_address:
            _LOGGER.warning("Flipr BLE: impossible d'activer — aucune adresse BLE configurée")
            return

        new_options = dict(self.entry.options)
        new_options[CONF_BLE_ENABLED] = True
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        
        # Recharger l'intégration pour démarrer le polling BLE
        await self.hass.config_entries.async_reload(self.entry.entry_id)

    async def async_turn_off(self, **kwargs):
        """Désactive le polling BLE et recharge l'intégration."""
        new_options = dict(self.entry.options)
        new_options[CONF_BLE_ENABLED] = False
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        
        # Recharger l'intégration pour stopper le polling BLE
        await self.hass.config_entries.async_reload(self.entry.entry_id)
