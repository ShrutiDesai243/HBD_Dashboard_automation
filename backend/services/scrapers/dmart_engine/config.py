# ============================================================
# DMart Web Scraper — Configuration Module
# ============================================================
# Centralized configuration for the scraper. All tunable
# parameters live here to avoid magic numbers in code.
#
# Adapted from task-01_dmart-scraper/src/config.py:
#   - BASE_DIR now resolves to backend/ inside the project
#   - Output paths write to backend/output/ (not the task folder)
#   - All scraper constants (SELECTORS, timing) are unchanged.
# ============================================================

import random
from pathlib import Path

# ── Project Paths ──────────────────────────────────────────────
# Resolve to backend/output/dmart/ inside the HBD Dashboard project
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # → backend/
OUTPUT_DIR = BASE_DIR / "output" / "dmart"
EXPORT_DIR = OUTPUT_DIR / "exports"
CATEGORY_EXPORT_DIR = EXPORT_DIR / "categories"
JSONL_EXPORT_DIR = EXPORT_DIR / "jsonl"
DB_PATH = OUTPUT_DIR / "dmart_master.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Ensure output directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
CATEGORY_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
JSONL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ── Target Website ─────────────────────────────────────────────
BASE_URL = "https://www.dmart.in"
DEFAULT_PINCODE = "400001"  # Mumbai — high-availability zone

# ── Browser Stealth Settings ──────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
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
    """Return a random user agent string."""
    return random.choice(USER_AGENTS)


def get_random_viewport() -> dict:
    """Return a random screen resolution dict."""
    return random.choice(SCREEN_RESOLUTIONS)


# ── Scroll & Timing Settings ──────────────────────────────────
SCROLL_PAUSE_MS = 500           # ms to wait between scroll steps (tuned faster)
SCROLL_TIMEOUT_MS = 2000        # ms with no height change = done (tuned faster)
MAX_SCROLL_ATTEMPTS = 150       # safety cap on scroll iterations
NETWORK_IDLE_TIMEOUT_MS = 15000 # max ms to wait for network idle
PAGE_LOAD_TIMEOUT_MS = 60000    # max ms for initial page load

# ── Concurrency & Parallelization ──────────────────────────────
CONCURRENT_CATEGORIES = 3       # number of concurrent tabs running in parallel

# ── Retry & Resilience ────────────────────────────────────────
MAX_RETRIES = 3                 # retries per category on failure
RETRY_DELAY_S = 5               # seconds between retries
REQUEST_DELAY_RANGE = (0.5, 1.5)# random delay between page loads (tuned faster)

# ── DMart DOM Selectors ───────────────────────────────────────
# These selectors target the React-rendered DMart frontend.
# They may need updating if DMart changes their DOM structure.
SELECTORS = {
    # ── Pincode / Location Popup ──
    "pincode_popup":        "[class*='location'], [class*='pincode'], [class*='Location'], [class*='Pincode']",
    "pincode_input":        "input[placeholder*='pincode' i], input[placeholder*='Enter' i], input[type='tel'][class*='pin' i], input[name*='pin' i]",
    "pincode_submit":       "button[class*='submit' i], button[class*='check' i], button[class*='apply' i], button[type='submit']",
    "pincode_close":        "[class*='close' i], [class*='dismiss' i], button[aria-label='close' i]",

    # ── Navigation / Category Tree ──
    "nav_menu":             "nav, [class*='nav' i], [class*='menu' i], [class*='category' i]",
    "category_links":       "a[href*='/category/'], a[href*='/c/'], [class*='categ'] a",

    # ── Product Listing Page ──
    "product_card":         "div.MuiGrid-item:has(button:has-text('ADD TO CART')), div.MuiGrid-item:has(i.dmart-icon-cart), [class*='product-card' i], li[class*='product' i]",
    "product_link":         "a[href*='/product/'], a[href*='/p/'], a",
    "product_name":         "a[aria-label], [class*='product-name' i], [class*='ProductName' i], [class*='product-title' i], div[class*='text-primaryColor']:not([class*='text-center'])",
    "product_brand":        "[class*='brand' i], [class*='Brand' i]",
    "product_mrp":          "[class*='mrp' i], .line-through, s, del, p:has-text('MRP') + p",
    "product_sale_price":   "[class*='selling-price' i], [class*='dmart-price' i], section.text-primaryColor p.font-bold, p:has-text('DMart') + p",
    "product_pack_size":    "[class*='pack' i], [class*='variant' i], .MuiSelect-select span, div:has-text('kg'), div:has-text('gm'), div:has-text('L'), div:has-text('ml')",
    "product_availability": "[class*='out-of-stock' i], [class*='unavailable' i], div:has-text('Out of Stock')",
    "product_sku":          "[data-sku], [data-product-id], [data-id], [id*='sku' i]",
    "product_image":        "img[src*='images/products/'], img[src*='cdn.dmart.in/images/'], img",
    
    # ── Infinite Scroll ──
    "scroll_sentinel":      "[class*='loading' i], [class*='spinner' i], [class*='loader' i]",
    "no_more_products":     "[class*='no-more' i], [class*='end-of' i], [class*='empty' i]",
    "load_more_button":     "button:has-text('Load More'), button:has-text('View More'), button:has-text('Show More'), a:has-text('Load More'), a:has-text('View More'), div[role='button']:has-text('Load More'), span:has-text('Load More'), :has-text('View More Products'), :has-text('View All Products')",
}

# DOM Selectors for deeply scraping Product Description Pages (PDPs)
PDP_SELECTORS = {
    "product_name": "h1",
    "product_brand": "h1",  # Brand is often prefixed in the H1 title for DMart
    "product_mrp": "p:has-text('MRP'), span:has-text('MRP')",
    "product_sale_price": "h1 + div p:has-text('₹')", # It's generally near the H1
    "breadcrumbs": "nav[aria-label='breadcrumb'] li, .MuiBreadcrumbs-li",
    "description": "div[role='tabpanel'], .whitespace-pre-wrap, div[class*='desc' i], section[class*='desc' i]",
}

# ── Logging ────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE = OUTPUT_DIR / "scraper.log"

# ── Master Pincode Loop List ──────────────────────────────────
PINCODE_LIST = [
    "400001",  # Mumbai South
    #"411001",  # Pune
    #"560001",  # Bangalore
    # "560102",  # Bangalore HSR
    # "500032",  # Hyderabad Gachibowli
    # "380015",  # Ahmedabad
    #"395007",  # Surat
    # "452001",  # Indore
]

