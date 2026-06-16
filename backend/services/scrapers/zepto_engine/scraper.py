import asyncio
import json
import logging
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Response, Playwright

from .config import (
    BASE_URL,
    DEFAULT_PINCODE,
    SELECTORS,
    SCROLL_PAUSE_MS,
    SCROLL_TIMEOUT_MS,
    MAX_SCROLL_ATTEMPTS,
    NETWORK_IDLE_TIMEOUT_MS,
    PAGE_LOAD_TIMEOUT_MS,
    CONCURRENT_CATEGORIES,
    MAX_RETRIES,
    RETRY_DELAY_S,
    REQUEST_DELAY_RANGE,
    EXPORT_DIR,
    CATEGORY_EXPORT_DIR,
    JSONL_EXPORT_DIR,
    get_random_user_agent,
    get_random_viewport,
    API_URL_PATTERNS,
    PINCODE_GEO_MAP,
)
from .cleaner import DataCleaner
from .database import DatabaseManager

logger = logging.getLogger(__name__)


class ZeptoScraper:
    """Async Playwright Zepto scraper with:

    - stealth patches
    - pincode + lat/lon geolocation injection
    - API interception for `/api/v1/layout/` and GraphQL
    - JSONL streaming into SQLite-backed intermediate buffer

    The engine is intentionally tolerant: if API payload extraction fails,
    it uses DOM fallbacks.
    """

    def __init__(self, db_manager: DatabaseManager, pincode: str = DEFAULT_PINCODE):
        self.db = db_manager
        self.pincode = str(pincode).strip() if pincode else DEFAULT_PINCODE

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._api_payload_products: List[dict] = []
        self.stats = {
            "products_scraped": 0,
            "products_failed": 0,
            "api_responses_captured": 0,
        }

        self.current_jsonl_path: Optional[Path] = None
        self.current_category_name: Optional[str] = None
        self.current_category_id: Optional[int] = None
        self.scraped_skus: set = set()
        self.scraped_namepack: set = set()
        self.category_products_scraped = 0

    async def __aenter__(self):
        await self._launch_browser()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._close_browser()
        return False

    async def _launch_browser(self):
        self._playwright = await async_playwright().start()

        viewport = get_random_viewport()
        user_agent = get_random_user_agent()

        logger.info(
            f"Launching browser | UA: {user_agent[:50]}... | Viewport: {viewport} | pincode={self.pincode}"
        )

        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-extensions",
                f"--window-size={viewport['width']},{viewport['height']}",
            ],
        )

        geo = PINCODE_GEO_MAP.get(self.pincode) or list(PINCODE_GEO_MAP.values())[0]

        # Note: Playwright needs permissions set for geolocation; we also
        # inject cookies/localStorage as a fuzzy fallback.
        self._context = await self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            bypass_csp=True,
            geolocation={"latitude": geo["lat"], "longitude": geo["lon"], "accuracy": 50},
            permissions=["geolocation"],
        )

        await self._context.add_init_script(
            """
            // webdriver masking
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // languages
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN','en-US','en'] });

            // plugins
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });

            // runtime signals
            window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}), app: { isInstalled: false } };
            """
        )

        # Cookie + localStorage injection for pincode gating on Zepto.
        await self._context.add_cookies(
            [
                {
                    "name": "pincode",
                    "value": self.pincode,
                    "domain": ".zepto.com",
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                },
                {
                    "name": "userPincode",
                    "value": self.pincode,
                    "domain": ".zepto.com",
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                },
            ]
        )

        self._page = await self._context.new_page()
        self._page.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
        self._page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)

        self._page.on("response", self._on_response)

    async def _close_browser(self):
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Browser cleanup error: {e}")

    async def _on_response(self, response: Response):
        try:
            url = response.url
            if not any(p in url for p in API_URL_PATTERNS):
                return
            if response.status != 200:
                return

            content_type = response.headers.get("content-type", "")
            if "json" not in content_type and "graphql" not in url.lower():
                return

            body = await response.json()
            products = self._extract_products_from_payload(body)
            if products:
                self._api_payload_products.extend(products)
                self.stats["api_responses_captured"] += 1
                logger.info(f"API intercepted: {len(products)} products from {url[:70]}")
        except Exception:
            # Tolerate failures; scraping can continue.
            return

    def _extract_products_from_payload(self, body: Any) -> List[dict]:
        if not body:
            return []
        candidates: List[Any] = []

        if isinstance(body, dict):
            for key in ["products", "items", "results", "data", "catalog", "layout"]:
                if key in body:
                    candidates.append(body.get(key))

            # GraphQL-like nested dicts
            data = body.get("data") if isinstance(body.get("data"), (dict, list)) else None
            if isinstance(data, dict):
                for k in ["products", "items", "catalog"]:
                    if k in data:
                        candidates.append(data.get(k))

        elif isinstance(body, list):
            candidates.append(body)

        # Flatten lists
        flattened: List[dict] = []
        for c in candidates:
            if isinstance(c, list):
                for el in c:
                    if isinstance(el, dict):
                        flattened.append(el)
            elif isinstance(c, dict):
                # one more nesting
                for v in c.values():
                    if isinstance(v, list):
                        for el in v:
                            if isinstance(el, dict):
                                flattened.append(el)

        return flattened

    async def _handle_pincode_injection(self):
        # Fuzzy: for some flows localStorage keys matter.
        try:
            await self._page.goto(BASE_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)

            geo = PINCODE_GEO_MAP.get(self.pincode) or list(PINCODE_GEO_MAP.values())[0]
            await self._page.evaluate(
                f"""
                localStorage.setItem('pincode', '{self.pincode}');
                localStorage.setItem('userPincode', '{self.pincode}');
                localStorage.setItem('deliveryPincode', '{self.pincode}');
                localStorage.setItem('selectedPincode', '{self.pincode}');
                """
            )
            await self._page.reload(wait_until="domcontentloaded")
            try:
                await self._page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT_MS)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Pincode injection init flow failed: {e}")

    def _get_jsonl_path(self, category_slug: str) -> Path:
        safe_slug = re.sub(r"[^\w\-]", "_", category_slug)
        return JSONL_EXPORT_DIR / f"{safe_slug}_{self.pincode}.jsonl"

    def _get_csv_path(self, category_slug: str) -> Path:
        safe_name = category_slug.replace("/", "_").replace("\\", "_")
        return CATEGORY_EXPORT_DIR / f"{safe_name}_{self.pincode}.csv"

    def _get_completion_path(self, category_slug: str) -> Path:
        safe_name = category_slug.replace("/", "_").replace("\\", "_")
        return CATEGORY_EXPORT_DIR / f"{safe_name}_{self.pincode}.completed"

    def _purge_stale_caches(self):
        # Weekly Run Cache Purging: delete .completed and .jsonl older than 24h.
        now = datetime.now().timestamp()
        cutoff = 24 * 3600

        for base in [CATEGORY_EXPORT_DIR, JSONL_EXPORT_DIR]:
            if not base.exists():
                continue
            for p in base.glob("*"):
                try:
                    if p.suffix not in (".jsonl", ".completed"):
                        continue
                    age = now - p.stat().st_mtime
                    if age > cutoff:
                        p.unlink(missing_ok=True)
                except Exception:
                    continue

    def _is_category_completed(self, category_slug: str) -> bool:
        marker = self._get_completion_path(category_slug)
        if not marker.exists():
            return False
        age = datetime.now().timestamp() - marker.stat().st_mtime
        if age > 24 * 3600:
            try:
                marker.unlink(missing_ok=True)
            except Exception:
                pass
            return False
        return True

    async def _stream_to_jsonl(self, product: dict, jsonl_path: Path):
        try:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                json.dump(product, f, ensure_ascii=False, default=str)
                f.write("\n")
        except Exception as e:
            logger.error(f"JSONL stream write failed: {e}")

    async def _process_api_products_batch(self, page: Page) -> int:
        """Convert intercepted API payloads into cleaned product rows.

        Zepto payload schemas can vary. This method is tolerant and only
        requires sku_id + product_name to be present after cleaning.
        """
        if not self._api_payload_products:
            return 0

        raw_products = self._api_payload_products
        self._api_payload_products = []

        new_saved = 0
        for raw in raw_products:
            try:
                cleaned = DataCleaner.clean_product_data(raw)

                sku = str(cleaned.get("sku_id") or "").strip()
                name = cleaned.get("product_name")
                pack_size = cleaned.get("pack_size")

                # IMPORTANT: some Zepto APIs provide title but not a stable sku_id.
                # We still allow DOM-level scraping to fill gaps by skipping here.
                if not sku or not name:
                    continue

                namepack = (str(name).strip().lower(), str(pack_size or "").strip().lower())
                if sku in self.scraped_skus or namepack in self.scraped_namepack:
                    continue

                if self.current_jsonl_path:
                    await self._stream_to_jsonl(cleaned, self.current_jsonl_path)

                cat_id = self.current_category_id
                if cat_id is None:
                    cat_id = self.db.resolve_category_path(
                        f"{cleaned.get('main_category') or 'Uncategorized'} > {cleaned.get('subcategory') or ''}".strip()
                    )

                ok = self.db.upsert_product(
                    {
                        **cleaned,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    category_id=cat_id,
                )

                if ok:
                    self.scraped_skus.add(sku)
                    self.scraped_namepack.add(namepack)
                    new_saved += 1

            except Exception:
                self.stats["products_failed"] += 1

        page.category_products_scraped += new_saved
        self.stats["products_scraped"] += new_saved
        return new_saved

    # NOTE: The implementation above is the only _process_api_products_batch.


    async def _extract_products_from_dom(self, page: Page) -> List[dict]:
        products = []

        # 1. Try to extract from #itemListSchema first (highly reliable SEO schema.org data)
        try:
            schema_el = await page.query_selector("#itemListSchema")
            if schema_el:
                content = await schema_el.inner_text()
                if content:
                    data = json.loads(content)
                    items = data.get("itemListElement", [])
                    for idx, list_item in enumerate(items):
                        item = list_item.get("item", {})
                        if not item:
                            continue

                        name = item.get("name")
                        url = item.get("url") or list_item.get("url")
                        image = item.get("image")

                        # Parse sku_id from URL
                        sku_id = None
                        if url:
                            pvid_match = re.search(r"pvid/([^/]+)", url)
                            if pvid_match:
                                sku_id = pvid_match.group(1)
                            else:
                                sku_id = url.split('/')[-1]

                        if not sku_id and name:
                            # fallback hash of name
                            sku_id = f"hash_{hash(name)}"

                        # Parse price
                        raw_price = item.get("offers", {}).get("price")
                        price = float(raw_price) / 100.0 if raw_price else None

                        # Parse availability
                        raw_avail = item.get("offers", {}).get("availability", "")
                        availability = 1 if "InStock" in str(raw_avail) else 0

                        products.append({
                            "sku_id": sku_id,
                            "product_name": name,
                            "product_url": url,
                            "image_url": image,
                            "selling_price": price,
                            "mrp": price,  # fallback to selling price
                            "availability": availability,
                        })

                    if products:
                        logger.info(f"[Schema] Successfully extracted {len(products)} products from #itemListSchema")
                        return products
        except Exception as e:
            logger.warning(f"Failed to parse #itemListSchema: {e}")

        # 2. Light DOM fallback.
        cards = []
        for sel in SELECTORS["product_card"]:
            try:
                found = await page.query_selector_all(sel)
                if found:
                    cards = found
                    break
            except Exception:
                continue
        if not cards:
            return products

        for card in cards:
            try:
                name_el = await card.query_selector(SELECTORS["product_name"][0])
                name = await name_el.inner_text() if name_el else None

                # sku: not reliable in DOM fallback.
                url_el = await card.query_selector("a[href*='/p/'], a[href*='/product/']")
                href = await url_el.get_attribute("href") if url_el else None

                sku_id = None
                if href:
                    m = re.findall(r"(\d{5,15})", href)
                    if m:
                        sku_id = m[-1]

                products.append(
                    {
                        "sku_id": sku_id,
                        "product_name": name,
                        "product_url": href,
                        "image_url": None,
                    }
                )
            except Exception:
                continue

        return products

    async def _process_dom_products_batch(self, page: Page) -> int:
        dom_products = await self._extract_products_from_dom(page)
        if not dom_products:
            return 0

        new_saved = 0
        for raw in dom_products:
            try:
                cleaned = DataCleaner.clean_product_data(raw)
                sku = str(cleaned.get("sku_id") or "").strip()
                name = cleaned.get("product_name")
                if not sku or not name:
                    continue

                namepack = (str(name).strip().lower(), str(cleaned.get("pack_size") or "").strip().lower())
                if sku in self.scraped_skus or namepack in self.scraped_namepack:
                    continue

                if self.current_jsonl_path:
                    await self._stream_to_jsonl(cleaned, self.current_jsonl_path)

                cat_id = self.current_category_id
                if cat_id is None:
                    cat_id = self.db.resolve_category_path(
                        f"{cleaned.get('main_category') or 'Uncategorized'} > {cleaned.get('subcategory') or ''}".strip()
                    )

                ok = self.db.upsert_product({**cleaned, "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, category_id=cat_id)
                if ok:
                    self.scraped_skus.add(sku)
                    self.scraped_namepack.add(namepack)
                    new_saved += 1
            except Exception:
                self.stats["products_failed"] += 1

        page.category_products_scraped += new_saved
        self.stats["products_scraped"] += new_saved
        return new_saved

    async def _scroll_to_load_all(self, page: Page):
        prev_height = 0
        no_change_count = 0
        scroll_count = 0
        max_no_change = 3

        while scroll_count < MAX_SCROLL_ATTEMPTS:
            scroll_count += 1

            curr_height = await page.evaluate("document.body.scrollHeight")

            if curr_height == prev_height:
                no_change_count += 1
            else:
                no_change_count = 0

            if no_change_count >= max_no_change:
                break

            await page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")

            # click load more if present
            for sel in SELECTORS["load_more_button"]:
                try:
                    loc = page.locator(sel)
                    if await loc.count() > 0 and await loc.first.is_visible():
                        await loc.first.click()
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(SCROLL_PAUSE_MS)

            # Incremental save from API interception
            saved_api = await self._process_api_products_batch(page)
            if saved_api:
                logger.info(f"[API] Incrementally saved {saved_api} products")
            else:
                # periodic DOM fallback
                if scroll_count % 5 == 0:
                    dom_saved = await self._process_dom_products_batch(page)
                    if dom_saved:
                        logger.info(f"[DOM] Incrementally saved {dom_saved} products")

            prev_height = curr_height

    async def scrape_category(self, category_url: str, category_name: str, category_slug: str, category_id: Optional[int] = None):
        # Weekly cache purge
        self._purge_stale_caches()

        if self._is_category_completed(category_slug):
            logger.info(f"[Skip] Zepto category '{category_name}' already completed (fresh marker).")
            return 0

        if not self._page:
            return 0
        page = self._page

        self.current_category_name = category_name
        self.current_category_id = category_id
        self.current_jsonl_path = self._get_jsonl_path(category_slug)
        page.category_products_scraped = 0
        self.scraped_skus.clear()
        self.scraped_namepack.clear()

        # stale marker purge for this category
        if self.current_jsonl_path.exists():
            try:
                age = datetime.now().timestamp() - self.current_jsonl_path.stat().st_mtime
                if age > 24 * 3600:
                    self.current_jsonl_path.unlink(missing_ok=True)
            except Exception:
                pass

        # Do NOT preload from old SQLite; only preload from fresh JSONL for crash recovery.
        if self.current_jsonl_path.exists():
            try:
                with open(self.current_jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            sku = str(data.get("sku_id") or "").strip()
                            name = data.get("product_name")
                            pack = data.get("pack_size")
                            if sku:
                                self.scraped_skus.add(sku)
                            if name:
                                self.scraped_namepack.add((name.strip().lower(), str(pack or "").strip().lower()))
                        except Exception:
                            continue
            except Exception:
                pass

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._api_payload_products = []
                page.category_products_scraped = 0

                resp = await page.goto(category_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
                if resp and resp.status in (403, 429):
                    cooldown = random.uniform(60.0, 120.0)
                    logger.warning(f"Rate limited on category. Cooling {cooldown:.1f}s (attempt {attempt}/{MAX_RETRIES})")
                    await asyncio.sleep(cooldown)
                    continue

                # Pincode injection is already run once at startup. Calling it here redirects the page away from category_url.

                # wait for some product cards to render
                try:
                    await page.wait_for_timeout(1500)
                except Exception:
                    pass

                await self._scroll_to_load_all(page)

                # final sweep
                await self._process_api_products_batch(page)
                await self._process_dom_products_batch(page)

                # completion checkpoint
                completion_path = self._get_completion_path(category_slug)
                try:
                    with open(completion_path, "w", encoding="utf-8") as cf:
                        json.dump(
                            {
                                "category_name": category_name,
                                "category_slug": category_slug,
                                "pincode": self.pincode,
                                "completed_at": datetime.now().isoformat(),
                                "products_scraped_this_run": page.category_products_scraped,
                            },
                            cf,
                            indent=2,
                        )
                except Exception:
                    pass

                csv_path = self._get_csv_path(category_slug)
                try:
                    self.db.export_master_csv(csv_path)
                except Exception:
                    pass

                return page.category_products_scraped

            except Exception as e:
                logger.error(f"Zepto category failed attempt {attempt}/{MAX_RETRIES}: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_S)
                else:
                    raise

    async def discover_categories(self) -> List[Dict[str, Any]]:
        logger.info(f"Discovering categories dynamically from {BASE_URL}...")
        discovered = []
        seen_urls = set()

        # Fallback list with new subcategory /cn/ URL patterns in case dynamic fetch fails
        fallback = [
            {
                "name": "Fresh Fruits",
                "slug": "fresh-fruits",
                "url": f"{BASE_URL}/cn/fruits-vegetables/fresh-fruits/cid/64374cfe-d06f-4a01-898e-c07c46462c36/scid/09e63c15-e5f7-4712-9ff8-513250b79942",
            },
            {
                "name": "Fresh Vegetables",
                "slug": "fresh-vegetables",
                "url": f"{BASE_URL}/cn/fruits-vegetables/fresh-vegetables/cid/64374cfe-d06f-4a01-898e-c07c46462c36/scid/b4827798-fcb6-4520-ba5b-0f2bd9bd7208",
            },
            {
                "name": "Atta",
                "slug": "atta",
                "url": f"{BASE_URL}/cn/atta-rice-oil-dals/atta/cid/2f7190d0-7c40-458b-b450-9a1006db3d95/scid/2b5e863c-9497-46ae-a7e9-85f6ef7380da",
            },
        ]

        if not self._page:
            return fallback

        try:
            await self._page.goto(BASE_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            await self._page.wait_for_timeout(3000)

            links = await self._page.query_selector_all("a")
            for link in links:
                href = await link.get_attribute("href")
                if not href:
                    continue

                # Only process product grid pages (/cn/)
                if "/cn/" in href:
                    full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)

                        # Extract name
                        name = (await link.inner_text()).strip()
                        slug = ""
                        parts = href.split('/')
                        idx_cn = parts.index("cn")
                        if len(parts) > idx_cn + 2:
                            slug = parts[idx_cn + 2]
                        elif len(parts) > idx_cn + 1:
                            slug = parts[idx_cn + 1]

                        if not name:
                            name = slug.replace("-", " ").title()

                        if not slug:
                            slug = "uncategorized"

                        discovered.append({
                            "name": name,
                            "slug": slug,
                            "url": full_url
                        })

            if discovered:
                logger.info(f"Successfully discovered {len(discovered)} categories dynamically.")
                return discovered

        except Exception as e:
            logger.warning(f"Dynamic category discovery failed: {e}. Using hardcoded fallback.")

        return fallback

    async def run(self, max_categories: Optional[int] = None, categories_to_scrape: Optional[List[str]] = None):
        logger.info(f"Zepto Scraper starting | pincode={self.pincode}")

        await self._handle_pincode_injection()
        categories = await self.discover_categories()

        if categories_to_scrape:
            # Always evaluate filter, but do not wipe categories.
            filt = []
            for c in categories:
                if any(
                    t.lower().strip() in c["name"].lower()
                    or t.lower().strip() in c["slug"].lower()
                for t in categories_to_scrape
                ):
                    filt.append(c)

            if not filt:
                logger.warning(
                    "Zepto engine category filter matched 0 categories; "
                    "falling back to all discovered categories. "
                    f"filter={categories_to_scrape}"
                )
            else:
                categories = filt



        if max_categories:
            categories = categories[: max_categories]

        # register categories in SQLite on-the-fly
        scraped = 0
        for idx, cat in enumerate(categories, 1):
            if self._is_category_completed(cat["slug"]):
                logger.info(f"[Skip] {cat['name']} already completed")
                continue

            logger.info(f"[{idx}/{len(categories)}] Scraping Zepto category: {cat['name']}")
            cat_id = None
            try:
                cat_id = self.db.upsert_category(cat["name"], None, 1, cat["name"])
            except Exception:
                cat_id = None

            count = await self.scrape_category(cat["url"], cat["name"], cat["slug"], category_id=cat_id)
            scraped += count

        logger.info(
            f"Zepto Scraper complete | categories={len(categories)} products={self.stats['products_scraped']} failed={self.stats['products_failed']}"
        )
        return scraped

