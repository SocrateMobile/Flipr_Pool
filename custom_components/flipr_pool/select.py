from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, API_BASE_URL

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["merged"]
    async_add_entities([FliprModeSelect(coordinator)])

class FliprModeSelect(CoordinatorEntity, SelectEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Flipr Mode Filtration"
        self._attr_unique_id = f"flipr_{coordinator.config_entry.entry_id}_mode"
        self._attr_options = ["auto", "manual", "off", "planning"]
        self._attr_icon = "mdi:auto-fix"

    @property
    def current_option(self):
        """Retourne le mode actuel depuis le coordinateur."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("hub_mode", "auto")

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name=f"Flipr Pool ({self.coordinator.flipr_id})",
            manufacturer="Flipr",
        )

    async def async_select_option(self, option: str):
        serial = self.coordinator.flipr_id
        headers = {"Authorization": f"Bearer {self.coordinator.token}"}

        # Mapping des modes pour l'API
        url = f"{API_BASE_URL}/hub/{serial}/mode/{option}"
        session = self.coordinator.hass.helpers.aiohttp_client.async_get_clientsession(self.coordinator.hass)
        async with session.put(url, headers=headers) as resp:
            if resp.status == 200:
                if self.coordinator.data:
                    self.coordinator.data["hub_mode"] = option
                self.async_write_ha_state()