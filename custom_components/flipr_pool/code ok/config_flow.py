import logging
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)


class FliprConfigFlow(config_entries.ConfigFlow, domain="flipr_pool"):
    """Gestion du formulaire de configuration pour Flipr Pool Control."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Retourne le flow d'options (dimensions piscine)."""
        return FliprOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            auth_url = "https://apis.goflipr.com/OAuth2/token"
            auth_data = {
                "grant_type": "password",
                "username": user_input["email"],
                "password": user_input["password"]
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(auth_url, data=auth_data, headers=headers) as resp:
                        if resp.status == 200:
                            return self.async_create_entry(
                                title=f"Flipr ({user_input['email']})",
                                data=user_input
                            )
                        response_text = await resp.text()
                        errors["base"] = "invalid_auth_detailed"
                        description_placeholders["error_info"] = f"Code {resp.status}: {response_text[:100]}"

            except Exception as e:
                errors["base"] = "cannot_connect"
                description_placeholders["error_info"] = str(e)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("email"): str,
                vol.Required("password"): str,
                vol.Required("flipr_id"): str,
                vol.Optional("pool_length", default=0.0): vol.Coerce(float),
                vol.Optional("pool_width",  default=0.0): vol.Coerce(float),
                vol.Optional("pool_depth",  default=0.0): vol.Coerce(float),
            }),
            errors=errors,
            description_placeholders=description_placeholders
        )


class FliprOptionsFlow(config_entries.OptionsFlow):
    """Options flow : dimensions de la piscine et paramètres de traitement.
    
    Note: self.config_entry est fourni automatiquement par HA (2024+).
    """

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # On récupère les valeurs actuelles (soit dans options, soit dans data)
        options = self.config_entry.options
        data = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "pool_length",
                    default=options.get("pool_length", data.get("pool_length", 0.0))
                ): vol.Coerce(float),
                vol.Optional(
                    "pool_width",
                    default=options.get("pool_width", data.get("pool_width", 0.0))
                ): vol.Coerce(float),
                vol.Optional(
                    "pool_depth",
                    default=options.get("pool_depth", data.get("pool_depth", 0.0))
                ): vol.Coerce(float),
            }),
        )