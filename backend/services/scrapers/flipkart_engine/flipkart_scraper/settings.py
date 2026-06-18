"""
settings.py — Scrapy project settings for Flipkart scraper.
"""

BOT_NAME = "flipkart_scraper"
SPIDER_MODULES = ["flipkart_scraper.spiders"]
NEWSPIDER_MODULE = "flipkart_scraper.spiders"

# ── Politeness ────────────────────────────────────────────────────────────────
ROBOTSTXT_OBEY = False
DOWNLOAD_DELAY = 2          # seconds between requests per domain
RANDOMIZE_DOWNLOAD_DELAY = True  # 0.5× to 1.5× of DOWNLOAD_DELAY
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# ── Retry ─────────────────────────────────────────────────────────────────────
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 502, 503, 504]

# ── HTTP Cache (useful during development) ────────────────────────────────────
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 3600

# ── Middlewares ───────────────────────────────────────────────────────────────
DOWNLOADER_MIDDLEWARES = {
    "flipkart_scraper.middlewares.RotateUserAgentMiddleware": 400,
    "flipkart_scraper.middlewares.FlipkartHeadersMiddleware": 410,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 550,
    "scrapy.downloadermiddlewares.httpcache.HttpCacheMiddleware": 900,
}

# ── Pipelines (order matters) ─────────────────────────────────────────────────
ITEM_PIPELINES = {
    "flipkart_scraper.pipelines.CleaningPipeline": 100,   # clean first
    "flipkart_scraper.pipelines.DedupPipeline": 200,      # dedup second
    "flipkart_scraper.pipelines.CSVExportPipeline": 300,  # write CSV
    "flipkart_scraper.pipelines.MySQLPipeline": 400,      # write to MySQL directly
}

# ── Output ────────────────────────────────────────────────────────────────────
FEEDS = {}  # We handle output in CSVExportPipeline — disable default feed

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# ── Misc ──────────────────────────────────────────────────────────────────────
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
    "Gecko/20100101 Firefox/126.0",
]
