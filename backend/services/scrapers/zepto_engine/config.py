import random
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # → backend/
OUTPUT_DIR = BASE_DIR / "output" / "zepto"
EXPORT_DIR = OUTPUT_DIR / "exports"
CATEGORY_EXPORT_DIR = EXPORT_DIR / "categories"
JSONL_EXPORT_DIR = EXPORT_DIR / "jsonl"
DB_PATH = OUTPUT_DIR / "zepto_master.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Make sure all directories exist recursively
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
CATEGORY_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
JSONL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ── Target website ─────────────────────────────────────────────
BASE_URL = "https://www.zepto.com"
DEFAULT_PINCODE = "400001"

# ── Stealth ───────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

SCREEN_RESOLUTIONS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def get_random_viewport() -> dict:
    return random.choice(SCREEN_RESOLUTIONS)


# ── Timing / Scroll / Retry ─────────────────────────────────────
SCROLL_PAUSE_MS = 400
SCROLL_TIMEOUT_MS = 2000
MAX_SCROLL_ATTEMPTS = 150
NETWORK_IDLE_TIMEOUT_MS = 15000
PAGE_LOAD_TIMEOUT_MS = 60000

CONCURRENT_CATEGORIES = 3

MAX_RETRIES = 3
RETRY_DELAY_S = 5
REQUEST_DELAY_RANGE = (0.5, 1.5)


# ── Zepto DOM fallback selectors ────────────────────────────────
SELECTORS = {
    # PLP product cards (fallback)
    "product_card": [
        "a[href*='/p/'], a[href*='/product/']",
        "[data-testid*='product']",
    ],

    # PDP / Product name fallback
    "product_name": [
        "h1",
        "[data-testid*='product-title']",
    ],

    # price fallback
    "price": [
        "[data-testid*='price']",
        "[class*='price' i]",
    ],

    # image fallback
    "image": [
        "img",
    ],

    # load more fallback
    "load_more_button": [
        "button:has-text('Load More')",
        "button:has-text('Show more')",
        "button[aria-label*='Load']",
    ],
}

# API endpoints to intercept (primary)
# NOTE: Zepto responses change frequently; we keep broad patterns.
API_URL_PATTERNS = [
    "/api/v1/layout/",
    "/api/v1/catalog/",
    "graphql",
]


# ── Fuzzy geolocation heuristics ───────────────────────────────
# We cannot reliably reverse-geocode without external calls.
# This mapping is intentionally lightweight and can be extended.
# Keys: pincode -> {lat, lon, city}
PINCODE_GEO_MAP = {
    "400050": {"lat": 19.0544, "lon": 72.8402, "city": "Mumbai"},
    "560034": {"lat": 12.9325, "lon": 77.6269, "city": "Bengaluru"},
    # "110048": {"lat": 28.5520, "lon": 77.2358, "city": "Delhi"},
    # "411038": {"lat": 18.5074, "lon": 73.8077, "city": "Pune"},
    # "500081": {"lat": 17.4347, "lon": 78.4025, "city": "Hyderabad"},
    # "400001": {"lat": 18.9750, "lon": 72.8258, "city": "Mumbai"},
    # "400076": {"lat": 19.1000, "lon": 72.9000, "city": "Mumbai"},
    # "411001": {"lat": 18.5204, "lon": 73.8567, "city": "Pune"},
    # "560001": {"lat": 12.9716, "lon": 77.5946, "city": "Bengaluru"},

}


