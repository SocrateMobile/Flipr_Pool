"""Constants for the Flipr Pool integration."""

DOMAIN = "flipr_pool"
API_BASE_URL = "https://apis.goflipr.com"

# ── Configuration de traitement ────────────────────────────
# Ces valeurs servent de base pour les calculs de doses
PH_TARGET          = 7.4     # pH idéal cible
PH_MINUS_DOSE      = 100.0   # g par m³ par unité pH (granulés bisulfate)
PH_PLUS_DOSE       = 150.0   # g par m³ par unité pH (granulés carbonate)

CHLORINE_TARGET    = 2.0     # mg/L idéal
CHLORINE_DOSE      = 1.5     # g de produit par m³ par mg/L (chlore choc 70%)

PUMP_MIN_HOURS     = 4.0
PUMP_MAX_HOURS     = 24.0

# ── Endpoints API ──────────────────────────────────────────
AUTH_URL = f"{API_BASE_URL}/OAuth2/token"
SURVEY_URL = "{api_base}/modules/{flipr_id}/survey/last"
SHORTTERM_URL = "{api_base}/modules/{flipr_id}/shortterm"
HUB_URL = f"{API_BASE_URL}/hub/{{flipr_id}}"