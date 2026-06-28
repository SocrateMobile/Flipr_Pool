"""Client Bluetooth Low Energy (BLE) pour Flipr Pool.

Gère la connexion, la lecture et le décodage des trames binaires
envoyées par le capteur Flipr via Bluetooth.

Supporte :
- Flipr classique : notification GATT asynchrone
- Flipr Start Max  : connexion maintenue 35s puis lecture directe
"""

import asyncio
import logging
import struct
from datetime import datetime, timezone

from .const import (
    BLE_SERVICE_UUID,
    BLE_CHAR_NOTIFY,
    BLE_CHAR_READ,
    BLE_CONNECTION_TIMEOUT,
    BLE_STARTMAX_WAIT,
    BLE_NAME_PREFIXES,
)

_LOGGER = logging.getLogger(__name__)


class FliprBleError(Exception):
    """Erreur de communication BLE avec le Flipr."""


def _decode_flipr_frame(raw: bytes) -> dict:
    """Décode une trame binaire Flipr (20 octets) en valeurs de mesure.

    Format de la trame (little-endian) :
    Offset  Taille  Champ
    0       2       pH brut (uint16, ÷ 100)
    2       2       Redox / ORP brut (int16, mV)
    4       2       Température brute (int16, ÷ 100, °C)
    6       2       Conductivité brute (uint16, µS/cm)
    8       2       Batterie brute (uint16, ÷ 100, fraction 0-1)
    10      2       Chlore estimé brut (uint16, ÷ 1000, mg/L)
    12      4       Timestamp (uint32, epoch UTC)
    16      2       Flags (uint16, bit 0 = Start Max)
    18      2       Réservé
    """
    if len(raw) < 16:
        raise FliprBleError(f"Trame trop courte: {len(raw)} octets (minimum 16)")

    try:
        ph_raw, redox_raw, temp_raw, cond_raw, batt_raw, cl_raw = struct.unpack_from(
            "<HhHHHH", raw, 0
        )
    except struct.error as e:
        raise FliprBleError(f"Erreur décodage trame: {e}") from e

    ph = round(ph_raw / 100.0, 2) if ph_raw > 0 else None
    redox = redox_raw if redox_raw != 0 else None
    temperature = round(temp_raw / 100.0, 1) if temp_raw > 0 else None
    conductivity = cond_raw if cond_raw > 0 else None
    battery = round(min(batt_raw / 100.0, 1.0) * 100, 1) if batt_raw > 0 else None
    chlorine = round(cl_raw / 1000.0, 3) if cl_raw > 0 else None

    # Timestamp si présent (octets 12-15)
    ts = None
    if len(raw) >= 16:
        try:
            ts_raw = struct.unpack_from("<I", raw, 12)[0]
            if ts_raw > 1_000_000_000:  # Timestamp raisonnable (après 2001)
                ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
        except (struct.error, ValueError, OSError):
            pass

    # Flags si présent (octets 16-17)
    is_start_max = False
    if len(raw) >= 18:
        try:
            flags = struct.unpack_from("<H", raw, 16)[0]
            is_start_max = bool(flags & 0x01)
        except struct.error:
            pass

    return {
        "temperature": temperature,
        "ph": ph,
        "redox": redox,
        "conductivity": conductivity,
        "battery": battery,
        "chlorine": chlorine,
        "last_update_ble": ts or datetime.now(timezone.utc),
        "is_start_max": is_start_max,
    }


def _detect_flipr_model(name: str, service_uuids: list[str] | None = None) -> str:
    """Détecte le modèle du Flipr à partir de son nom BLE et de ses services.

    Heuristique :
    - Noms commençant par "F30" → Start Max (3ème génération)
    - Noms commençant par "F2B" → Start (peut être Start Max selon le firmware)
    - Noms commençant par "Flipr" → Classique (1ère/2ème génération)
    - Si le service GATT de lecture directe (BLE_CHAR_READ) est annoncé → Start Max
    """
    name_upper = name.upper()
    if name_upper.startswith("F30"):
        return "Start Max"
    if name_upper.startswith("F2B"):
        # F2B peut être Start ou Start Max — on suppose Start Max par sécurité
        return "Start Max"
    return "Classique"


def _extract_serial_from_name(name: str) -> str:
    """Extrait le numéro de série du Flipr depuis son nom BLE.

    Exemples :
    - "Flipr-AB1234"  → "AB1234"
    - "F30_CD5678"    → "CD5678"
    - "F2B-EF9012"    → "EF9012"
    """
    for sep in ("-", "_", " "):
        if sep in name:
            parts = name.split(sep, 1)
            if len(parts) == 2:
                return parts[1].strip()
    # Retirer le préfixe connu
    for prefix in BLE_NAME_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):].strip("-_ ")
    return name


async def scan_for_flipr(hass, timeout: float = 15.0) -> list[dict]:
    """Interroge le cache Bluetooth natif de Home Assistant pour trouver les Flipr à portée.

    Utilise async_discovered_service_info() de HA au lieu d'un scan brut BleakScanner,
    car dans HA le contrôleur Bluetooth est géré par le composant bluetooth intégré.
    Un scan brut BleakScanner.discover() confliquerait avec le contrôleur.

    Retourne une liste de dicts :
    [
        {
            "name": "Flipr-AB1234",
            "address": "AA:BB:CC:DD:EE:FF",
            "rssi": -60,
            "model": "Classique" | "Start Max",
            "serial": "AB1234",
        }
    ]
    """
    devices = []
    try:
        from homeassistant.components.bluetooth import async_discovered_service_info

        for info in async_discovered_service_info(hass, connectable=False):
            name = info.name or ""
            name_upper = name.upper()

            # Récupérer les UUIDs de service annoncés
            service_uuids = [u.lower() for u in (info.service_uuids or [])]

            # Un appareil est un Flipr s'il a le bon préfixe de nom
            # OU s'il annonce l'UUID de service Flipr principal (fee8)
            is_flipr = (
                name_upper.startswith(("FLIPR", "F2", "F3"))
                or BLE_SERVICE_UUID in service_uuids
                or "fee8" in service_uuids
            )

            if not is_flipr:
                continue

            # Si le nom est vide mais que c'est un Flipr (détecté par UUID), on donne un nom par défaut
            if not name:
                name = f"Flipr-{info.address.replace(':', '')[-6:].upper()}"

            model = _detect_flipr_model(name, service_uuids)
            serial = _extract_serial_from_name(name)

            rssi = info.rssi

            device_info = {
                "name": name,
                "address": info.address.upper(),
                "rssi": rssi,
                "model": model,
                "serial": serial,
            }
            devices.append(device_info)
            _LOGGER.info(
                "Flipr BLE détecté (cache HA): %s (%s) Modèle=%s Série=%s RSSI=%s",
                name, info.address, model, serial, rssi
            )
    except ImportError:
        _LOGGER.warning("homeassistant.components.bluetooth non disponible — BLE scan désactivé")
    except Exception as e:
        _LOGGER.warning("Erreur lors de la lecture du cache BLE HA: %s", e)

    return devices


async def read_flipr_ble(
    address: str,
    hass=None,
) -> dict:
    """Connecte au Flipr via BLE, lit les mesures et retourne un dict normalisé.

    Gère automatiquement le modèle Start Max (attente 35s avant lecture).

    Args:
        address: Adresse MAC du Flipr BLE (ex: "AA:BB:CC:DD:EE:FF")
        hass: Instance HomeAssistant (pour bleak-retry-connector si disponible)

    Returns:
        dict avec les clés: temperature, ph, redox, conductivity, battery, chlorine,
                           last_update_ble, ble_rssi, ble_status
    """
    try:
        from bleak import BleakClient
    except ImportError:
        raise FliprBleError("bleak n'est pas installé")

    # Essayer d'utiliser bleak-retry-connector (recommandé pour HA sur RPi)
    establish_fn = None
    try:
        from bleak_retry_connector import establish_connection
        establish_fn = establish_connection
    except ImportError:
        _LOGGER.debug("bleak-retry-connector non disponible, utilisation de BleakClient direct")

    ble_lock = asyncio.Lock()
    result = {
        "ble_status": "connecting",
        "ble_rssi": None,
    }

    async with ble_lock:
        client = None
        try:
            # Connexion
            if establish_fn and hass:
                # Utiliser la méthode HA-optimisée (retry automatique)
                from homeassistant.components.bluetooth import async_ble_device_from_address
                device = async_ble_device_from_address(hass, address, connectable=True)
                if not device:
                    from bleak.backends.device import BLEDevice
                    device = BLEDevice(address, name=None, details=None, rssi=0)
                client = await asyncio.wait_for(
                    establish_fn(BleakClient, device, max_attempts=3),
                    timeout=BLE_CONNECTION_TIMEOUT,
                )
            else:
                client = BleakClient(address)
                await asyncio.wait_for(
                    client.connect(),
                    timeout=BLE_CONNECTION_TIMEOUT,
                )

            if not client.is_connected:
                raise FliprBleError(f"Impossible de se connecter au Flipr {address}")

            result["ble_status"] = "reading"
            _LOGGER.debug("Flipr BLE connecté: %s", address)

            # Tenter de lire le RSSI
            try:
                if hasattr(client, "rssi"):
                    result["ble_rssi"] = client.rssi
            except Exception:
                pass

            # ── Stratégie de lecture ────────────────────────────
            raw_data = None

            # Stratégie 1 : Notification (Flipr classique)
            notification_event = asyncio.Event()
            notification_data = bytearray()

            def _notification_handler(sender, data: bytearray):
                nonlocal notification_data
                notification_data.extend(data)
                notification_event.set()

            try:
                await client.start_notify(BLE_CHAR_NOTIFY, _notification_handler)
                # Attendre la notification (max 15s pour le classique)
                try:
                    await asyncio.wait_for(notification_event.wait(), timeout=15.0)
                    raw_data = bytes(notification_data)
                    _LOGGER.debug("Flipr BLE: données reçues par notification (%d octets)", len(raw_data))
                except asyncio.TimeoutError:
                    _LOGGER.debug("Flipr BLE: pas de notification en 15s — tentative Start Max")
                finally:
                    try:
                        await client.stop_notify(BLE_CHAR_NOTIFY)
                    except Exception:
                        pass
            except Exception as e:
                _LOGGER.debug("Flipr BLE: notification non supportée (%s) — tentative Start Max", e)

            # Stratégie 2 : Lecture directe après attente (Start Max)
            if raw_data is None:
                _LOGGER.info("Flipr BLE: mode Start Max — attente de %ds pour la mesure", BLE_STARTMAX_WAIT)
                result["ble_status"] = "measuring"
                await asyncio.sleep(BLE_STARTMAX_WAIT)

                try:
                    raw_data = await client.read_gatt_char(BLE_CHAR_READ)
                    _LOGGER.debug("Flipr BLE: données lues en mode Start Max (%d octets)", len(raw_data))
                except Exception as e:
                    raise FliprBleError(f"Lecture Start Max échouée: {e}") from e

            if raw_data is None or len(raw_data) < 12:
                raise FliprBleError("Aucune donnée BLE reçue du Flipr")

            # Décodage
            decoded = _decode_flipr_frame(raw_data)
            decoded.update(result)
            decoded["ble_status"] = "ok"
            return decoded

        except asyncio.TimeoutError:
            result["ble_status"] = "timeout"
            raise FliprBleError(f"Timeout de connexion BLE au Flipr {address}")
        except FliprBleError:
            result["ble_status"] = "error"
            raise
        except Exception as e:
            result["ble_status"] = "error"
            raise FliprBleError(f"Erreur BLE inattendue: {e}") from e
        finally:
            if client and client.is_connected:
                try:
                    await client.disconnect()
                except Exception:
                    pass
