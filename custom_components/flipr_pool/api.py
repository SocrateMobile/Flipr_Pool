"""Client API asynchrone pour l'API REST Flipr (GoFlipr).

Spécification API :
  - Base URL         : https://apis.goflipr.com
  - Auth             : POST /OAuth2/token  (grant_type=password)
  - Liste modules    : GET  /modules
  - Données piscine  : GET  /modules/{poolId}/NewResume  → Current { Temperature, PH, ORP, BatteryLevel, ... }
  - Hub état         : GET  /hub/{hubId}/state
  - Hub mode         : PUT  /hub/{hubId}/mode/{mode}     (auto|manual|planning)
  - Hub pompe        : POST /hub/{hubId}/Manual/True|False  (nécessite mode=manual au préalable)
"""

import asyncio
import logging
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Any

from .const import (
    API_BASE_URL,
    AUTH_URL,
    PLACES_URL,
    MODULES_URL,
    ALERTS_URL,
    THRESHOLDS_URL,
)

_LOGGER = logging.getLogger(__name__)

# En-tête obligatoire sur TOUTES les requêtes vers apis.goflipr.com
_FLIPR_HEADERS = {"User-Agent": "X-Flipr"}


class FliprAuthError(Exception):
    """Échec d'authentification (identifiants invalides ou compte bloqué)."""


class FliprApiError(Exception):
    """Erreur générale de l'API Flipr (réseau, rate-limit, réponse invalide)."""


class FliprApiClient:
    """Client asynchrone pour l'API REST Flipr utilisant aiohttp."""
    
    _global_blocked_until: datetime | None = None
    _global_retry_count: int = 0
    _global_token: str | None = None

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = FliprApiClient._global_token
        self._cache: dict[str, tuple[datetime, Any]] = {}

    # ═══════════════════════════════════════════════════════════
    #  Authentification OAuth2
    # ═══════════════════════════════════════════════════════════

    async def authenticate(self) -> str:
        """Authentification OAuth2 password-grant. Retourne le access_token."""
        if not self._email or not self._password:
            raise FliprAuthError("Email ou mot de passe manquant.")

        if FliprApiClient._global_token:
            self._token = FliprApiClient._global_token
            return self._token

        self._check_rate_limit()

        auth_data = {
            "grant_type": "password",
            "username": self._email.strip(),
            "password": self._password.strip(),
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            **_FLIPR_HEADERS,
        }

        try:
            async with self._session.post(AUTH_URL, data=auth_data, headers=headers) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    token = json_data.get("access_token") if json_data else None
                    if not token:
                        raise FliprAuthError("Réponse d'authentification invalide (token absent).")
                    self._token = token
                    FliprApiClient._global_token = token
                    self._reset_rate_limit()
                    return self._token

                if resp.status == 429:
                    self._apply_rate_limit()
                    raise FliprAuthError(f"Rate-limit Flipr (429). Réessayez dans quelques minutes.")

                # Autre erreur (400, 401, 403, 500…)
                err_msg = await self._extract_error(resp)
                raise FliprAuthError(f"Serveur Flipr : {err_msg}")

        except aiohttp.ClientError as e:
            raise FliprAuthError(f"Erreur réseau : {e}")

    # ═══════════════════════════════════════════════════════════
    #  Requête authentifiée générique
    # ═══════════════════════════════════════════════════════════

    async def _cached_get(self, key: str, url: str, ttl_hours: int = 6) -> Any:
        """Effectue une requête GET avec un cache en mémoire pour éviter le rate-limit."""
        now = datetime.now(timezone.utc)
        if key in self._cache:
            entry_time, data = self._cache[key]
            if (now - entry_time).total_seconds() < ttl_hours * 3600:
                return data
        
        try:
            data = await self._request("GET", url)
            self._cache[key] = (now, data)
            return data
        except Exception as e:
            if key in self._cache:
                return self._cache[key][1]
            raise e

    async def _request(self, method: str, url: str, bypass_rate_limit: bool = False, **kwargs: Any) -> Any:
        """Effectue une requête authentifiée avec gestion du renouvellement de token."""
        if not self._token:
            await self.authenticate()

        if not bypass_rate_limit:
            self._check_rate_limit()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._token}"
        headers.update(_FLIPR_HEADERS)

        try:
            async with self._session.request(method, url, headers=headers, **kwargs) as resp:
                # ── Succès ──
                if 200 <= resp.status < 300:
                    self._reset_rate_limit()
                    return await self._parse_response(resp)

                # ── Token expiré → renouvellement unique ──
                if resp.status == 401:
                    _LOGGER.info("Token Flipr expiré — renouvellement en cours…")
                    FliprApiClient._global_token = None
                    self._token = None
                    await self.authenticate()
                    headers["Authorization"] = f"Bearer {self._token}"
                    async with self._session.request(method, url, headers=headers, **kwargs) as retry:
                        if 200 <= retry.status < 300:
                            self._reset_rate_limit()
                            return await self._parse_response(retry)
                        retry.raise_for_status()

                # ── Rate-limit ──
                if resp.status == 429:
                    self._apply_rate_limit()
                    raise FliprApiError(f"Rate-limit Flipr (429). Prochaine tentative dans {self._backoff_minutes()} min.")

                # ── Autre erreur ──
                resp.raise_for_status()

        except aiohttp.ClientError as e:
            raise FliprApiError(f"Erreur HTTP : {e}")

    # ═══════════════════════════════════════════════════════════
    #  Endpoints : Liste des appareils
    # ═══════════════════════════════════════════════════════════

    async def list_devices(self) -> list[dict[str, Any]]:
        """Liste tous les appareils (Flipr + Hub) du compte.

        Tente d'abord GET /place (plus riche), puis fallback sur GET /modules.
        """
        devices: list[dict[str, Any]] = []

        # ── Méthode principale : /place ──
        try:
            places = await self._request("GET", PLACES_URL)
            if isinstance(places, list):
                for place in places:
                    place_id = place.get("Id")

                    # Fliprs
                    for mod in (place.get("Modules") or place.get("modules") or []):
                        serial = str(mod.get("Serial") or mod.get("serial") or mod.get("Id") or "")
                        if serial:
                            devices.append({
                                "serial": serial,
                                "type": "flipr",
                                "label": f"Flipr {serial}",
                                "raw": mod,
                                "place_id": place_id,
                            })

                    # Hubs
                    for hub in (place.get("Hubs") or place.get("hubs") or []):
                        hub_serial = str(hub.get("Serial") or hub.get("Id") or "")
                        if hub_serial:
                            devices.append({
                                "serial": hub_serial,
                                "type": "hub",
                                "label": f"Hub {hub_serial}",
                                "raw": hub,
                                "place_id": place_id,
                            })
        except Exception as e:
            _LOGGER.warning("Erreur récupération /place : %s", e)

        # ── Fallback : GET /modules ──
        if not devices:
            try:
                modules = await self._request("GET", MODULES_URL)
                if isinstance(modules, list):
                    for mod in modules:
                        serial = str(mod.get("Serial") or mod.get("serial") or mod.get("Id") or "")
                        if serial:
                            devices.append({
                                "serial": serial,
                                "type": "flipr",
                                "label": f"Flipr {serial}",
                                "raw": mod,
                                "place_id": None,
                            })
            except Exception as e:
                _LOGGER.debug("Secours /modules échoué : %s", e)

        return devices

    # ═══════════════════════════════════════════════════════════
    #  Endpoint principal : Données piscine (NewResume)
    # ═══════════════════════════════════════════════════════════

    async def get_pool_data(
        self, flipr_id: str, place_id: str | None = None, hub_id: str | None = None
    ) -> dict[str, Any]:
        """Récupère toutes les données cloud d'une piscine.

        Flux :
          1. GET /modules/{id}/NewResume  (données capteur, nœud Current)
          2. GET /modules/{id}/shortterm  (météo, état de l'eau)
          3. Résolution place_id / hub_id & Récupération des modules
        """
        data: dict[str, Any] = {
            "module_last_measure": None,
            "module_shortterm": None,
            "alerts": [],
            "thresholds": {},
            "hub_state": {},
            "place_id": place_id,
            "hub_id": hub_id,
        }

        # ── 1. NewResume (endpoint principal) ──
        new_resume_url = f"{API_BASE_URL}/modules/{flipr_id}/NewResume"
        try:
            data["module_last_measure"] = await self._request("GET", new_resume_url)
        except Exception as e:
            _LOGGER.warning("Échec GET /NewResume : %s", e)

        # ── 1bis. Fallback survey/last (endpoint historique si NewResume vide ou invalide) ──
        m_check = data.get("module_last_measure")
        is_empty = False
        if not m_check or not isinstance(m_check, dict):
            is_empty = True
        else:
            cur = m_check.get("Current", m_check) if isinstance(m_check.get("Current"), dict) else m_check
            if (cur.get("Temperature") is None and cur.get("temperature") is None and cur.get("PH") is None and cur.get("ph") is None):
                is_empty = True

        if is_empty:
            survey_url = f"{API_BASE_URL}/modules/{flipr_id}/survey/last"
            try:
                survey_res = await self._request("GET", survey_url)
                if isinstance(survey_res, dict) and (
                    survey_res.get("Temperature") is not None or survey_res.get("temperature") is not None or survey_res.get("PH") is not None or survey_res.get("ph") is not None
                ):
                    data["module_last_measure"] = survey_res
                    _LOGGER.info("Flipr: Mesures récupérées avec succès via fallback /survey/last pour %s", flipr_id)
            except Exception as e:
                _LOGGER.debug("Échec fallback GET /survey/last : %s", e)

        # ── 2. ShortTerm (météo) - en cache 6h ──
        shortterm_url = f"{API_BASE_URL}/modules/{flipr_id}/shortterm"
        try:
            data["module_shortterm"] = await self._cached_get(f"shortterm_{flipr_id}", shortterm_url, ttl_hours=6)
        except Exception:
            pass

        # ── 3. Résolution place_id / hub_id & Récupération des modules ──
        try:
            modules_list = await self._cached_get("modules", MODULES_URL, ttl_hours=24)
            if isinstance(modules_list, list):
                data["raw_modules"] = modules_list
                if not hub_id:
                    for mod in modules_list:
                        discovered_hub_id = str(mod.get("Serial") or mod.get("Id") or "")
                        if not discovered_hub_id or discovered_hub_id == flipr_id:
                            continue  # Ne pas tester le Flipr lui-même
                        
                        # Test de l'endpoint d'état pour confirmer si c'est un Hub
                        try:
                            state_url = f"{API_BASE_URL}/hub/{discovered_hub_id}/state"
                            hub_state = await self._request("GET", state_url)
                            if (
                                isinstance(hub_state, dict) 
                                and hub_state 
                                and hub_state.get("ErrorCode") != "Forbidden" 
                                and "is not a HUB" not in str(hub_state.get("ErrorMessage", ""))
                                and ("behavior" in hub_state or "stateEquipment" in hub_state)
                            ):
                                hub_id = discovered_hub_id
                                data["hub_id"] = hub_id
                                data["hub_state"] = hub_state
                                _LOGGER.info("Flipr Hub confirmé via API: %s", hub_id)
                                break
                            else:
                                _LOGGER.debug("Module %s n'est pas un Hub: %s", discovered_hub_id, hub_state)
                        except Exception as e:
                            _LOGGER.warning("Erreur test Hub pour %s: %s", discovered_hub_id, e)
        except Exception as e:
            _LOGGER.debug("Erreur interrogation /modules : %s", e)

        if not place_id or not hub_id:
            try:
                places = await self._cached_get("places", PLACES_URL, ttl_hours=24)
                if isinstance(places, list):
                    for place in places:
                        modules = place.get("Modules") or place.get("modules") or []
                        match = any(
                            str(m.get("Id")) == flipr_id or str(m.get("Serial")) == flipr_id
                            for m in modules
                        )
                        if match:
                            if not place_id:
                                place_id = place.get("Id")
                                data["place_id"] = place_id
                            if not hub_id:
                                hubs = place.get("Hubs") or place.get("hubs") or []
                                if hubs:
                                    hub_id = str(hubs[0].get("Serial") or hubs[0].get("Id"))
                                    data["hub_id"] = hub_id
                            break
            except Exception:
                pass

        # ── 4. Hub State : GET /hub/{hubId}/state ──
        if hub_id:
            try:
                hub_url = f"{API_BASE_URL}/hub/{hub_id}/state"
                hub_resp = await self._request("GET", hub_url)
                if isinstance(hub_resp, dict) and not hub_resp.get("ErrorCode"):
                    # Passer les données brutes pour que le coordinateur les parse
                    data["hub_state"] = hub_resp
                    _LOGGER.info("Flipr Hub %s state récupéré: %s", hub_id, hub_resp)
                elif isinstance(hub_resp, dict) and hub_resp.get("ErrorCode"):
                    _LOGGER.debug("Flipr Hub %s a retourné : %s", hub_id, hub_resp.get("ErrorMessage"))
            except Exception as e:
                _LOGGER.debug("Échec GET hub state pour %s : %s", hub_id, e)

        # ── 5. Alertes - en cache 4h ──
        if place_id:
            alert_url = ALERTS_URL.format(api_base=API_BASE_URL, place_id=place_id)
            try:
                data["alerts"] = await self._cached_get(f"alerts_{place_id}", alert_url, ttl_hours=4)
            except Exception:
                pass

        # ── 6. Seuils - en cache 24h ──
        threshold_url = THRESHOLDS_URL.format(api_base=API_BASE_URL, flipr_id=flipr_id)
        try:
            data["thresholds"] = await self._cached_get(f"thresholds_{flipr_id}", threshold_url, ttl_hours=24)
        except Exception:
            pass

        return data

    # ═══════════════════════════════════════════════════════════
    #  Endpoints Hub : Contrôle de la pompe
    # ═══════════════════════════════════════════════════════════

    async def set_hub_mode(self, hub_id: str, mode: str) -> None:
        """Change le mode du Hub : PUT /hub/{hubId}/mode/{mode}

        Modes valides : auto, manual, planning
        """
        if mode not in ("auto", "manual", "planning"):
            raise ValueError(f"Mode Hub invalide : {mode!r}. Attendu : auto, manual, planning.")

        url = f"{API_BASE_URL}/hub/{hub_id}/mode/{mode}"
        await self._request("PUT", url, bypass_rate_limit=True)
        _LOGGER.info("Hub %s : mode changé en '%s'", hub_id, mode)

    async def set_hub_pump(self, hub_id: str, state: bool) -> None:
        """Allume/éteint la pompe du Hub en mode manuel."""
        state_str = "True" if state else "False"
        url = f"{API_BASE_URL}/hub/{hub_id}/Manual/{state_str}"
        await self._request("POST", url, bypass_rate_limit=True)
        _LOGGER.info("Hub %s : pompe → %s via %s", hub_id, "ON" if state else "OFF", url)

    async def get_hub_state(self, hub_id: str) -> dict[str, Any]:
        """Récupère l'état actuel du Hub : GET /hub/{hubId}/state"""
        url = f"{API_BASE_URL}/hub/{hub_id}/state"
        resp = await self._request("GET", url)
        if not isinstance(resp, dict):
            return {}

        behavior = resp.get("behavior", "auto")
        if isinstance(behavior, str):
            mode_str = behavior.lower()
        else:
            mode_str = {1: "manual", 2: "planning"}.get(behavior, "auto")

        return {
            "state": bool(resp.get("stateEquipment", False)),
            "mode": mode_str,
            "planning": resp.get("planning"),
        }

    # ═══════════════════════════════════════════════════════════
    #  Helpers internes
    # ═══════════════════════════════════════════════════════════

    def _check_rate_limit(self) -> None:
        """Lève une exception si on est en période de backoff 429."""
        if FliprApiClient._global_blocked_until and datetime.now(timezone.utc) < FliprApiClient._global_blocked_until:
            remaining = int((FliprApiClient._global_blocked_until - datetime.now(timezone.utc)).total_seconds())
            raise FliprApiError(f"Rate-limit actif. Réessayez dans {remaining}s.")

    def _apply_rate_limit(self) -> None:
        """Active le backoff : 60s, puis 120s, max 300s."""
        FliprApiClient._global_retry_count += 1
        seconds = min(300, 60 * (2 ** min(3, FliprApiClient._global_retry_count - 1)))
        FliprApiClient._global_blocked_until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        _LOGGER.warning("Rate-limit Flipr (429). Pause de %ds (tentative %d).", seconds, FliprApiClient._global_retry_count)

    def reset_rate_limit(self) -> None:
        """Réinitialise publiquement le compteur de rate-limit (ex: lors d'un diagnostic)."""
        FliprApiClient._global_blocked_until = None
        FliprApiClient._global_retry_count = 0

    def _reset_rate_limit(self) -> None:
        """Réinitialise le compteur de backoff après un succès."""
        self.reset_rate_limit()

    def _backoff_minutes(self) -> int:
        """Retourne le nombre de minutes du backoff actuel."""
        return max(1, int((60 * (2 ** min(3, max(0, FliprApiClient._global_retry_count - 1)))) / 60))

    @staticmethod
    async def _extract_error(resp: aiohttp.ClientResponse) -> str:
        """Extrait un message d'erreur lisible depuis la réponse HTTP."""
        try:
            err_data = await resp.json()
            return str(
                err_data.get("error_description")
                or err_data.get("error")
                or f"HTTP {resp.status}"
            )[:150]
        except Exception:
            text = await resp.text()
            return text[:150] if text else f"HTTP {resp.status}"

    @staticmethod
    async def _parse_response(resp: aiohttp.ClientResponse) -> Any:
        """Parse la réponse : JSON si possible, texte sinon."""
        try:
            return await resp.json()
        except Exception:
            return await resp.text()
