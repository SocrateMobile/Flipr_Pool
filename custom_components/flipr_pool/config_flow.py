"""Config flow et Options flow pour Flipr Pool.

Flow d'installation :
  1. async_step_user      → Email + mot de passe
  2. async_step_select_device → Liste des appareils du compte (Flipr + Hub) → sélection

Options flow :
  1. async_step_init        → Dimensions, chimie, choix "Scanner BLE" ou sauvegarder
  2. async_step_ble_scan    → Lance un scan BLE, affiche les appareils trouvés
  3. async_step_ble_confirm → Confirme l'appareil BLE sélectionné
"""

import logging
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    API_BASE_URL,
    AUTH_URL,
    MODULES_URL,
    PLACES_URL,
    CONF_TAC, CONF_TH, CONF_CYA, CONF_TDS,
    DEFAULT_TAC, DEFAULT_TH, DEFAULT_CYA, DEFAULT_TDS,
    CONF_BLE_ENABLED,
    CONF_BLE_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Helpers Cloud
# ═══════════════════════════════════════════════════════════════

async def _async_authenticate(email: str, password: str) -> dict | None:
    """Authentification Cloud. Retourne le JSON complet (avec access_token) ou None."""
    auth_data = {
        "grant_type": "password",
        "username": email.strip(),
        "password": password.strip(),
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(AUTH_URL, data=auth_data, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            return None


async def _async_list_cloud_devices(token: str) -> list[dict]:
    """Liste tous les appareils (Flipr + Hub) du compte utilisateur.

    Récupère d'abord les appareils depuis l'endpoint /place (recommandé)
    puis utilise /modules en secours.
    """
    headers = {"Authorization": f"Bearer {token}"}
    devices = []

    async with aiohttp.ClientSession() as session:
        # 1. Récupération via les Places (Piscines)
        try:
            async with session.get(PLACES_URL, headers=headers) as resp:
                if resp.status == 200:
                    places = await resp.json()
                    if isinstance(places, list):
                        for place in places:
                            # Extraction des modules Flipr dans cette place
                            modules = place.get("Modules") or place.get("modules") or []
                            if isinstance(modules, list):
                                for mod in modules:
                                    serial = mod.get("Serial") or mod.get("serial") or mod.get("Id") or ""
                                    if serial:
                                        devices.append({
                                            "serial": str(serial),
                                            "type": "flipr",
                                            "label": f"Flipr {serial}",
                                            "raw": mod,
                                        })

                            # Extraction des Hubs associés
                            hubs = place.get("Hubs") or place.get("hubs") or []
                            if isinstance(hubs, list):
                                for hub in hubs:
                                    hub_serial = hub.get("Serial") or hub.get("Id") or ""
                                    if hub_serial:
                                        devices.append({
                                            "serial": str(hub_serial),
                                            "type": "hub",
                                            "label": f"Hub {hub_serial}",
                                            "raw": hub,
                                        })
        except Exception as e:
            _LOGGER.warning("Erreur lors de la récupération des places: %s", e)

        # 2. Secours via l'endpoint direct /modules
        try:
            async with session.get(MODULES_URL, headers=headers) as resp:
                if resp.status == 200:
                    modules = await resp.json()
                    if isinstance(modules, list):
                        existing_serials = {d["serial"] for d in devices}
                        for mod in modules:
                            serial = mod.get("Serial") or mod.get("serial") or mod.get("Id") or ""
                            if serial and str(serial) not in existing_serials:
                                devices.append({
                                    "serial": str(serial),
                                    "type": "flipr",
                                    "label": f"Flipr {serial}",
                                    "raw": mod,
                                })
        except Exception as e:
            _LOGGER.debug("Erreur ou indisponibilité de l'endpoint /modules: %s", e)

    return devices


# ═══════════════════════════════════════════════════════════════
#  Config Flow (installation)
# ═══════════════════════════════════════════════════════════════

class FliprConfigFlow(config_entries.ConfigFlow, domain="flipr_pool"):
    """Gestion du formulaire de configuration pour Flipr Pool.

    Étape 1 : Identifiants (email + mot de passe)
    Étape 2 : Sélection de l'appareil parmi ceux détectés sur le compte
    """

    VERSION = 1

    def __init__(self):
        self._email = None
        self._password = None
        self._token = None
        self._cloud_devices = []
        self._selected_flipr_id = None
        self._discovered_ble_address = ""
        self._matched_mac_by_serial = {}
        self._manual_user_input = {}
        self._from_manual_device = False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FliprOptionsFlow()

    async def async_step_user(self, user_input=None):
        """Étape 1 : Email + mot de passe."""
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            email = user_input["email"]
            password = user_input["password"]

            try:
                auth_result = await _async_authenticate(email, password)
                if auth_result and auth_result.get("access_token"):
                    self._email = email
                    self._password = password
                    self._token = auth_result["access_token"]

                    # Découvrir les appareils du compte
                    self._cloud_devices = await _async_list_cloud_devices(self._token)
                    _LOGGER.info("Flipr: %d appareils trouvés sur le compte", len(self._cloud_devices))

                    if self._cloud_devices:
                        # 1. Scan BLE automatique (5 secondes)
                        has_flipr = any(d["type"] == "flipr" for d in self._cloud_devices)
                        self._matched_mac_by_serial = {}
                        if has_flipr:
                            _LOGGER.info("Flipr : Lancement du scan BLE automatique au démarrage (5s)...")
                            try:
                                from .ble_client import scan_for_flipr
                                discovered = await scan_for_flipr(timeout=5.0)
                                
                                # Appariement par S/N exact
                                for dev in discovered:
                                    for cloud_dev in self._cloud_devices:
                                        if cloud_dev["type"] == "flipr" and cloud_dev["serial"].upper() == dev["serial"].upper():
                                            self._matched_mac_by_serial[cloud_dev["serial"]] = dev["address"]
                                            _LOGGER.info("Flipr BLE : Appareil %s détecté par S/N à l'adresse %s", cloud_dev["serial"], dev["address"])

                                # Appariement 1-à-1 si un seul Flipr cloud et un seul Flipr BLE trouvé
                                cloud_fliprs = [d for d in self._cloud_devices if d["type"] == "flipr"]
                                if len(cloud_fliprs) == 1 and len(discovered) == 1:
                                    single_cloud = cloud_fliprs[0]
                                    single_ble = discovered[0]
                                    if single_cloud["serial"] not in self._matched_mac_by_serial:
                                        self._matched_mac_by_serial[single_cloud["serial"]] = single_ble["address"]
                                        _LOGGER.info("Flipr BLE : Appariement automatique 1-à-1 de %s avec %s", single_cloud["serial"], single_ble["address"])
                            except Exception as e:
                                _LOGGER.warning("Erreur lors du scan BLE automatique : %s", e)

                        # Si un Flipr est associé au compte mais non trouvé sur le réseau local,
                        # on demande l'adresse MAC manuellement.
                        if has_flipr and not self._matched_mac_by_serial:
                            return await self.async_step_manual_mac()

                        return await self.async_step_select_device()
                    else:
                        # Pas de devices trouvés → formulaire manuel
                        errors["base"] = "no_devices"
                        description_placeholders["error_info"] = (
                            "Aucun appareil Flipr trouvé sur ce compte. "
                            "Vous pouvez saisir le numéro de série manuellement."
                        )
                        return await self.async_step_manual_device()
                else:
                    errors["base"] = "invalid_auth"
            except Exception as e:
                errors["base"] = "cannot_connect"
                description_placeholders["error_info"] = str(e)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("email"): str,
                vol.Required("password"): str,
            }),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_select_device(self, user_input=None):
        """Étape 2 : Sélection de l'appareil Flipr parmi ceux du compte."""
        if user_input is not None:
            selected = user_input["device"]
            # Trouver le device correspondant
            chosen = None
            for dev in self._cloud_devices:
                if dev["serial"] == selected:
                    chosen = dev
                    break

            self._selected_flipr_id = chosen["serial"] if chosen else selected
            
            # Associer l'adresse MAC si elle a été trouvée automatiquement
            if self._selected_flipr_id in self._matched_mac_by_serial:
                self._discovered_ble_address = self._matched_mac_by_serial[self._selected_flipr_id]

            return await self.async_step_pool_details()

    async def async_step_manual_mac(self, user_input=None):
        """Saisie manuelle de l'adresse MAC si le Flipr n'est pas détecté."""
        if user_input is not None:
            self._discovered_ble_address = user_input.get("ble_address", "").strip()
            if self._from_manual_device:
                return self.async_show_form(
                    step_id="pool_details",
                    data_schema=vol.Schema({
                        vol.Optional("pool_length", default=self._manual_user_input.get("pool_length", 0.0)): vol.Coerce(float),
                        vol.Optional("pool_width",  default=self._manual_user_input.get("pool_width",  0.0)): vol.Coerce(float),
                        vol.Optional("pool_depth",  default=self._manual_user_input.get("pool_depth",  0.0)): vol.Coerce(float),
                        vol.Optional(CONF_TAC, default=self._manual_user_input.get(CONF_TAC, DEFAULT_TAC)): vol.Coerce(float),
                        vol.Optional(CONF_TH,  default=self._manual_user_input.get(CONF_TH,  DEFAULT_TH)):  vol.Coerce(float),
                        vol.Optional(CONF_CYA, default=self._manual_user_input.get(CONF_CYA, DEFAULT_CYA)): vol.Coerce(float),
                        vol.Optional(CONF_TDS, default=self._manual_user_input.get(CONF_TDS, DEFAULT_TDS)): vol.Coerce(float),
                    }),
                )
            return await self.async_step_select_device()

        return self.async_show_form(
            step_id="manual_mac",
            data_schema=vol.Schema({
                vol.Optional("ble_address", default=""): str,
            }),
        )

        # Construire la liste déroulante
        device_options = {}
        for dev in self._cloud_devices:
            serial_upper = dev["serial"].upper()
            label = dev["label"]
            
            if serial_upper.startswith("F"):
                prefix = "✅ "  # Carré vert avec check (Flipr)
            elif serial_upper.startswith("G"):
                prefix = "🔌 "  # Pompe / Hub
            elif serial_upper.startswith("C"):
                prefix = "📡 "  # Passerelle de connexion / Link
            else:
                # Fallback selon le type détecté
                if dev["type"] == "flipr":
                    prefix = "✅ "
                else:
                    prefix = "🔌 "
                    
            device_options[dev["serial"]] = f"{prefix}{label}"

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema({
                vol.Required("device"): vol.In(device_options),
            }),
            description_placeholders={
                "nb_devices": str(len(self._cloud_devices)),
            },
        )

    async def async_step_pool_details(self, user_input=None):
        """Étape 3 : Dimensions de la piscine et paramètres de chimie."""
        if user_input is not None:
            ble_address = self._discovered_ble_address
            ble_enabled = bool(ble_address)

            return self.async_create_entry(
                title=f"Flipr ({self._email} — {self._selected_flipr_id})",
                data={
                    "email": self._email,
                    "password": self._password,
                    "flipr_id": self._selected_flipr_id,
                    "ble_address": ble_address,
                    "ble_enabled": ble_enabled,
                    **user_input,
                },
            )

        return self.async_show_form(
            step_id="pool_details",
            data_schema=vol.Schema({
                vol.Optional("pool_length", default=0.0): vol.Coerce(float),
                vol.Optional("pool_width",  default=0.0): vol.Coerce(float),
                vol.Optional("pool_depth",  default=0.0): vol.Coerce(float),
                vol.Optional(CONF_TAC, default=DEFAULT_TAC): vol.Coerce(float),
                vol.Optional(CONF_TH,  default=DEFAULT_TH):  vol.Coerce(float),
                vol.Optional(CONF_CYA, default=DEFAULT_CYA): vol.Coerce(float),
                vol.Optional(CONF_TDS, default=DEFAULT_TDS): vol.Coerce(float),
            }),
        )

    async def async_step_manual_device(self, user_input=None):
        """Fallback : saisie manuelle du flipr_id si la découverte échoue."""
        if user_input is not None:
            flipr_id = user_input["flipr_id"]
            self._selected_flipr_id = flipr_id
            self._manual_user_input = user_input

            # Lancement d'un scan BLE rapide de 5s
            self._discovered_ble_address = ""
            try:
                from .ble_client import scan_for_flipr
                discovered = await scan_for_flipr(timeout=5.0)
                for dev in discovered:
                    if dev["serial"].upper() == flipr_id.upper():
                        self._discovered_ble_address = dev["address"]
                        break
            except Exception:
                pass

            if not self._discovered_ble_address:
                # Redirection vers manual_mac si non détecté en BLE
                self._from_manual_device = True
                return await self.async_step_manual_mac()

            return self.async_create_entry(
                title=f"Flipr ({self._email} — {flipr_id})",
                data={
                    "email": self._email,
                    "password": self._password,
                    "flipr_id": flipr_id,
                    "ble_address": self._discovered_ble_address,
                    "ble_enabled": True,
                    **user_input,
                },
            )

        return self.async_show_form(
            step_id="manual_device",
            data_schema=vol.Schema({
                vol.Required("flipr_id"): str,
                vol.Optional("pool_length", default=0.0): vol.Coerce(float),
                vol.Optional("pool_width",  default=0.0): vol.Coerce(float),
                vol.Optional("pool_depth",  default=0.0): vol.Coerce(float),
                vol.Optional(CONF_TAC, default=DEFAULT_TAC): vol.Coerce(float),
                vol.Optional(CONF_TH,  default=DEFAULT_TH):  vol.Coerce(float),
                vol.Optional(CONF_CYA, default=DEFAULT_CYA): vol.Coerce(float),
                vol.Optional(CONF_TDS, default=DEFAULT_TDS): vol.Coerce(float),
            }),
        )


# ═══════════════════════════════════════════════════════════════
#  Options Flow (configuration après installation)
# ═══════════════════════════════════════════════════════════════

class FliprOptionsFlow(config_entries.OptionsFlow):
    """Options flow multi-étapes :

    init          → Dimensions, chimie, option "Lancer un scan BLE"
    ble_scan      → Scan BLE en cours → résultats
    ble_confirm   → Confirme l'appareil BLE sélectionné

    Note: self.config_entry est fourni automatiquement par HA (2024+).
    """

    def __init__(self):
        self._ble_devices = []

    async def async_step_init(self, user_input=None):
        """Page principale des options."""
        if user_input is not None:
            scan_ble = user_input.pop("scan_ble", False)

            # Sauvegarder les options principales
            self._pending_options = user_input

            if scan_ble:
                # L'utilisateur veut scanner → on passe à l'étape BLE
                return await self.async_step_ble_scan()

            # Sinon on sauvegarde directement
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        data = self.config_entry.data

        def _get(key, default):
            return options.get(key, data.get(key, default))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                # ── Dimensions piscine ──────────────────────────────
                vol.Optional("pool_length", default=_get("pool_length", 0.0)): vol.Coerce(float),
                vol.Optional("pool_width",  default=_get("pool_width",  0.0)): vol.Coerce(float),
                vol.Optional("pool_depth",  default=_get("pool_depth",  0.0)): vol.Coerce(float),
                # ── Chimie de l'eau (pour calculs LSI et Chlore Actif) ──
                vol.Optional(CONF_TAC, default=_get(CONF_TAC, DEFAULT_TAC)): vol.Coerce(float),
                vol.Optional(CONF_TH,  default=_get(CONF_TH,  DEFAULT_TH)):  vol.Coerce(float),
                vol.Optional(CONF_CYA, default=_get(CONF_CYA, DEFAULT_CYA)): vol.Coerce(float),
                vol.Optional(CONF_TDS, default=_get(CONF_TDS, DEFAULT_TDS)): vol.Coerce(float),
                # ── Bluetooth BLE ──────────────────────────────────
                vol.Optional(CONF_BLE_ENABLED, default=_get(CONF_BLE_ENABLED, False)): bool,
                vol.Optional(CONF_BLE_ADDRESS, default=_get(CONF_BLE_ADDRESS, "")): str,
                # ── Action : scanner les appareils BLE à portée ────
                vol.Optional("scan_ble", default=False): bool,
            }),
        )

    async def async_step_ble_scan(self, user_input=None):
        """Étape 2 : Scan BLE — recherche des Flipr à portée."""
        errors = {}

        if user_input is not None:
            selected = user_input.get("ble_device", "")
            if selected and selected != "__none__":
                # Trouver les infos du device sélectionné
                chosen = None
                for dev in self._ble_devices:
                    if dev["address"] == selected:
                        chosen = dev
                        break

                if chosen:
                    return await self.async_step_ble_confirm(chosen)

            errors["base"] = "no_ble_selected"

        # Lancer le scan BLE
        _LOGGER.info("Flipr: lancement du scan BLE (15 secondes)...")
        try:
            from .ble_client import scan_for_flipr
            self._ble_devices = await scan_for_flipr(timeout=15.0)
        except Exception as e:
            _LOGGER.error("Erreur lors du scan BLE: %s", e)
            self._ble_devices = []

        if not self._ble_devices:
            # Aucun appareil trouvé → retour aux options avec message
            _LOGGER.warning("Flipr: aucun appareil BLE détecté à portée")
            # Sauvegarder les options en attente sans BLE
            if hasattr(self, "_pending_options"):
                return self.async_create_entry(title="", data=self._pending_options)
            return await self.async_step_init()

        # Construire la liste déroulante avec les infos détaillées
        device_options = {}
        for dev in self._ble_devices:
            label = (
                f"{dev['name']} — {dev['model']} "
                f"(S/N: {dev['serial']}, MAC: {dev['address']}, "
                f"RSSI: {dev.get('rssi', '?')} dBm)"
            )
            device_options[dev["address"]] = label

        return self.async_show_form(
            step_id="ble_scan",
            data_schema=vol.Schema({
                vol.Required("ble_device"): vol.In(device_options),
            }),
            errors=errors,
            description_placeholders={
                "nb_ble": str(len(self._ble_devices)),
            },
        )

    async def async_step_ble_confirm(self, chosen_device=None, user_input=None):
        """Étape 3 : Confirme la sélection BLE et sauvegarde tout."""
        if user_input is not None or chosen_device is not None:
            # Fusionner les options en attente + les infos BLE
            final_options = {}
            if hasattr(self, "_pending_options"):
                final_options.update(self._pending_options)

            if chosen_device:
                final_options[CONF_BLE_ENABLED] = True
                final_options[CONF_BLE_ADDRESS] = chosen_device["address"]
                final_options["ble_model"] = chosen_device.get("model", "Inconnu")
                final_options["ble_serial"] = chosen_device.get("serial", "")
                final_options["ble_name"] = chosen_device.get("name", "")

            return self.async_create_entry(title="", data=final_options)

        # Fallback — ne devrait pas arriver
        return await self.async_step_init()