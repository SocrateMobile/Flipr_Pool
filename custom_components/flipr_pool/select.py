import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Les modes acceptés par l'API officielle Flipr (PUT hub/{serial}/mode/{behavior})
# behavior est un STRING : "manual", "auto", "planning"
# Note : "off" n'existe pas dans l'API — on utilise POST Manual/False pour arrêter
VALID_MODES = ["manual", "planning", "auto"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([FliprModeSelect(coordinator)])

class FliprModeSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "mode_filtration"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"flipr_{coordinator.flipr_id}_mode"
        self._attr_options = VALID_MODES
        self._attr_icon = "mdi:auto-fix"

    @property
    def current_option(self):
        """Retourne le mode actuel depuis le coordinateur."""
        if not self.coordinator.data:
            return None
        mode = self.coordinator.data.get("hub_mode")
        # S'assurer que le mode est dans la liste des options valides
        if mode in VALID_MODES:
            return mode
        return None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name="Flipr Piscine",
            manufacturer="Flipr",
        )

    async def async_select_option(self, option: str) -> None:
        hub_id = getattr(self.coordinator, "hub_id", None) or self.coordinator.flipr_id
        api_client = getattr(self.coordinator, "api_client", None)
        
        if not api_client:
            _LOGGER.warning("Le contrôle du mode de filtration n'est pas disponible en mode local uniquement.")
            return

        try:
            # API officielle : PUT hub/{serial}/mode/{behavior}
            # behavior = string parmi "manual", "auto", "planning"
            url = f"https://apis.goflipr.com/hub/{hub_id}/mode/{option}"
            await api_client._request("PUT", url)

            if self.coordinator.data:
                self.coordinator.data["hub_mode"] = option
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Erreur lors du changement de mode Flipr Hub : %s", err)