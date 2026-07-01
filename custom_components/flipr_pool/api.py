"""Client API pour communiquer avec les serveurs Flipr (Cloud)."""

import logging
import aiohttp
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

from .const import (
    AUTH_URL,
    PLACES_URL,
    MODULES_URL,
    ALERTS_URL,
    THRESHOLDS_URL,
)

_LOGGER = logging.getLogger(__name__)


class FliprAuthError(Exception):
    """Exception levée en cas d'échec d'authentification."""
    pass


class FliprApiError(Exception):
    """Exception levée pour les erreurs générales de l'API Flipr."""
    pass


class FliprApiClient:
    """Client pour l'API REST Flipr."""

    def __init__(self, session: aiohttp.ClientSession, email: str | None = None, password: str | None = None) -> None:
        """Initialise le client."""
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None
        # Mécanisme de backoff exponentiel
        self._blocked_until: datetime | None = None
        self._retry_count: int = 0

    async def authenticate(self) -> str:
        """S'authentifie auprès du Cloud Flipr et retourne le token."""
        if not self._email or not self._password:
            raise FliprAuthError("Email ou mot de passe manquant pour l'authentification.")

        # Vérifier si l'IP est temporairement bloquée (429)
        if self._blocked_until and datetime.now(timezone.utc) < self._blocked_until:
            wait_minutes = int((self._blocked_until - datetime.now(timezone.utc)).total_seconds() / 60)
            raise FliprApiError(f"IP temporairement bloquée (429). Réessayez dans {wait_minutes} min.")

        auth_data = {
            "grant_type": "password",
            "username": self._email.strip(),
            "password": self._password.strip(),
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        try:
            async with self._session.post(AUTH_URL, data=auth_data, headers=headers) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    if json_data and json_data.get("access_token"):
                        self._token = json_data["access_token"]
                        self._blocked_until = None  # Reset block si succès
                        self._retry_count = 0
                        return self._token
                    raise FliprAuthError("Réponse d'authentification invalide (token manquant).")
                
                if resp.status == 429:
                    self._retry_count += 1
                    backoff_minutes = 60 * (2 ** (self._retry_count - 1))
                    self._blocked_until = datetime.now(timezone.utc) + timedelta(minutes=backoff_minutes)
                    raise FliprAuthError(f"Trop de requêtes vers le Cloud Flipr (Erreur 429). IP bloquée pour {backoff_minutes} min (Essai {self._retry_count}).")

                try:
                    err_data = await resp.json()
                    err_msg = err_data.get("error_description") or err_data.get("error") or f"HTTP {resp.status}"
                except Exception:
                    err_msg = await resp.text()
                
                raise FliprAuthError(f"Serveur Flipr : {err_msg[:150]}")
                
        except aiohttp.ClientError as e:
            raise FliprAuthError(f"Erreur de connexion réseau : {str(e)}")

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Effectue une requête authentifiée."""
        if not self._token:
            await self.authenticate()

        # Vérification 429 global
        if self._blocked_until and datetime.now(timezone.utc) < self._blocked_until:
            wait_minutes = int((self._blocked_until - datetime.now(timezone.utc)).total_seconds() / 60)
            raise FliprApiError(f"IP temporairement bloquée par Flipr. Attente {wait_minutes} min.")

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with self._session.request(method, url, headers=headers, **kwargs) as resp:
                if 200 <= resp.status < 300:
                    self._retry_count = 0
                    self._blocked_until = None
                    try:
                        return await resp.json()
                    except Exception:
                        return await resp.text()
                elif resp.status == 401:
                    # Token expiré, on réauthentifie une fois
                    _LOGGER.info("Token expiré, renouvellement...")
                    await self.authenticate()
                    headers["Authorization"] = f"Bearer {self._token}"
                    async with self._session.request(method, url, headers=headers, **kwargs) as retry_resp:
                        if 200 <= retry_resp.status < 300:
                            try:
                                return await retry_resp.json()
                            except Exception:
                                return await retry_resp.text()
                        retry_resp.raise_for_status()
                elif resp.status == 429:
                    # Backoff exponentiel (1h, 2h, 4h, 8h...)
                    self._retry_count += 1
                    backoff_minutes = 60 * (2 ** (self._retry_count - 1))
                    self._blocked_until = datetime.now(timezone.utc) + timedelta(minutes=backoff_minutes)
                    raise FliprApiError(f"Rate Limit (429) atteint. IP bloquée pour {backoff_minutes} min (Essai {self._retry_count}).")
                else:
                    resp.raise_for_status()
        except aiohttp.ClientError as e:
            raise FliprApiError(f"Erreur de requête HTTP: {e}")

    async def list_devices(self) -> list[dict[str, Any]]:
        """Liste tous les appareils (Flipr + Hub) du compte utilisateur."""
        devices = []

        try:
            places = await self._request("GET", PLACES_URL)
            if isinstance(places, list):
                for place in places:
                    # Fliprs
                    modules = place.get("Modules") or place.get("modules") or []
                    for mod in modules:
                        serial = mod.get("Serial") or mod.get("serial") or mod.get("Id") or ""
                        if serial:
                            devices.append({
                                "serial": str(serial),
                                "type": "flipr",
                                "label": f"Flipr {serial}",
                                "raw": mod,
                                "place_id": place.get("Id"),
                            })

                    # Hubs
                    hubs = place.get("Hubs") or place.get("hubs") or []
                    for hub in hubs:
                        hub_serial = hub.get("Serial") or hub.get("Id") or ""
                        if hub_serial:
                            devices.append({
                                "serial": str(hub_serial),
                                "type": "hub",
                                "label": f"Hub {hub_serial}",
                                "raw": hub,
                                "place_id": place.get("Id"),
                            })
        except Exception as e:
            _LOGGER.warning("Erreur récupération des places: %s", e)

        # Fallback via /modules si aucun appareil trouvé
        if not devices:
            try:
                modules = await self._request("GET", MODULES_URL)
                if isinstance(modules, list):
                    for mod in modules:
                        serial = mod.get("Serial") or mod.get("serial") or mod.get("Id") or ""
                        if serial:
                            devices.append({
                                "serial": str(serial),
                                "type": "flipr",
                                "label": f"Flipr {serial}",
                                "raw": mod,
                                "place_id": None,
                            })
            except Exception as e:
                _LOGGER.debug("Secours /modules échoué: %s", e)

        return devices

    async def get_pool_data(self, flipr_id: str, place_id: str | None = None, hub_id: str | None = None) -> dict[str, Any]:
        """Récupère l'ensemble des données cloud d'une piscine (mesures, alertes, hub)."""
        data = {
            "module_last_measure": None,
            "module_shortterm": None,
            "alerts": [],
            "thresholds": {},
            "hub_state": {},
            "place_id": place_id,
        }

        # 1. Dernière mesure du Flipr
        module_url = f"https://apis.goflipr.com/modules/{flipr_id}/survey/last"
        try:
            data["module_last_measure"] = await self._request("GET", module_url)
        except Exception as e:
            _LOGGER.warning("Impossible de lire la dernière mesure Cloud: %s", e)

        # 2. ShortTerm (pour l'état de l'eau)
        shortterm_url = f"https://apis.goflipr.com/modules/{flipr_id}/shortterm"
        try:
            data["module_shortterm"] = await self._request("GET", shortterm_url)
        except Exception:
            pass

        # Si place_id n'est pas fourni, on tente de le trouver via les places
        if not place_id:
            try:
                places = await self._request("GET", PLACES_URL)
                if isinstance(places, list):
                    for place in places:
                        modules = place.get("Modules") or place.get("modules") or []
                        if any(str(m.get("Id")) == flipr_id or str(m.get("Serial")) == flipr_id for m in modules):
                            place_id = place.get("Id")
                            data["place_id"] = place_id
                            # Si un hub est dans la même place, on le prend
                            hubs = place.get("Hubs") or place.get("hubs") or []
                            if hubs and not hub_id:
                                hub_id = str(hubs[0].get("Serial") or hubs[0].get("Id"))
                            break
            except Exception:
                pass

        # 3. État du Hub
        if hub_id:
            hub_url = f"https://apis.goflipr.com/hub/{hub_id}/state"
            try:
                hub_data = await self._request("GET", hub_url)
                data["hub_state"] = {
                    "Mode": hub_data.get("behavior"),
                    "Status": "on" if hub_data.get("stateEquipment") else "off"
                }
            except Exception as e:
                _LOGGER.debug("Erreur Hub State: %s", e)

        # 4. Alertes
        if place_id:
            alert_url = ALERTS_URL.format(api_base="https://apis.goflipr.com", place_id=place_id)
            try:
                data["alerts"] = await self._request("GET", alert_url)
            except Exception:
                pass

        # 5. Seuils
        threshold_url = THRESHOLDS_URL.format(api_base="https://apis.goflipr.com", flipr_id=flipr_id)
        try:
            data["thresholds"] = await self._request("GET", threshold_url)
        except Exception:
            pass
            
        data["hub_id"] = hub_id

        return data
