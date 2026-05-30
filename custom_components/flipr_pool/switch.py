import logging
import aiohttp
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, API_BASE_URL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FliprPumpSwitch(coordinator)])

class FliprPumpSwitch(CoordinatorEntity, SwitchEntity):
    """Switch pour contrôler la marche forcée de la pompe."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Flipr Pompe Filtration"
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
    def is_on(self):
        """Retourne True si le mode est 'manual' ou si l'état est 'on'."""
        mode = self.coordinator.data.get("hub_mode")
        state = self.coordinator.data.get("hub_state")
        return mode == "manual" or state == "on"

    async def async_turn_on(self, **kwargs):
        """Active la marche forcée (mode manual)."""
        await self._async_set_mode("manual")

    async def async_turn_off(self, **kwargs):
        """Désactive la filtration (mode off)."""
        await self._async_set_mode("off")

    async def _async_set_mode(self, mode):
        serial = self.coordinator.flipr_id
        token = self.coordinator.token
        url = f"{API_BASE_URL}/hub/{serial}/mode/{mode}"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers) as resp:
                if resp.status == 200:
                    # On met à jour l'état localement pour une réactivité immédiate
                    self.coordinator.data["hub_mode"] = mode
                    self.async_write_ha_state()
                    _LOGGER.info("Flipr Hub: Mode changé en %s", mode)
                else:
                    _LOGGER.error("Erreur lors du changement de mode Flipr: %s", resp.status)
