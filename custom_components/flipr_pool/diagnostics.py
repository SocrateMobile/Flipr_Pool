"""Diagnostics support for Flipr."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "email",
    "password",
    "token",
    "refresh_token",
    "flipr_id",
    "mac",
    "ble_address",
    "lat",
    "lon",
    "Street",
    "ZipCode",
    "City",
    "Country"
}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    diagnostics_data = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": async_redact_data(coordinator.data, TO_REDACT),
    }

    return diagnostics_data
