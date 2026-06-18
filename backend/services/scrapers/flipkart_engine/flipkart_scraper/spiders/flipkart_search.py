"""
flipkart_search.py
==================
On-demand search spider. User types any category or product name.
Spider finds and scrapes it. No CSS class dependency for URL resolution.

STABLE EXTRACTION STRATEGY (class-independent):
  Three signals used, in priority order:

  1. `store=` param in product links  — product DATA, never changes
     Every product href contains:  store=4rr%2Ftz1
     Decode → sid=4rr,tz1 → build category URL
     This is part of Flipkart's product tracking data, NOT their UI CSS.

  2. `a[href*="/pr?"][href*="sid="]` XPath  — URL structure, not class names
     Category browse links always contain /pr? and sid= in their href.
     We extract them by href pattern, not by CSS class.

  3. Search URL as ultimate fallback  — always works, no dependency at all
     flipkart.com/search?q=<query> renders the same product cards.
     Our parse() logic works identically on search and category pages.

Usage:
    scrapy crawl flipkart_search -a query="Gaming Laptops"
    scrapy crawl flipkart_search -a query="Samsung Galaxy" -a pages=3
    scrapy crawl flipkart_search -a query="boAt Earbuds" -a pages=5
"""

import re
import urllib.parse
from collections import Counter

import scrapy
from flipkart_scraper.items import FlipkartItem

# Tracking/noise params to strip when cleaning URLs
_STRIP_PARAMS = {
    "otracker", "otracker1", "otracker2", "fm", "iid", "ppt", "ppn",
    "ssid", "qH", "ov_redirect", "srno", "lid", "marketplace",
    "as", "as-show", "as-pos", "as-type",
}

# Same product card / field selectors as flipkart_products.py
SEL = {
    "container":   "div.jIjQ8S, div.bLCLBY, div.RGLWAk, div.QSCKDh",
    "name_div":    "div.RG5Slk::text",
    "name_link_a": "a.atJtCj",
    "name_link_b": "a.pIpigb",
    "price":       "div.hZ3P6w::text",
    "mrp":         "div.kRYCnD::text",
    "discount":    "div.HQe8jr span::text",
    "rating":      "div.MKiFS6::text",
    "reviews":     "span.PvbNMB",
    "brand":       "div.Fo1I0b::text",
    "specs":       "li.DTBslk::text",
    "image_b":     "img.UCc1lI::attr(src)",
    "image_a":     "img.MZeksS::attr(src)",
    "link_main":   "a.k7wcnx::attr(href)",
    "link_b":      "a.GnxRXv::attr(href)",
    "link_a1":     "a.CIaYa1::attr(href)",
    "next_page":   "a.jgg0SZ::attr(href)",
}


def _clean_url(url: str) -> str:
    """Strip tracking params, keep sid and p[] facet params."""
    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
        kept = {
            k: v for k, v in qs.items()
            if k.lower().split("[")[0].replace("%5b", "").replace("%5d", "")
            not in _STRIP_PARAMS
        }
        new_qs = urllib.parse.urlencode(kept, doseq=True)
        return urllib.parse.urlunparse(parsed._replace(query=new_qs))
    except Exception:
        return url


class FlipkartSearchSpider(scrapy.Spider):
    name = "flipkart_search"

    # ── Entry point ────────────────────────────────────────────────────────────

    async def start(self):
        query = getattr(self, "query", "").strip()
        if not query:
            self.logger.error(
                "No query provided. Use: scrapy crawl flipkart_search -a query='Gaming Laptops'"
            )
            return

        self._query     = query
        self._max_pages = int(getattr(self, "pages", "3"))
        self._items_count = 0

        search_url = (
            "https://www.flipkart.com/search"
            f"?q={urllib.parse.quote(query)}&marketplace=FLIPKART"
        )

        self.logger.info(f"[flipkart_search] Query: '{query}' | Max pages: {self._max_pages}")

        yield scrapy.Request(
            url=search_url,
            callback=self.resolve_and_scrape,
            meta={
                "query":      query,
                "search_url": search_url,
                "page_num":   1,
            },
            dont_filter=True,
        )

    # ── Step 1: Resolve real category URL (class-independent) ─────────────────

    def resolve_and_scrape(self, response):
        """
        Extract the best category URL from the search results page,
        then scrape it. Uses three class-independent strategies.
        """
        query = response.meta["query"]
        self.logger.info(
            f"[resolve] HTTP {response.status} | {response.url[:80]}"
        )

        category_url, method = self._resolve_url(response)

        self.logger.info(
            f"[resolve] Method={method} | URL={category_url[:90]}"
        )

        # If the resolved URL is the same as what we already have, scrape here
        if category_url == response.url:
            self.logger.info("[resolve] Using search page directly (no better URL found)")
            yield from self._scrape_page(response, page_num=1)
        else:
            yield scrapy.Request(
                url=category_url,
                callback=self.parse,
                meta={
                    "query":        query,
                    "leaf_category": query,
                    "main_category": "",
                    "subcategory":   "",
                    "page_num":      1,
                    "category_url":  category_url,
                },
                dont_filter=True,
            )

    def _resolve_url(self, response) -> tuple[str, str]:
        """
        Multi-layer class-independent URL resolver.
        Returns (url, method_name).

        STRATEGY PRIORITY:
          1. store= param from product hrefs  → product data (never changes)
          2. href pattern a[href*=/pr?][sid=]  → URL structure (stable years)
          3. Current search URL               → always works
        """

        # ── Strategy 1: Extract `store=` from product link hrefs ─────────────
        # Every product card has a link with:  store=4rr%2Ftz1
        # This is the category SID encoded inside the product tracking URL.
        # It's product DATA embedded in URLs — extremely stable.
        store_sids = []
        for href in response.xpath('//a[contains(@href,"store=")]/@href').getall()[:15]:
            m = re.search(r"[?&]store=([^&]+)", href)
            if m:
                raw = urllib.parse.unquote(m.group(1))
                sid = raw.replace("%2C", ",").replace("+", " ").strip()
                if sid and re.match(r"^[a-z0-9,]+$", sid, re.I):
                    store_sids.append(sid)

        if store_sids:
            common_sid, count = Counter(store_sids).most_common(1)[0]
            if count >= 2:  # Must appear in at least 2 product links
                # Now find a href that uses this SID to get the real path
                encoded = urllib.parse.quote(common_sid)
                # Try to get the actual category path from any /pr? link with this SID
                for href in response.xpath(
                    '//a[contains(@href,"/pr?") and contains(@href,"sid=")]/@href'
                ).getall():
                    m = re.search(r"sid=([^&]+)", href)
                    if m:
                        decoded = urllib.parse.unquote(m.group(1)).strip()
                        if decoded == common_sid or decoded.startswith(common_sid):
                            clean = _clean_url(response.urljoin(href))
                            return clean, f"store_sid(sid={common_sid},count={count})"

                # Fallback: build a /search URL with the sid appended
                base = response.url.split("?")[0]
                q = urllib.parse.quote(self._query)
                url = f"https://www.flipkart.com/search?q={q}&sid={encoded}"
                return url, f"store_sid_built(sid={common_sid})"

        # ── Strategy 2: href pattern matching — NO class names ───────────────
        # Category browse links always have /pr? and sid= in their href.
        # We select by href content, not CSS class.
        # We prefer links marked with otracker=categorytree (sidebar category
        # links) — this query-param value has been stable for 3+ years.
        cat_hrefs = response.xpath(
            '//a[contains(@href, "/pr?") '
            'and contains(@href, "sid=") '
            'and not(contains(@href, "pid=")) '
            'and not(contains(@href, "/p/"))]/@href'
        ).getall()

        if cat_hrefs:
            # Prefer sidebar links (have otracker=categorytree in href)
            sidebar = [h for h in cat_hrefs if "categorytree" in h]
            candidates = sidebar if sidebar else cat_hrefs

            # Pick the most specific URL (deepest SID = most category segments)
            def _sid_depth(href):
                m = re.search(r"sid=([^&]+)", href)
                return len(urllib.parse.unquote(m.group(1)).split(",")) if m else 0

            candidates.sort(key=_sid_depth, reverse=True)
            best = _clean_url(response.urljoin(candidates[0]))
            source = "sidebar_href" if sidebar else "any_pr_href"
            return best, source

        # ── Strategy 3: Response URL (if Flipkart redirected search → category) ─
        if "/pr?" in response.url and "sid=" in response.url:
            return _clean_url(response.url), "redirect"

        # ── Strategy 4: Search URL fallback — always works ────────────────────
        return response.url, "search_fallback"

    # ── Step 2: Parse product cards (same as flipkart_products.py) ───────────

    def parse(self, response):
        yield from self._scrape_page(response, response.meta.get("page_num", 1))

    def _scrape_page(self, response, page_num: int):
        meta  = response.meta
        query = meta.get("query", self._query)

        products = response.css(SEL["container"])
        self.logger.info(
            f"[p{page_num}] HTTP {response.status} | "
            f"{len(products)} cards | {response.url[:70]}"
        )

        for product in products:
            item = FlipkartItem()
            item["main_category"] = meta.get("main_category", "")
            item["subcategory"]   = meta.get("subcategory", "")
            item["leaf_category"] = meta.get("leaf_category", query)
            item["product_name"]  = self._get_name(product)
            item["brand"]         = product.css(SEL["brand"]).get()
            item["price"]         = product.css(SEL["price"]).get()
            mrp_list              = product.css(SEL["mrp"]).getall()
            item["mrp"]           = "".join(mrp_list) if mrp_list else None
            item["discount"]      = product.css(SEL["discount"]).get()
            item["rating"]        = product.css(SEL["rating"]).get()
            item["reviews"]       = self._get_reviews(product)
            item["image_url"]     = (
                product.css(SEL["image_b"]).get()
                or product.css(SEL["image_a"]).get()
            )

            rel  = (
                product.css(SEL["link_main"]).get()
                or product.css(SEL["link_b"]).get()
                or product.css(SEL["link_a1"]).get()
            )
            full = response.urljoin(rel) if rel else None

            if full:
                pid_m              = re.search(r"pid=([A-Z0-9]+)", full)
                path               = re.sub(r"\?.*", "", full)
                item["product_url"] = f"{path}?pid={pid_m.group(1)}" if pid_m else path
                item["product_id"]  = pid_m.group(1) if pid_m else None
            else:
                item["product_url"] = None
                item["product_id"]  = None

            specs              = product.css(SEL["specs"]).getall()
            item["spec_bullets"] = " | ".join(specs) if specs else None

            self._items_count += 1
            yield item

        # ── Pagination ────────────────────────────────────────────────────────
        if page_num < self._max_pages:
            next_href = response.css(SEL["next_page"]).get()
            if next_href:
                yield response.follow(
                    next_href,
                    callback=self.parse,
                    meta={**meta, "page_num": page_num + 1},
                )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_name(self, product):
        name = product.css(SEL["name_div"]).get()
        if name and name.strip():
            return name.strip()
        for sel in (SEL["name_link_a"], SEL["name_link_b"]):
            el = product.css(sel)
            if el:
                title = el.attrib.get("title")
                if title and title.strip():
                    return title.strip()
                text = el.css("::text").get()
                if text and text.strip():
                    return text.strip()
        return None

    def _get_reviews(self, product):
        raw = " ".join(product.css(SEL["reviews"] + " *::text").getall()).strip()
        if not raw:
            raw = product.css(SEL["reviews"] + "::text").get("").strip()
        if not raw:
            return None
        m = re.match(r"^\(?([0-9,]+)\)?$", raw.replace("\xa0", " ").strip())
        return m.group(1).replace(",", "") if m else raw

    def closed(self, reason):
        self.logger.info(
            f"[flipkart_search] Done. Query='{self._query}' | "
            f"Items={self._items_count} | Reason={reason}"
        )
