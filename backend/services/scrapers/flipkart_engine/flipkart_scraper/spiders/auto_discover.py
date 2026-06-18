"""
auto_discover.py — Crawls Flipkart's navigation menu and automatically
appends any NEW category URLs found into categories.csv.

Run this periodically to keep categories.csv up to date without
manual editing as Flipkart adds new sections.

Usage:
    scrapy crawl auto_discover
    scrapy crawl auto_discover -a dry_run=True   # preview only, no CSV write
"""

import re
import scrapy
from urllib.parse import urljoin, urlparse, parse_qs
from ..csv_manager import load_categories, save_categories, FIELDNAMES, print_summary


NAV_SEED_URLS = [
    "https://www.flipkart.com/",
    "https://www.flipkart.com/electronics-store",
    "https://www.flipkart.com/tvs-appliances",
    "https://www.flipkart.com/mobiles-store",
    "https://www.flipkart.com/fashion-store",
    "https://www.flipkart.com/home-improvement-store",
    "https://www.flipkart.com/sports-store",
]

# Flipkart category URL pattern — must contain sid= or /pr? with product listing markers
CATEGORY_PATTERN = re.compile(
    r"flipkart\.com/.+/pr\?.*sid=|flipkart\.com/.+\?.*sid=.*&"
)

# These patterns are navigation/auth/account links — skip them
SKIP_PATTERNS = re.compile(
    r"/(login|register|cart|wishlist|account|orders|track|"
    r"help|sitemap|plus|offers|advertise|sell|flyout|notifications)"
    r"|javascript:|#|mailto:",
    re.IGNORECASE
)


def _guess_hierarchy(url: str, link_text: str) -> tuple[str, str, str]:
    """
    Best-effort hierarchy from URL path segments and link text.
    Returns (level1, level2, level3).
    """
    path = urlparse(url).path.strip("/")
    parts = [p.replace("-", " ").title() for p in path.split("/") if p]

    # Map common path prefixes to level1
    L1_MAP = {
        "mobiles": "Electronics", "laptops": "Electronics", "tablets": "Electronics",
        "headphones": "Electronics", "cameras": "Electronics", "televisions": "TVs & Appliances",
        "washing": "TVs & Appliances", "refrigerators": "TVs & Appliances",
        "air-conditioners": "TVs & Appliances", "mens": "Men", "womens": "Women",
        "boys": "Baby & Kids", "girls": "Baby & Kids", "baby": "Baby & Kids",
        "toys": "Baby & Kids", "furniture": "Home & Furniture", "home-decor": "Home & Furniture",
        "kitchen": "Home & Furniture", "sports": "Sports Books & More",
        "books": "Sports Books & More", "musical": "Sports Books & More",
    }

    first = path.split("/")[0].lower() if path else ""
    level1 = next((v for k, v in L1_MAP.items() if first.startswith(k)), "Other")
    level2 = parts[0] if len(parts) > 0 else "General"
    level3 = link_text.strip() if link_text.strip() else (parts[-1] if parts else "Unknown")

    return level1, level2, level3


class AutoDiscoverSpider(scrapy.Spider):
    name = "auto_discover"
    allowed_domains = ["flipkart.com"]

    def __init__(self, dry_run=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dry_run = dry_run in (True, "True", "true", "1")
        # Build set of already-known URLs for dedup check
        existing = load_categories()
        self._known_urls = {r["url"].strip() for r in existing}
        self._new_rows: list[dict] = []

    async def start(self):
        for url in NAV_SEED_URLS:
            yield scrapy.Request(
                url=url,
                callback=self.parse_nav,
                headers={"Accept": "text/html,*/*", "Accept-Language": "en-IN"},
                errback=self.on_error,
            )

    def parse_nav(self, response):
        """Extract all category-looking hrefs from the page navigation."""
        # Target nav links — Flipkart uses various nav containers
        selectors = [
            "nav a[href]",
            "._1LKTO3",           # category nav links
            "._2GWsHO a[href]",   # mega menu
            "a._2UzuFa[href]",    # top nav items
            "div._1Lr76j a[href]",# sub nav
            "a[href*='/pr?']",    # any listing link
            "a[href*='?sid=']",   # sid-based links
        ]

        seen_hrefs = set()
        for sel in selectors:
            for a in response.css(sel):
                href = a.attrib.get("href", "").strip()
                text = " ".join(a.css("::text").getall()).strip()

                if not href or href in seen_hrefs:
                    continue
                seen_hrefs.add(href)

                full_url = urljoin("https://www.flipkart.com", href)

                # Skip non-category links
                if SKIP_PATTERNS.search(full_url):
                    continue

                if not CATEGORY_PATTERN.search(full_url):
                    continue

                valid_prefixes = (
                    "mobiles", "laptops", "tablets", "televisions", "cameras",
                    "headphones", "computers", "gaming", "smart-wearable",
                    "clothing", "footwear", "mens", "womens", "kids", "baby",
                    "furniture", "home-decor", "kitchen", "sports", "books",
                    "musical-instruments", "toys", "health-care", "networking",
                    "audio-video", "computer-peripherals", "wearable", "electronics",
                )
                path_segments = [
                    segment for segment in urlparse(full_url).path.strip("/").split("/")
                    if segment
                ]
                if not path_segments or not path_segments[0].startswith(valid_prefixes):
                    continue

                if full_url not in self._known_urls:
                    l1, l2, l3 = _guess_hierarchy(full_url, text)
                    new_row = {
                        "level1": l1,
                        "level2": l2,
                        "level3": l3 or text,
                        "url": full_url,
                        "scrape_status": "pending",
                        "last_scraped": "",
                        "items_found": "",
                        "pages_scraped": "0",
                        "errors": "",
                        "notes": "auto-discovered",
                    }
                    self._new_rows.append(new_row)
                    self._known_urls.add(full_url)
                    self.logger.info(f"[NEW] {l1} > {l2} > {l3} — {full_url}")

    def on_error(self, failure):
        self.logger.warning(f"[SKIP] {failure.request.url} — {failure.value}")

    def closed(self, reason):
        if not self._new_rows:
            self.logger.info("No new categories discovered — CSV is up to date.")
            print_summary()
            return

        self.logger.info(f"Discovered {len(self._new_rows)} new categories.")

        if self.dry_run:
            self.logger.info("[DRY RUN] Would add:")
            for r in self._new_rows:
                self.logger.info(f"  {r['level1']} > {r['level2']} > {r['level3']}")
            return

        # Append to CSV
        existing = load_categories()
        all_rows = existing + self._new_rows
        save_categories(all_rows)

        self.logger.info(
            f"categories.csv updated: {len(existing)} existing + "
            f"{len(self._new_rows)} new = {len(all_rows)} total"
        )
        print_summary()
