"""Constants for the Flipr Pool integration."""

DOMAIN = "flipr_pool"
VERSION = "3.3.4"
API_BASE_URL = "https://apis.goflipr.com"

# ── Configuration de traitement ────────────────────────────
# Ces valeurs servent de base pour les calculs de doses
PH_TARGET          = 7.4     # pH idéal cible
PH_MINUS_DOSE      = 100.0   # g par m³ par unité pH (granulés bisulfate)
PH_PLUS_DOSE       = 150.0   # g par m³ par unité pH (granulés carbonate)

CHLORINE_TARGET    = 2.0     # mg/L idéal
CHLORINE_SHOCK_TARGET = 5.0  # mg/L cible pour traitement choc
CHLORINE_DOSE      = 1.5     # g de produit par m³ par mg/L (chlore choc 70%)

PUMP_MIN_HOURS     = 4.0
PUMP_MAX_HOURS     = 24.0

# ── Paramètres de chimie de l'eau (LSI & Chlore Actif) ────
CONF_TAC           = "tac"     # Alcalinité totale (TAC) en ppm/mg/L
CONF_TH            = "th"      # Titre Hydrotimétrique / dureté en ppm/mg/L
CONF_CYA           = "cya"     # Acide cyanurique / Stabilisant en ppm/mg/L
CONF_TDS           = "tds"     # Total Dissolved Solids / Sels dissous en ppm/mg/L

DEFAULT_TAC        = 100.0     # ppm - alcalinité moyenne de l'eau douce
DEFAULT_TH         = 200.0     # ppm - dureté moyenne de l'eau douce
DEFAULT_CYA        = 30.0      # ppm - stabilisant faible (eau non stabilisée)
DEFAULT_TDS        = 1000.0    # ppm - standard eau douce

# ── Endpoints API ──────────────────────────────────────────
AUTH_URL = "https://apis.goflipr.com/OAuth2/token"
SURVEY_URL = "{api_base}/modules/{flipr_id}/survey/last"
SHORTTERM_URL = "{api_base}/modules/{flipr_id}/shortterm"
HUB_URL = f"{API_BASE_URL}/hub/{{flipr_id}}"
PLACES_URL = f"{API_BASE_URL}/place"
ALERTS_URL = "{api_base}/place/{place_id}/allAlerts"
THRESHOLDS_URL = "{api_base}/modules/{flipr_id}/Thresholds"
MODULES_URL = f"{API_BASE_URL}/modules"

# ── BLE (Bluetooth Low Energy) ─────────────────────────────
# Préfixes du nom BLE annoncé par les Flipr
BLE_NAME_PREFIXES = ("Flipr", "F2B", "F30")

# UUID du service GATT principal Flipr
BLE_SERVICE_UUID = "0000fee8-0000-1000-8000-00805f9b34fb"

# Caractéristiques GATT
BLE_CHAR_NOTIFY    = "0000fff1-0000-1000-8000-00805f9b34fb"  # Notifications (Flipr classique)
BLE_CHAR_READ      = "0000fff2-0000-1000-8000-00805f9b34fb"  # Lecture directe (Start Max)
BLE_CHAR_WRITE     = "0000fff3-0000-1000-8000-00805f9b34fb"  # Commandes d'écriture

# Intervalles
BLE_UPDATE_INTERVAL_MIN   = 60    # minutes entre chaque lecture BLE
BLE_CONNECTION_TIMEOUT    = 45    # secondes max pour une connexion BLE
BLE_STARTMAX_WAIT         = 35    # secondes d'attente pour le modèle Start Max

# Options de configuration BLE
CONF_BLE_ENABLED   = "ble_enabled"
CONF_BLE_ADDRESS   = "ble_address"

# Intervalles des coordinateurs
CLOUD_UPDATE_INTERVAL_MIN = 60
BLE_UPDATE_INTERVAL_DEFAULT = 60