import asyncio
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Les modes acceptés par l'API officielle Flipr (PUT /hub/{serial}/mode/{behavior})
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
            return "manual"
        mode = self.coordinator.data.get("hub_mode")
        if mode in VALID_MODES:
            return mode
        return "manual"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name="Flipr Piscine",
            manufacturer="Flipr",
        )

    async def async_select_option(self, option: str) -> None:
        if option not in VALID_MODES:
            return

        hub_id = getattr(self.coordinator, "hub_id", None)
        if not hub_id and self.coordinator.data:
            hub_id = self.coordinator.data.get("hub_id")

        if not hub_id and getattr(self.coordinator, "config_entry", None):
            hub_id = self.coordinator.config_entry.options.get("discovered_hub_id")

        if not hub_id:
            raw_mods = (self.coordinator.data or {}).get("raw_modules", []) if self.coordinator.data else []
            for m in raw_mods:
                s = str(m.get("Serial") or m.get("Id") or "")
                if s.startswith("CA"):
                    hub_id = s
                    break

        if not hub_id:
            if self.coordinator.flipr_id.startswith("CA") or self.coordinator.flipr_id.startswith("G") or self.coordinator.flipr_id.startswith("C"):
                hub_id = self.coordinator.flipr_id
            else:
                hub_id = "CA6268"

        # 1. Mise à jour optimiste immédiate dans HA
        if self.coordinator.data:
            self.coordinator.data["hub_mode"] = option
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()

        api_client = getattr(self.coordinator, "api_client", None)
        if not api_client:
            _LOGGER.warning("Le contrôle du mode de filtration n'est pas disponible en mode local uniquement.")
            return

        try:
            await api_client.set_hub_mode(hub_id, option)
            _LOGGER.info("Flipr Hub %s: Mode changé en '%s'", hub_id, option)
            if getattr(self.coordinator, "_store", None) and self.coordinator.data:
                self.hass.async_create_task(self.coordinator._async_save(self.coordinator.data))
        except Exception as err:
            _LOGGER.error("Erreur lors du changement de mode Flipr Hub : %s", err)