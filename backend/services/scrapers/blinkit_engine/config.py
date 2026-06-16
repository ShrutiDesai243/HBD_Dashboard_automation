"""
Blinkit Scraper Engine — Configuration
"""
import os
import pathlib

# ── Paths ──────────────────────────────────────────────────────────────────────
ENGINE_DIR   = pathlib.Path(__file__).parent
BACKEND_DIR  = ENGINE_DIR.parent.parent.parent
OUTPUT_DIR   = BACKEND_DIR / "output"
LOGS_DIR     = BACKEND_DIR / "logs"
STATE_FILE   = OUTPUT_DIR / "blinkit_scrape_state.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Blinkit API ────────────────────────────────────────────────────────────────
BLINKIT_BASE_URL      = "https://blinkit.com"
CATEGORY_LIST_URL     = "https://blinkit.com/v6/layout/web/slot/header_category_tile_list"
PRODUCTS_BY_CAT_URL   = "https://blinkit.com/v6/catalog/products/by_category"
SUBCATEGORY_LIST_URL  = "https://blinkit.com/v6/catalog/products/category_listing"
PRODUCT_DETAIL_URL    = "https://blinkit.com/v6/catalog/products/by_category"

# Default pincode (Delhi — largest catalog)
DEFAULT_PINCODE = "110001"

# Major city pincodes for broader coverage
PINCODE_LIST = [
    "110001",  # Delhi
    "400001",  # Mumbai
    "560001",  # Bangalore
    "600001",  # Chennai
    "700001",  # Kolkata
    "500001",  # Hyderabad
    "380001",  # Ahmedabad
    "411001",  # Pune
]

# ── HTTP Headers ───────────────────────────────────────────────────────────────
BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "app_client": "consumer_web",
    "app_version": "1060000",
    "web_app_version": "1060000",
    "device_id": "web_device_01",
    "Origin": "https://blinkit.com",
    "Referer": "https://blinkit.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# ── Rate Limiting ──────────────────────────────────────────────────────────────
REQUEST_DELAY_MIN   = 0.5    # seconds between requests (min)
REQUEST_DELAY_MAX   = 1.5    # seconds between requests (max)
MAX_RETRIES         = 5
BACKOFF_BASE        = 1.5    # exponential backoff factor
BACKOFF_MAX         = 30     # max backoff seconds
REQUEST_TIMEOUT     = 20     # HTTP timeout seconds
CONCURRENT_WORKERS  = 3      # parallel category workers

# ── Database Batching ──────────────────────────────────────────────────────────
PRODUCT_BATCH_SIZE  = 500    # products per MySQL commit
CATEGORY_BATCH_SIZE = 50     # categories per commit

# ── Scrape Modes ───────────────────────────────────────────────────────────────
MODE_FULL        = "full"         # Scrape ALL categories & products
MODE_CATEGORIES  = "categories"   # Only update category tree
MODE_INCREMENTAL = "incremental"  # Only scrape new/updated products
