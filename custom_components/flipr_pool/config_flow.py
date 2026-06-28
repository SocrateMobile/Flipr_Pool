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
from homeassistant.helpers import selector

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

class FliprAuthError(Exception):
    """Exception levée en cas d'échec d'authentification."""

async def _async_authenticate(email: str, password: str) -> dict:
    """Authentification Cloud. Retourne le JSON complet (avec access_token) ou lève FliprAuthError."""
    auth_data = {
        "grant_type": "password",
        "username": email.strip(),
        "password": password.strip(),
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(AUTH_URL, data=auth_data, headers=headers) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    if json_data and json_data.get("access_token"):
                        return json_data
                    raise FliprAuthError("Réponse d'authentification invalide (token manquant).")
                
                if resp.status == 429:
                    raise FliprAuthError("Trop de requêtes vers le Cloud Flipr (Erreur 429). Votre IP est temporairement bloquée par Flipr. Réessayez plus tard ou utilisez le mode Local.")

                # Tenter d'extraire la description de l'erreur
                try:
                    err_data = await resp.json()
                    err_msg = err_data.get("error_description") or err_data.get("error") or f"HTTP {resp.status}"
                except Exception:
                    err_msg = await resp.text()
                
                raise FliprAuthError(f"Serveur Flipr : {err_msg[:150]}")
    except aiohttp.ClientError as e:
        raise FliprAuthError(f"Erreur de connexion réseau : {str(e)}")


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
        self._installation_type = "mix"

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FliprOptionsFlow()

    async def async_step_user(self, user_input=None):
        """Étape initiale : Choix du type d'installation."""
        if user_input is not None:
            self._installation_type = user_input["installation_type"]
            if self._installation_type == "local":
                return await self.async_step_local_bt()
            else:
                return await self.async_step_cloud_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("installation_type", default="mix"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["mix", "local", "cloud"],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="installation_type",
                    )
                )
            })
        )

    async def async_step_cloud_auth(self, user_input=None):
        """Authentification Cloud (pour mode Mixte et Cloud)."""
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
                    _LOGGER.info("Flipr : %d appareils trouvés sur le compte", len(self._cloud_devices))

                    if self._cloud_devices:
                        return await self.async_step_select_device()
                    else:
                        errors["base"] = "no_devices"
                        description_placeholders["error_info"] = (
                            "Aucun appareil Flipr trouvé sur ce compte."
                        )
                else:
                    errors["base"] = "invalid_auth"
            except FliprAuthError as e:
                errors["base"] = "invalid_auth_detailed"
                description_placeholders["error_info"] = str(e)
            except Exception as e:
                errors["base"] = "cannot_connect"
                description_placeholders["error_info"] = str(e)

        return self.async_show_form(
            step_id="cloud_auth",
            data_schema=vol.Schema({
                vol.Required("email"): str,
                vol.Required("password"): str,
            }),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_local_bt(self, user_input=None):
        """Installation locale en Bluetooth uniquement."""
        errors = {}

        if user_input is not None:
            selected = user_input["device"]
            if selected == "manual":
                self._from_manual_device = True
                return await self.async_step_manual_device()
            
            # Un appareil a été sélectionné dans la liste
            self._discovered_ble_address = selected
            
            # Extraire le serial
            chosen_serial = "Inconnu"
            if hasattr(self, "_discovered_bt_devices"):
                for dev in self._discovered_bt_devices:
                    if dev["address"] == selected:
                        chosen_serial = dev["serial"]
                        break
            
            self._selected_flipr_id = chosen_serial
            return await self.async_step_pool_details()

        # Scanner le cache Bluetooth de HA pour trouver des Flipr
        discovered_devices = []
        try:
            from .ble_client import scan_for_flipr
            discovered_devices = await scan_for_flipr(self.hass)
        except Exception as e:
            _LOGGER.warning("Erreur lors de la recherche des appareils Bluetooth local : %s", e)

        self._discovered_bt_devices = discovered_devices

        # Construire la liste des options
        device_options = {"manual": "Saisir le numéro de série & MAC manuellement"}
        for dev in discovered_devices:
            label = f"✅ {dev['name']} (S/N: {dev['serial']}, MAC: {dev['address']})"
            device_options[dev["address"]] = label

        return self.async_show_form(
            step_id="local_bt",
            data_schema=vol.Schema({
                vol.Required("device", default="manual" if not discovered_devices else list(device_options.keys())[1]): vol.In(device_options),
            }),
            errors=errors,
            description_placeholders={
                "nb_devices": str(len(discovered_devices)),
            }
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
            
            # Si c'est Mixte et que l'appareil choisi est un Flipr, on recherche le BLE
            if self._installation_type == "mix" and chosen and chosen.get("type") == "flipr":
                return await self.async_step_mix_ble()

            return await self.async_step_pool_details()

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

    async def async_step_mix_ble(self, user_input=None):
        """Recherche du Flipr sélectionné dans le cache Bluetooth HA."""
        _LOGGER.info("Flipr : Recherche du Flipr %s dans le cache Bluetooth HA...", self._selected_flipr_id)
        self._discovered_ble_address = ""
        try:
            from .ble_client import scan_for_flipr
            discovered = await scan_for_flipr(self.hass)
            for dev in discovered:
                dev_serial = dev.get("serial", "").upper()
                dev_name = dev.get("name", "").upper()
                target = self._selected_flipr_id.upper()
                
                # Check if serials match exactly, or if one is contained in the other, or if the name contains the target
                if (target and dev_serial and (target in dev_serial or dev_serial in target)) or target in dev_name:
                    self._discovered_ble_address = dev["address"]
                    _LOGGER.info("Flipr BLE : Appareil %s détecté localement à l'adresse %s (S/N: %s)", target, dev["address"], dev_serial)
                    break
        except Exception as e:
            _LOGGER.warning("Erreur lors du scan BLE en mode mixte : %s", e)

        if self._discovered_ble_address:
            # Trouvé ! On demande confirmation à l'utilisateur
            return await self.async_step_mix_ble_confirm()
        else:
            # Non trouvé ! On va sur le choix manuel/ignorer
            return await self.async_step_manual_mac_choice()

    async def async_step_mix_ble_confirm(self, user_input=None):
        """Confirmation de l'appareil BLE détecté automatiquement."""
        if user_input is not None:
            choice = user_input["choice"]
            if choice == "confirm":
                # L'adresse MAC est conservée
                return await self.async_step_pool_details()
            elif choice == "manual":
                return await self.async_step_manual_mac()
            elif choice == "ignore":
                self._discovered_ble_address = ""
                return await self.async_step_pool_details()

        return self.async_show_form(
            step_id="mix_ble_confirm",
            data_schema=vol.Schema({
                vol.Required("choice", default="confirm"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["confirm", "manual", "ignore"],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="mix_ble_confirm_choice",
                    )
                )
            }),
            description_placeholders={
                "mac": self._discovered_ble_address,
                "serial": self._selected_flipr_id,
            }
        )

    async def async_step_manual_mac_choice(self, user_input=None):
        """Menu intermédiaire : Choisir de saisir l'adresse MAC ou d'ignorer."""
        self._discovered_ble_address = ""
        if self._installation_type == "mix" or self._from_manual_device:
            return self.async_show_menu(
                step_id="manual_mac_choice",
                menu_options=["manual_mac", "pool_details"],
            )
        return self.async_show_menu(
            step_id="manual_mac_choice",
            menu_options=["manual_mac", "select_device"],
        )

    async def async_step_manual_mac(self, user_input=None):
        """Saisie manuelle de l'adresse MAC si le Flipr n'est pas détecté."""
        if user_input is not None:
            self._discovered_ble_address = user_input.get("ble_address", "").strip()
            if self._installation_type == "mix" or self._from_manual_device:
                return await self.async_step_pool_details()
            return await self.async_step_select_device()

        return self.async_show_form(
            step_id="manual_mac",
            data_schema=vol.Schema({
                vol.Required("ble_address"): str,
            }),
        )

    async def async_step_pool_details(self, user_input=None):
        """Étape 3 : Dimensions de la piscine et paramètres de chimie."""
        if user_input is not None:
            ble_address = self._discovered_ble_address
            ble_enabled = bool(ble_address) or (self._installation_type == "local")

            if self._installation_type == "local":
                title = f"Flipr (Local — {self._selected_flipr_id})"
            else:
                title = f"Flipr ({self._email} — {self._selected_flipr_id})"

            return self.async_create_entry(
                title=title,
                data={
                    "installation_type": self._installation_type,
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
        """Fallback : Saisie manuelle de l'identifiant (et de la MAC en mode local)."""
        if user_input is not None:
            flipr_id = user_input["flipr_id"]
            self._selected_flipr_id = flipr_id
            self._manual_user_input = user_input

            if self._installation_type == "local":
                self._discovered_ble_address = user_input["ble_address"].strip().upper()
                return await self.async_step_pool_details()

            # Lancement d'un scan BLE rapide (si Mixte / Cloud)
            self._discovered_ble_address = ""
            try:
                from .ble_client import scan_for_flipr
                discovered = await scan_for_flipr(self.hass)
                for dev in discovered:
                    if dev["serial"].upper() == flipr_id.upper():
                        self._discovered_ble_address = dev["address"]
                        break
            except Exception:
                pass

            if not self._discovered_ble_address:
                # Redirection vers manual_mac_choice si non détecté en BLE
                self._from_manual_device = True
                return await self.async_step_manual_mac_choice()

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

        # Affichage du formulaire
        schema_fields = {
            vol.Required("flipr_id"): str,
        }
        if self._installation_type == "local":
            schema_fields[vol.Required("ble_address")] = str

        schema_fields.update({
            vol.Optional("pool_length", default=0.0): vol.Coerce(float),
            vol.Optional("pool_width",  default=0.0): vol.Coerce(float),
            vol.Optional("pool_depth",  default=0.0): vol.Coerce(float),
            vol.Optional(CONF_TAC, default=DEFAULT_TAC): vol.Coerce(float),
            vol.Optional(CONF_TH,  default=DEFAULT_TH):  vol.Coerce(float),
            vol.Optional(CONF_CYA, default=DEFAULT_CYA): vol.Coerce(float),
            vol.Optional(CONF_TDS, default=DEFAULT_TDS): vol.Coerce(float),
        })

        return self.async_show_form(
            step_id="manual_device",
            data_schema=vol.Schema(schema_fields),
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
            self._ble_devices = await scan_for_flipr(self.hass)
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