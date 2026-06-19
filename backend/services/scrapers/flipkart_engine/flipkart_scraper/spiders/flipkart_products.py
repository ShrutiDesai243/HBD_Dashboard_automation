"""
flipkart_products.py
====================
Run from E:\flipkart_scraper folder:

    scrapy crawl flipkart_products -a debug=1
    scrapy crawl flipkart_products -o output/products.json
    scrapy crawl flipkart_products -o output/products.csv
"""

import csv
import os
import re
import scrapy
from flipkart_scraper.items import FlipkartItem
from flipkart_scraper.csv_manager import get_pending_urls

SEL = {
    # ── Product card containers ────────────────────────────────────────────
    # jIjQ8S  — current main search/browse layout (confirmed working June 2026)
    # bLCLBY  — older Fashion/compact grid layout (keep as fallback)
    # RGLWAk  — older Baby&Kids/Home browse grid (keep as fallback)
    # QSCKDh  — secondary container seen in some pages
    "container":     "div.jIjQ8S, div.bLCLBY, div.RGLWAk, div.QSCKDh",

    # ── Product name ────────────────────────────────────────────────────────
    # RG5Slk  — current name div (confirmed working June 2026)
    # atJtCj  — old Fashion/Electronics anchor name
    # pIpigb  — old browse-grid anchor name
    "name_div":      "div.RG5Slk::text",
    "name_link_a":   "a.atJtCj",
    "name_link_b":   "a.pIpigb",

    # ── Pricing ─────────────────────────────────────────────────────────────
    "price":         "div.hZ3P6w::text",  # selling price
    "mrp":           "div.kRYCnD::text",  # original MRP
    "discount":      "div.HQe8jr span::text",

    # ── Metadata ────────────────────────────────────────────────────────────
    "rating":        "div.MKiFS6::text",
    "reviews":       "span.PvbNMB",
    "brand":         "div.Fo1I0b::text",
    "specs":         "li.DTBslk::text",

    # ── Images ──────────────────────────────────────────────────────────────
    "image_b":       "img.UCc1lI::attr(src)",  # current
    "image_a":       "img.MZeksS::attr(src)",  # older fallback

    # ── Product link ────────────────────────────────────────────────────────
    # k7wcnx  — current product anchor (confirmed working June 2026)
    # GnxRXv / CIaYa1 — old fallbacks
    "link_main":     "a.k7wcnx::attr(href)",
    "link_b":        "a.GnxRXv::attr(href)",
    "link_a1":       "a.CIaYa1::attr(href)",

    # ── Pagination ──────────────────────────────────────────────────────────
    "next_page":     "a.jgg0SZ::attr(href)",
}


class FlipkartProductsSpider(scrapy.Spider):
    name = "flipkart_products"

    # ── FIXED: async def start() — required for Scrapy 2.12+ / Python 3.14 ───
    async def start(self):
        is_debug  = str(getattr(self, "debug", "0")).strip() in ("1", "true", "True")
        max_pages = int(getattr(self, "pages", "1"))
        category_filter = getattr(self, "category", None)
        show_pending = str(getattr(self, "show_pending", "0")).strip() in ("1", "true", "True")

        self._is_debug  = is_debug
        self._max_pages = max_pages
        self.scraped_stats = {}

        # Use csv_manager to get only verified rows — no manual CSV open needed
        rows = get_pending_urls()

        if rows:
            self.logger.info(f"--- PENDING SEED CATEGORIES ({len(rows)} TOTAL) ---")
            for r in rows:
                self.logger.info(f"  - {r.get('main_category')} > {r.get('subcategory')} > {r.get('leaf_category')}")
        else:
            self.logger.warning(
                "No verified URLs found. Run discover_categories first."
            )
            return

        if show_pending:
            self.logger.info("show_pending=1 passed. Exiting without scraping.")
            return

        # Apply category filter if provided
        if category_filter:
            filtered_rows = [
                r for r in rows
                if r.get("main_category", "").strip().lower() == category_filter.strip().lower()
            ]
            self.logger.info(f"Filtered by category='{category_filter}': {len(filtered_rows)} of {len(rows)} rows matched.")
            rows = filtered_rows
            if not rows:
                self.logger.warning(f"No pending categories matched filter '{category_filter}'.")
                return

        if is_debug:
            rows = rows[:1]
            self.logger.info("DEBUG MODE: 1 category, page 1 only")

        for row in rows:
            url = row.get("url", "").strip()
            if not url:
                continue
            if url.startswith("/"):
                url = "https://www.flipkart.com" + url
            
            # Initialize stats tracking for CSV update when spider finishes
            self.scraped_stats[url] = {"items": 0, "pages": 0, "row": row}

            yield scrapy.Request(
                url=url,
                callback=self.parse,
                dont_filter=True,
                meta={
                    "main_category": row.get("main_category", "").strip(),
                    "subcategory":   row.get("subcategory", "").strip(),
                    "leaf_category": row.get("leaf_category", "").strip(),
                    "category_url":  url,
                    "page_num":      1,
                },
            )

    def parse(self, response):
        meta     = response.meta
        page_num = meta["page_num"]
        label    = f"{meta['leaf_category']} p{page_num}"

        self.logger.info(f"[{label}] HTTP {response.status} | {response.url[:70]}")

        products = response.css(SEL["container"])
        self.logger.info(f"[{label}] Cards found: {len(products)}")

        # Track counts of items and pages crawled
        category_url = meta.get("category_url")
        if category_url and category_url in self.scraped_stats:
            self.scraped_stats[category_url]["pages"] += 1
            self.scraped_stats[category_url]["items"] += len(products)

        if self._is_debug:
            for p in products[:3]:
                self.logger.info(f"  >> {self._get_name(p)}")

        for product in products:
            item = FlipkartItem()

            item["main_category"] = meta["main_category"]
            item["subcategory"]   = meta["subcategory"]
            item["leaf_category"] = meta["leaf_category"]

            item["product_name"] = self._get_name(product)
            item["brand"]        = product.css(SEL["brand"]).get()
            item["price"]        = product.css(SEL["price"]).get()
            mrp_list             = product.css(SEL["mrp"]).getall()
            item["mrp"]          = "".join(mrp_list) if mrp_list else None
            item["discount"]     = product.css(SEL["discount"]).get()
            item["rating"]       = product.css(SEL["rating"]).get()
            item["reviews"]      = self._get_reviews(product)
            item["image_url"]    = (
                product.css(SEL["image_b"]).get()
                or product.css(SEL["image_a"]).get()
            )

            # ── Product link: k7wcnx is current; GnxRXv / CIaYa1 are old fallbacks
            rel  = (
                product.css(SEL["link_main"]).get()
                or product.css(SEL["link_b"]).get()
                or product.css(SEL["link_a1"]).get()
            )
            full = response.urljoin(rel) if rel else None

            # Clean URL: keep path + ?pid=XXXX only, strip all tracking params
            if full:
                pid_m = re.search(r"pid=([A-Z0-9]+)", full)
                path  = re.sub(r"\?.*", "", full)  # path without query string
                item["product_url"] = f"{path}?pid={pid_m.group(1)}" if pid_m else path
                item["product_id"]  = pid_m.group(1) if pid_m else None
            else:
                item["product_url"] = None
                item["product_id"]  = None

            specs = product.css(SEL["specs"]).getall()
            item["spec_bullets"] = " | ".join(specs) if specs else None

            yield item

        # Pagination — uncomment after page 1 confirmed working
        if not self._is_debug and page_num < self._max_pages:
             next_href = response.css(SEL["next_page"]).get()
             if next_href:
                 yield response.follow(
                     next_href,
                     callback=self.parse,
                     meta={**meta, "page_num": page_num + 1},
                 )

    def closed(self, reason):
        # Update status to 'done' in categories.csv for successfully scraped categories
        from flipkart_scraper.csv_manager import mark_done
        for url, stats in getattr(self, "scraped_stats", {}).items():
            if stats["items"] > 0:   # only mark done if actual products were scraped
                mark_done(url, stats["items"], stats["pages"])
                self.logger.info(
                    f"Updated CSV status to 'done' for: {stats['row'].get('leaf_category')} "
                    f"({stats['items']} items, {stats['pages']} pages)"
                )
            else:
                self.logger.warning(
                    f"Skipped mark_done (0 items): {stats['row'].get('leaf_category')} | {url[:60]}"
                )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_name(self, product):
        # 1. Try current layout: div.RG5Slk (confirmed June 2026)
        name = product.css(SEL["name_div"]).get()
        if name and name.strip():
            return name.strip()
        # 2. Old layouts: anchor title or text
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
        m = re.match(r"^\(?([\d,]+)\)?$", raw.replace("\xa0", " ").strip())
        if m:
            return m.group(1).replace(",", "")
        return raw