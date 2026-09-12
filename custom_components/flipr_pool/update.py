"""Update platform for Flipr Pool Control integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import logging
import os
import re
import shutil
import tempfile
import zipfile
from typing import Any

import aiohttp

from homeassistant.components import frontend
from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

GITHUB_REPO = "SocrateMobile/flipr_pool"
GITHUB_LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
UPDATE_CHECK_INTERVAL = timedelta(hours=4)


def parse_semver(version_str: str) -> tuple[int, ...]:
    """Parse semver string into a comparable tuple of integers."""
    if not version_str:
        return (0, 0, 0)
    clean = re.sub(r"^[vV]", "", str(version_str).strip())
    parts: list[int] = []
    for segment in clean.split("."):
        digits = re.match(r"^\d+", segment)
        parts.append(int(digits.group(0)) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def get_installed_version() -> str:
    """Read version directly from manifest.json with fallback."""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    try:
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return str(data.get("version", "5.7.3"))
    except Exception as err:
        _LOGGER.debug("Could not read manifest.json version for flipr_pool: %s", err)
    return "5.7.3"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the update platform for Flipr Pool Control."""
    installed_ver = get_installed_version()
    update_entity = FliprPoolUpdateEntity(
        hass=hass,
        entry=entry,
        installed_version=installed_ver,
    )

    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})["update_entity"] = update_entity
    async_add_entities([update_entity], True)


class FliprPoolUpdateEntity(UpdateEntity):
    """Representation of the Flipr Pool Control update entity."""

    _attr_has_entity_name = True
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.RELEASE_NOTES
        | UpdateEntityFeature.PROGRESS
    )

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        installed_version: str,
    ) -> None:
        """Initialize the update entity."""
        self.hass = hass
        self.entry = entry
        self._attr_name = "Mise à jour"
        self._attr_unique_id = f"flipr_pool_update_{entry.entry_id}"
        self._attr_title = "Flipr Pool Control"

        self._attr_installed_version = installed_version
        self._attr_latest_version = installed_version
        self._attr_release_summary: str | None = None
        self._attr_release_url: str | None = None
        self._release_body: str | None = None
        self._zip_download_url: str | None = None

        self._attr_in_progress = False
        self._attr_update_percentage: int | None = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Flipr Pool Control",
            manufacturer="SocrateMobile",
            model="Flipr Smart Pool Monitor",
            sw_version=installed_version,
        )

        self._unsub_interval = None

    async def async_added_to_hass(self) -> None:
        """Register periodic update checks and initial check."""
        await super().async_added_to_hass()
        self._unsub_interval = async_track_time_interval(
            self.hass, self._async_periodic_check, UPDATE_CHECK_INTERVAL
        )
        self.hass.async_create_task(self.async_update())

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        await super().async_will_remove_from_hass()

    async def _async_periodic_check(self, _now: Any = None) -> None:
        """Periodic check called by timer."""
        await self.async_update()

    async def async_update(self) -> None:
        """Check GitHub for the latest release."""
        try:
            session = async_get_clientsession(self.hass)
            headers = {
                "User-Agent": "HomeAssistant-FliprPool",
                "Accept": "application/vnd.github.v3+json",
            }
            async with session.get(
                GITHUB_LATEST_RELEASE_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "GitHub release check returned HTTP %s for %s",
                        resp.status,
                        GITHUB_REPO,
                    )
                    return

                data = await resp.json()
                tag = data.get("tag_name", "").strip()
                clean_tag = re.sub(r"^[vV]", "", tag)
                if not clean_tag:
                    return

                self._attr_installed_version = get_installed_version()
                self._attr_latest_version = clean_tag
                self._attr_release_summary = data.get("name") or f"Version {clean_tag}"
                self._release_body = data.get("body") or ""
                self._attr_release_url = data.get("html_url")
                self._zip_download_url = (
                    f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.zip"
                )

                has_update = parse_semver(clean_tag) > parse_semver(self._attr_installed_version)

                # Update left sidebar panel badge & icon
                self._update_sidebar_panel(has_update)

                self.async_write_ha_state()
                _LOGGER.info(
                    "Flipr Pool Control update check: installed=%s, latest=%s, update_available=%s",
                    self._attr_installed_version,
                    clean_tag,
                    has_update,
                )
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout checking GitHub releases for Flipr Pool Control")
        except Exception as err:
            _LOGGER.warning("Error checking GitHub releases for Flipr Pool Control: %s", err)

    def _update_sidebar_panel(self, update_available: bool) -> None:
        """Update the Home Assistant left sidebar panel badge/title if registered."""
        try:
            title = "Flipr Pool Control 🔴" if update_available else "Flipr Pool Control"
            icon = "mdi:shield-alert" if update_available else "mdi:pool"
            frontend.async_register_built_in_panel(
                self.hass,
                component_name="custom",
                sidebar_title=title,
                sidebar_icon=icon,
                frontend_url_path="flipr_pool",
                config={},
                require_admin=False,
                update=True,
            )
        except Exception as err:
            _LOGGER.debug("Could not update Flipr Pool sidebar panel registration: %s", err)

    async def async_release_notes(self) -> str | None:
        """Return release notes in markdown."""
        return self._release_body

    async def async_install(
        self, version: str | None = None, backup: bool = True, **kwargs: Any
    ) -> None:
        """Download and install update, then restart Home Assistant."""
        if not self._zip_download_url:
            await self.async_update()

        if not self._zip_download_url:
            raise HomeAssistantError("URL de téléchargement GitHub introuvable.")

        _LOGGER.info(
            "Starting Flipr Pool Control update to version %s (download: %s)",
            self._attr_latest_version,
            self._zip_download_url,
        )

        self._attr_in_progress = True
        self._attr_update_percentage = 10
        self.async_write_ha_state()

        temp_dir = tempfile.mkdtemp(prefix="flipr_pool_update_")
        zip_path = os.path.join(temp_dir, "release.zip")

        try:
            session = async_get_clientsession(self.hass)
            headers = {"User-Agent": "HomeAssistant-FliprPool"}
            async with session.get(self._zip_download_url, headers=headers, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Échec téléchargement release Flipr (HTTP {resp.status})")
                with open(zip_path, "wb") as f:
                    while True:
                        chunk = await resp.content.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)

            self._attr_update_percentage = 40
            self.async_write_ha_state()

            def _do_extract_and_copy() -> None:
                extract_path = os.path.join(temp_dir, "extracted")
                os.makedirs(extract_path, exist_ok=True)
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(extract_path)

                source_component_dir = None
                for root, _dirs, _files in os.walk(extract_path):
                    if os.path.exists(os.path.join(root, "__init__.py")) and os.path.exists(
                        os.path.join(root, "manifest.json")
                    ):
                        try:
                            with open(os.path.join(root, "manifest.json"), "r", encoding="utf-8") as mf:
                                mdata = json.load(mf)
                                if mdata.get("domain") == DOMAIN:
                                    source_component_dir = root
                                    break
                        except Exception:
                            if os.path.basename(root) in (DOMAIN, "flipr_pool", "Flipr-Pool"):
                                source_component_dir = root
                                break

                if not source_component_dir:
                    raise RuntimeError("L'archive ne contient pas de composant flipr_pool valide.")

                target_dir = os.path.abspath(os.path.dirname(__file__))

                if backup:
                    backup_dir = os.path.join(tempfile.gettempdir(), f"{DOMAIN}_last_backup")
                    if os.path.exists(backup_dir):
                        shutil.rmtree(backup_dir, ignore_errors=True)
                    shutil.copytree(target_dir, backup_dir, dirs_exist_ok=True)
                    _LOGGER.info("Flipr Pool Control safety backup saved to %s", backup_dir)

                pycache_dir = os.path.join(target_dir, "__pycache__")
                if os.path.exists(pycache_dir):
                    shutil.rmtree(pycache_dir, ignore_errors=True)

                shutil.copytree(source_component_dir, target_dir, dirs_exist_ok=True)
                _LOGGER.info("Flipr Pool Control files successfully updated in %s", target_dir)

            await self.hass.async_add_executor_job(_do_extract_and_copy)

            self._attr_update_percentage = 90
            self.async_write_ha_state()

            self._update_sidebar_panel(False)
            self._attr_installed_version = self._attr_latest_version
            self._attr_update_percentage = 100
            self._attr_in_progress = False
            self.async_write_ha_state()

            _LOGGER.info("Flipr Pool Control update complete! Restarting Home Assistant...")
            await asyncio.sleep(1.5)
            await self.hass.services.async_call("homeassistant", "restart")

        except Exception as err:
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()
            _LOGGER.error("Flipr Pool Control auto-update failed: %s", err, exc_info=True)
            raise HomeAssistantError(f"Échec de la mise à jour : {err}") from err
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
