"""Switches pour Flipr Pool : pompe filtration + activation BLE."""

import logging
from datetime import timedelta
import aiohttp
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo
from .const import (
    DOMAIN,
    API_BASE_URL,
    CONF_BLE_ENABLED,
    CONF_BLE_ADDRESS,
    BLE_UPDATE_INTERVAL_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinators = hass.data[DOMAIN][entry.entry_id]
    merged = coordinators["merged"]

    entities = [FliprPumpSwitch(merged)]

    # Toujours ajouter le switch BLE (il montre "désactivé" si pas d'adresse)
    entities.append(FliprBleSwitch(hass, entry, coordinators))

    async_add_entities(entities)


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
        if not self.coordinator.data:
            return None
        mode = self.coordinator.data.get("hub_mode")
        state = self.coordinator.data.get("hub_state")
        return mode == "manual" or state == "on"

    async def async_turn_on(self, **kwargs):
        """Active la marche forcée (mode manual + pompe ON)."""
        await self._async_set_pump_state(True)

    async def async_turn_off(self, **kwargs):
        """Désactive la filtration (mode manual + pompe OFF)."""
        await self._async_set_pump_state(False)

    async def _async_set_pump_state(self, state: bool):
        serial = self.coordinator.flipr_id
        hub_id = getattr(self.coordinator, "hub_id", None) or serial
        token = self.coordinator.token
        if not token:
            _LOGGER.warning("Le contrôle de la pompe de filtration n'est pas disponible en mode local uniquement.")
            return

        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            # 1. Mettre le Hub en mode manuel d'abord
            mode_url = f"{API_BASE_URL}/hub/{hub_id}/mode/manual"
            async with session.put(mode_url, headers=headers) as resp:
                if resp.status != 200:
                    _LOGGER.error("Erreur lors du passage en mode manuel du Hub %s: %s", hub_id, resp.status)
                    return

            # 2. Envoyer la commande ON/OFF
            state_str = "True" if state else "False"
            state_url = f"{API_BASE_URL}/hub/{hub_id}/Manual/{state_str}"
            async with session.post(state_url, headers=headers) as resp:
                if resp.status == 200:
                    # On met à jour l'état localement pour une réactivité immédiate
                    if self.coordinator.data:
                        self.coordinator.data["hub_mode"] = "manual"
                        self.coordinator.data["hub_state"] = "on" if state else "off"
                    self.async_write_ha_state()
                    _LOGGER.info("Flipr Hub %s: Pompe filtration changée en %s", hub_id, "ON" if state else "OFF")
                else:
                    _LOGGER.error("Erreur lors du contrôle de la pompe du Hub %s: %s", hub_id, resp.status)


class FliprBleSwitch(SwitchEntity):
    """Switch pour activer/désactiver le coordinateur BLE.

    Quand ON  → Crée (ou reprend) le coordinateur BLE, qui lance les lectures BLE toutes les 60 min.
    Quand OFF → Met le coordinateur BLE en pause et détache du merged coordinator.
    """

    def __init__(self, hass, entry, coordinators):
        self._hass = hass
        self._entry = entry
        self._coordinators = coordinators
        self._merged = coordinators["merged"]
        self._attr_name = "Flipr Mode Bluetooth (BLE)"
        self._attr_unique_id = f"flipr_{entry.entry_id}_ble_switch"
        self._attr_icon = "mdi:bluetooth-connect"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._merged.flipr_id)},
            name=f"Flipr Pool ({self._merged.flipr_id})",
            manufacturer="Flipr",
        )

    @property
    def is_on(self) -> bool:
        """Le switch est ON si le coordinateur BLE existe et a un intervalle actif."""
        ble = self._coordinators.get("ble")
        return ble is not None and ble.update_interval is not None

    @property
    def available(self) -> bool:
        """Disponible seulement si une adresse BLE est configurée."""
        opts = {**self._entry.data, **self._entry.options}
        return bool(opts.get(CONF_BLE_ADDRESS, ""))

    @property
    def extra_state_attributes(self):
        opts = {**self._entry.data, **self._entry.options}
        attrs = {
            "Adresse BLE": opts.get(CONF_BLE_ADDRESS, "Non configurée"),
            "Intervalle": f"{BLE_UPDATE_INTERVAL_DEFAULT} min",
        }
        ble = self._coordinators.get("ble")
        if ble and ble.last_update_success_time:
            attrs["Dernier succès BLE"] = ble.last_update_success_time.isoformat()
        return attrs

    async def async_turn_on(self, **kwargs):
        """Active le coordinateur BLE."""
        opts = {**self._entry.data, **self._entry.options}
        ble_address = opts.get(CONF_BLE_ADDRESS, "")
        if not ble_address:
            _LOGGER.warning("Flipr BLE: impossible d'activer — aucune adresse BLE configurée")
            return

        ble = self._coordinators.get("ble")

        if ble is None:
            # Créer un nouveau coordinateur BLE
            async def _async_fetch_ble():
                try:
                    from .ble_client import read_flipr_ble
                    from . import _compute_ble_pool_data
                    ble_raw = await read_flipr_ble(ble_address, hass=self._hass)
                    data = _compute_ble_pool_data(ble_raw, self._entry)
                    _LOGGER.info("Flipr BLE: mesure OK via switch")
                    return data
                except Exception as err:
                    raise UpdateFailed(f"Erreur Flipr BLE: {err}")

            ble = DataUpdateCoordinator(
                self._hass, _LOGGER, name="flipr_pool_ble",
                update_method=_async_fetch_ble,
                update_interval=timedelta(minutes=BLE_UPDATE_INTERVAL_DEFAULT),
            )
            self._coordinators["ble"] = ble
            _LOGGER.info("Flipr BLE: coordinateur créé (adresse: %s)", ble_address)
        else:
            # Reprendre le coordinateur existant
            ble.update_interval = timedelta(minutes=BLE_UPDATE_INTERVAL_DEFAULT)

        # Attacher au merged coordinator
        self._merged.attach_ble_coordinator(ble)

        # Persister l'option
        new_options = dict(self._entry.options)
        new_options[CONF_BLE_ENABLED] = True
        self._hass.config_entries.async_update_entry(self._entry, options=new_options)

        # Premier refresh BLE
        try:
            await ble.async_config_entry_first_refresh()
        except Exception as err:
            _LOGGER.warning("Flipr BLE: premier refresh échoué (%s)", err)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Désactive le coordinateur BLE."""
        ble = self._coordinators.get("ble")
        if ble is not None:
            ble.update_interval = None  # Pause — plus de refresh automatique
            _LOGGER.info("Flipr BLE: coordinateur mis en pause")

        # Détacher du merged coordinator
        self._merged.detach_ble_coordinator()

        # Persister l'option
        new_options = dict(self._entry.options)
        new_options[CONF_BLE_ENABLED] = False
        self._hass.config_entries.async_update_entry(self._entry, options=new_options)

        self.async_write_ha_state()
