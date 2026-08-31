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
    async_add_entities([
        FliprForceUpdateButton(coordinator),
        FliprGenerateCardButton(coordinator)
    ])


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


class FliprGenerateCardButton(CoordinatorEntity, ButtonEntity):
    """Bouton pour générer le code YAML de la carte Lovelace avec les entités de l'utilisateur."""
    _attr_has_entity_name = True
    _attr_translation_key = "generate_card"

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"flipr_{coordinator.flipr_id}_generate_card"
        self._attr_icon = "mdi:code-json"
        self._attr_name = "Générer la carte Lovelace"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.flipr_id)},
            name="Flipr Piscine",
            manufacturer="Flipr",
        )

    async def async_press(self) -> None:
        """Génère le fichier YAML de la carte."""
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers import device_registry as dr
        from .card_template import COMBINED_CARD_TEMPLATE
        import os

        _LOGGER.info("Flipr : Génération de la carte Lovelace demandée")
        
        # 1. Obtenir les entités du device
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)
        device_id = None
        for device_entry in dev_reg.devices.values():
            if (DOMAIN, self.coordinator.flipr_id) in device_entry.identifiers:
                device_id = device_entry.id
                break
        
        if not device_id:
            _LOGGER.error("Flipr: Impossible de trouver l'appareil pour générer la carte")
            return

        entities = er.async_entries_for_device(ent_reg, device_id, include_disabled_entities=True)
        
        # 2. Déduire le préfixe et la pompe
        ph_entity = next((e for e in entities if e.entity_id.endswith("_ph") and e.domain == "sensor"), None)
        pump_entity = next((e for e in entities if e.domain == "switch" and ("pompe_filtration" in e.entity_id or "pump_filtration" in e.entity_id)), None)
        
        if not ph_entity:
            prefix = "sensor.flipr"
        else:
            prefix = ph_entity.entity_id.replace("_ph", "")
            
        pump_id = pump_entity.entity_id if pump_entity else "switch.flipr_pompe_filtration"
        
        # 3. Personnaliser le template
        yaml_content = COMBINED_CARD_TEMPLATE
        
        # Remplacer la logique dynamique Javascript par des variables en dur (plus rapide pour le frontend de l'utilisateur)
        js_search_ph = "const ph_entity_name = Object.keys(states).find(e => e.startsWith('sensor.') && e.includes('flipr') && e.endsWith('_ph'));"
        js_search_prefix = "const prefix = ph_entity_name ? ph_entity_name.replace('_ph', '') : 'sensor.flipr';"
        js_search_pump = "const pump_entity = Object.keys(states).find(e => e.startsWith('switch.') && (e.includes('pompe_filtration') || e.includes('pump_filtration')));"
        
        yaml_content = yaml_content.replace(js_search_ph, f"// Préfixe généré pour votre appareil : {prefix}\n          const prefix = '{prefix}';")
        yaml_content = yaml_content.replace(js_search_prefix, "")
        yaml_content = yaml_content.replace(js_search_pump, f"const pump_entity = '{pump_id}';")
        
        # Remplacer l'interpolation ${prefix} par le vrai préfixe
        yaml_content = yaml_content.replace("${prefix}", prefix)

        # 4. Écrire le fichier de façon asynchrone (non-bloquante pour l'event loop)
        file_path = self.hass.config.path("flipr_card.yaml")
        full_content = (
            "# ==============================================================================\n"
            "# CARTE LOVELACE FLIPR (Générée automatiquement)\n"
            "# \n"
            "# Ce code a été généré avec les identifiants exacts de vos capteurs.\n"
            "# Copiez tout le contenu de ce fichier et collez-le dans une carte\n"
            "# 'Manuel' ou dans l'éditeur de code de votre tableau de bord Lovelace.\n"
            "# \n"
            "# Prérequis : Vous devez installer la carte 'button-card' via HACS.\n"
            "# ==============================================================================\n\n"
            f"{yaml_content}"
        )

        def _write_yaml():
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_content)

        try:
            await self.hass.async_add_executor_job(_write_yaml)
            self.hass.components.persistent_notification.async_create(
                f"Le code de votre carte Lovelace a été généré avec succès avec le préfixe `{prefix}`.<br><br>Vous le trouverez dans le fichier <b>flipr_card.yaml</b> à la racine de votre dossier de configuration Home Assistant.<br><br>Copiez son contenu dans votre tableau de bord !",
                title="Flipr : Carte Lovelace Générée 🏊",
                notification_id="flipr_card_generated"
            )
            _LOGGER.info("Flipr : Fichier flipr_card.yaml généré avec succès")
            
        except Exception as err:
            _LOGGER.error("Flipr : Erreur lors de la génération du fichier yaml : %s", err)

