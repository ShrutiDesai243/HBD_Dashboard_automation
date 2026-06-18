"""
discover_categories.py
======================
Two-pass spider that fills blank URLs in categories.csv then verifies all URLs.

PASS 1 — NAV CRAWL (URL Discovery)
  Visits flipkart.com homepage, extracts every nav dropdown link,
  fuzzy-matches each link against your leaf_category names,
  writes matched clean URLs back into categories.csv.

PASS 2 — VERIFICATION
  Visits every row that has a URL (newly found or pre-existing),
  confirms product cards exist on the page,
  marks each row as 'verified' or 'failed'.

Run:
    scrapy crawl discover_categories
"""

import re
from difflib import SequenceMatcher
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, unquote

import scrapy
from flipkart_scraper.csv_manager import (
    get_url_pending,
    get_verify_pending,
    write_url,
    mark_verified,
    mark_failed,
    print_summary,
)

# ── Product card selectors — all three layouts ────────────────────────────────
# Layout A (bLCLBY) — Fashion, Electronics search
# Layout B (RGLWAk) — Baby&Kids, Home, Food browse grid
# Layout C (jIjQ8S) — Appliances, TVs, Washing Machines
CARD_SELECTORS = ["div.bLCLBY", "div.RGLWAk", "div.jIjQ8S", "div.QSCKDh"]

FLIPKART_HOME = "https://www.flipkart.com"

# Minimum fuzzy match score to accept a nav link as a category match
MATCH_THRESHOLD = 0.72

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class DiscoverCategoriesSpider(scrapy.Spider):
    name = "discover_categories"
    allowed_domains = ["flipkart.com"]

    # ── FIXED: async def start() — required for Scrapy 2.12+ / Python 3.14 ───
    async def start(self):
        print_summary()

        self._pending_rows = get_url_pending()
        self.logger.info(f"Rows needing URL discovery: {len(self._pending_rows)}")

        if self._pending_rows:
            yield scrapy.Request(
                url=FLIPKART_HOME,
                callback=self.parse_nav,
                headers=DEFAULT_HEADERS,
                dont_filter=True,
                meta={"handle_httpstatus_list": [301, 302, 403, 404]},
            )
        else:
            self.logger.info("No blank URLs — skipping nav crawl, going to verification.")
            async for req in self._verification_requests():
                yield req

    # ── PASS 1: Nav crawl ──────────────────────────────────────────────────────

    def parse_nav(self, response):
        self.logger.info(f"Nav page status: {response.status}")

        all_links = []
        for a in response.css("a[href]"):
            href = a.attrib.get("href", "").strip()
            text = " ".join(a.css("::text").getall()).strip()
            if not href or not text:
                continue
            if href.startswith("/") and ("/pr" in href or "store" in href or len(href) > 3):
                full_url = f"https://www.flipkart.com{href}"
                all_links.append((text, full_url))

        self.logger.info(f"Nav links extracted: {len(all_links)}")

        matched_count = 0
        unmatched = []

        for row in self._pending_rows:
            leaf = row["leaf_category"].strip()
            main = row["main_category"].strip()
            sub  = row["subcategory"].strip()

            best_score = 0
            best_url   = None
            best_text  = None

            for link_text, link_url in all_links:
                score = self._match_score(leaf, main, link_text, link_url)
                if score > best_score:
                    best_score = score
                    best_url   = link_url
                    best_text  = link_text

            if best_score >= MATCH_THRESHOLD and best_url:
                clean   = self._clean_url(best_url)
                written = write_url(main, sub, leaf, clean)
                if written:
                    matched_count += 1
                    self.logger.info(
                        f"[MATCHED {best_score:.2f}] '{leaf}' → '{best_text}' → {clean}"
                    )
                else:
                    self.logger.warning(
                        f"[WRITE FAIL] Row not found in CSV: '{main}' > '{sub}' > '{leaf}'"
                    )
            else:
                unmatched.append(row)
                self.logger.warning(
                    f"[NO MATCH] '{leaf}' (best score: {best_score:.2f}) — needs manual URL"
                )

        self.logger.info(
            f"Discovery done — matched: {matched_count}, unmatched: {len(unmatched)}"
        )
        if unmatched:
            self.logger.warning("Unmatched (add URLs manually):")
            for r in unmatched:
                self.logger.warning(
                    f"  {r['main_category']} > {r['subcategory']} > {r['leaf_category']}"
                )

        yield from self._verification_requests()

    # ── PASS 2: Verification ───────────────────────────────────────────────────

    def _verification_requests(self):
        """Sync generator — yields requests for every URL-bearing row."""
        rows = get_verify_pending()
        self.logger.info(f"URLs to verify: {len(rows)}")
        for row in rows:
            url = row.get("url", "").strip()
            if not url:
                continue
            if url.startswith("/"):
                url="https://www.flipkart.com" + url
            yield scrapy.Request(
                url=url,
                callback=self.verify_url,
                errback=self.on_error,
                headers=DEFAULT_HEADERS,
                dont_filter=True,
                meta={
                    "category_url": url,
                    "row": row,
                    "handle_httpstatus_list": [301, 302, 403, 404],
                },
            )

    def verify_url(self, response):
        url   = response.meta["category_url"]
        row   = response.meta["row"]
        label = f"{row.get('main_category','')} > {row.get('leaf_category','')}"

        if response.status in (301, 302):
            redirect = response.headers.get("Location", b"").decode()
            if redirect:
                self.logger.info(f"[REDIRECT] {label} → {redirect}")
                yield scrapy.Request(
                    url=redirect,
                    callback=self.verify_url,
                    errback=self.on_error,
                    headers=DEFAULT_HEADERS,
                    meta={**response.meta, "category_url": redirect},
                    dont_filter=True,
                )
            return

        if response.status == 404:
            mark_failed(url, "HTTP 404 — page not found")
            self.logger.warning(f"[404] {label} — {url}")
            return

        if response.status == 403:
            mark_failed(url, "HTTP 403 — blocked by Flipkart")
            self.logger.warning(f"[403 BLOCKED] {label}")
            return

        has_products = any(response.css(sel) for sel in CARD_SELECTORS)

        if response.status == 200 and has_products:
            mark_verified(url)
            card_count = sum(len(response.css(sel)) for sel in CARD_SELECTORS)
            self.logger.info(f"[VERIFIED] {label} — {card_count} cards")

        elif response.status == 200:
            mark_failed(url, "HTTP 200 but no product cards found")
            self.logger.warning(
                f"[EMPTY] {label} — no cards found. Check URL: {url}"
            )
        else:
            mark_failed(url, f"HTTP {response.status}")
            self.logger.warning(f"[HTTP {response.status}] {label} — {url}")

    def on_error(self, failure):
        url   = failure.request.meta.get("category_url", failure.request.url)
        row   = failure.request.meta.get("row", {})
        label = f"{row.get('main_category','')} > {row.get('leaf_category','')}"
        error = str(failure.value)
        mark_failed(url, error[:200])
        self.logger.error(f"[NETWORK ERROR] {label} — {error[:100]}")

    def closed(self, reason):
        self.logger.info(f"Spider closed: {reason}")
        print_summary()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _match_score(self, leaf: str, main: str, link_text: str, link_url: str) -> float:
        leaf_lower = leaf.lower().strip()
        text_lower = link_text.lower().strip()
        url_lower  = unquote(link_url).lower()

        text_score = SequenceMatcher(None, leaf_lower, text_lower).ratio()

        leaf_slug  = re.sub(r"[^a-z0-9]+", "-", leaf_lower).strip("-")
        slug_score = 1.0 if leaf_slug in url_lower else 0.0

        main_lower = main.lower().replace("tvs", "tv").replace("&", "and")
        main_words = [w for w in main_lower.split() if len(w) > 3]
        context_score = 0.2 if any(w in url_lower for w in main_words) else 0.0

        return (text_score * 0.55) + (slug_score * 0.30) + (context_score * 0.15)

    @staticmethod
    def _clean_url(url: str) -> str:
        """Keep only sid param, strip all tracking noise."""
        parsed = urlparse(url)
        qs     = parse_qs(parsed.query, keep_blank_values=False)

        if parsed.path == "/search":
            sid = qs.get("sid", [""])[0]
            clean_qs = urlencode({"sid": sid}) if sid else ""
            return urlunparse(parsed._replace(query=clean_qs))

        keep     = {"sid": qs["sid"][0]} if "sid" in qs else {}
        clean_qs = urlencode(keep) if keep else ""
        return urlunparse(parsed._replace(query=clean_qs))