import asyncio
import json
import logging
import re
import random
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Set

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Response,
    Playwright,
)

from services.scrapers.blinkit_engine.config import (
    DEFAULT_PINCODE,
    USER_AGENTS,
    PRODUCT_BATCH_SIZE,
)
from services.scrapers.blinkit_engine.database_sync import BlinkitDatabaseSync
from services.scrapers.blinkit_engine.progress_tracker import BlinkitProgressTracker

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Generate URL-safe slug from text."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


class BlinkitPlaywrightScraper:
    """
    Playwright-based scraper for Blinkit.
    Loads category/product pages, sets pincode, scrolls, intercepts APIs,
    and batch syncs records to MySQL.
    """

    def __init__(
        self,
        db_sync: BlinkitDatabaseSync,
        pincode: str = DEFAULT_PINCODE,
        tracker: Optional[BlinkitProgressTracker] = None,
        task_id: Optional[int] = None,
    ):
        self.db = db_sync
        self.pincode = pincode
        self.tracker = tracker
        self.task_id = task_id

        # Playwright elements
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # API intercept buffers
        self._intercepted_products: List[Dict] = []
        self._intercepted_categories: List[Dict] = []

        # Scrape state variables
        self.current_category_name: Optional[str] = None
        self.current_subcategory_name: Optional[str] = None
        self.current_parent_id: Optional[int] = None
        self.current_category_id: Optional[int] = None
        self.on_product_scraped_callback: Optional[Callable] = None

        # Deduplication cache per category run
        self.scraped_product_ids: Set[int] = set()

    # ── Context Manager ────────────────────────────────────────────────────────

    async def __aenter__(self):
        await self._launch_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_browser()
        return False

    async def _launch_browser(self):
        self._playwright = await async_playwright().start()

        # Stealth browser setup
        user_agent = random.choice(USER_AGENTS)
        logger.info(f"[Playwright] Launching browser | UA: {user_agent[:60]}...")

        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-extensions",
            ],
        )

        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=user_agent,
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            bypass_csp=True,
        )

        # Remove navigator.webdriver flag
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: { isInstalled: false },
            };
        """)

        self._page = await self._context.new_page()
        self._page.set_default_timeout(30000)
        self._page.set_default_navigation_timeout(30000)

        # Attach network response interceptor
        self._page.on("response", self._on_response)
        logger.info("[Playwright] Browser launched and configured.")

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
            logger.info("[Playwright] Browser shut down successfully.")
        except Exception as e:
            logger.warning(f"[Playwright] Error closing browser: {e}")

    # ── Location Handling ──────────────────────────────────────────────────────

    async def set_pincode_location(self) -> bool:
        """Sets delivery location using Blinkit's UI input automation."""
        logger.info(f"[Playwright] Loading homepage to set pincode: {self.pincode}...")
        try:
            await self._page.goto("https://blinkit.com", wait_until="domcontentloaded")
            await self._page.wait_for_timeout(3000)

            # Check location trigger button
            detect_btn = self._page.locator("button:has-text('Detect my location'), button:has-text('Select Location')")
            if await detect_btn.count() > 0:
                await detect_btn.first.click()
                await self._page.wait_for_timeout(2000)

            # Locate pincode input
            pincode_input = self._page.locator("input[placeholder*='pincode'], input[placeholder*='location'], input[placeholder*='address']")
            if await pincode_input.count() > 0:
                await pincode_input.first.fill(self.pincode)
                await self._page.wait_for_timeout(2000)
                await pincode_input.first.press("Enter")
                await self._page.wait_for_timeout(3000)
                logger.info(f"[Playwright] Pincode {self.pincode} submitted successfully.")
                return True
            else:
                logger.warning("[Playwright] Pincode input field not found on homepage.")
                return False
        except Exception as e:
            logger.error(f"[Playwright] Failed to set location: {e}", exc_info=True)
            return False

    # ── Response Interceptor ───────────────────────────────────────────────────

    async def _on_response(self, response: Response):
        url = response.url
        if "blinkit.com" not in url:
            return

        try:
            if response.status == 200:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    # Target 1: Products listing
                    if "listing_widgets" in url:
                        data = await response.json()
                        snippets = data.get("response", {}).get("snippets", [])
                        if snippets:
                            logger.info(f"[Playwright] Intercepted {len(snippets)} snippets from listing_widgets.")
                            self._intercepted_products.extend(snippets)

                    # Target 2: Categories sidebar list
                    elif "v1/layout/listing" in url and "listing_widgets" not in url:
                        data = await response.json()
                        snippets = data.get("response", {}).get("snippets", [])
                        # Extract subcategory items
                        subcategories = []
                        for snippet in snippets:
                            widget_type = snippet.get("widget_type", "")
                            if "vertical_image_text_selectable" in widget_type:
                                subcategories.append(snippet)
                        if subcategories:
                            logger.info(f"[Playwright] Intercepted {len(subcategories)} subcategories from layout listing.")
                            self._intercepted_categories.extend(subcategories)
        except Exception as e:
            logger.debug(f"[Playwright] Network interception read skipped: {e}")

    # ── Category Discovery ─────────────────────────────────────────────────────

    async def discover_categories(self) -> List[Dict[str, Any]]:
        """
        Discovers all categories from homepage and category sidebar.
        Returns a flat list of category records matching the blinkit_mapping schema.
        """
        logger.info("[Playwright] Starting Category Discovery...")
        homepage_categories = []

        try:
            # Step 1: Scan homepage links
            links = await self._page.query_selector_all("a")
            seen_parent_ids = set()

            for link in links:
                href = await link.get_attribute("href")
                text = (await link.inner_text()).strip()

                if href and "/cn/" in href and "/cid/" in href:
                    # Match /cn/slug/cid/parent_id/category_id
                    match = re.search(r"/cid/(\d+)/(\d+)", href)
                    if match:
                        parent_id = int(match.group(1))
                        category_id = int(match.group(2))

                        homepage_categories.append({
                            "parent_id": parent_id,
                            "category_id": category_id,
                            "text": text,
                            "href": href
                        })
                        seen_parent_ids.add(parent_id)

            logger.info(f"[Playwright] Scanned {len(homepage_categories)} link candidates from homepage. Found {len(seen_parent_ids)} unique parent category IDs.")

            # Step 2: Visit one subcategory link per parent_id to intercept all of its siblings
            category_tree = []
            visited_parents = set()

            for item in homepage_categories:
                p_id = item["parent_id"]
                if p_id in visited_parents:
                    continue

                visited_parents.add(p_id)
                self._intercepted_categories.clear()

                full_url = f"https://blinkit.com{item['href']}"
                logger.info(f"[Playwright] Navigating to {full_url} to intercept parent_id={p_id} sidebar subcategories...")

                try:
                    await self._page.goto(full_url, wait_until="domcontentloaded")
                    await self._page.wait_for_timeout(4000)

                    # Get parent category name from breadcrumb or page title
                    parent_name = "Category"
                    try:
                        title_el = await self._page.query_selector("h1, nav[aria-label='breadcrumb'] li, title")
                        if title_el:
                            parent_name = (await title_el.inner_text()).strip()
                    except Exception:
                        pass

                    if "online" in parent_name.lower() or "buy" in parent_name.lower():
                        parent_name = item["text"]

                    # Add level 1 parent record
                    category_tree.append({
                        "category_id": p_id,
                        "category_name": parent_name,
                        "slug": slugify(parent_name),
                        "parent_id": 0,
                        "category_level": 1,
                        "full_category_path": parent_name
                    })

                    # Add level 2 subcategory records from intercepted v1/layout/listing API call
                    if self._intercepted_categories:
                        for sub_snippet in self._intercepted_categories:
                            tracking = sub_snippet.get("tracking", {})
                            sub_id_str = tracking.get("widget_meta", {}).get("widget_id")
                            sub_name = tracking.get("widget_meta", {}).get("widget_title")

                            if sub_id_str and sub_name:
                                sub_id = int(sub_id_str)
                                category_tree.append({
                                    "category_id": sub_id,
                                    "category_name": sub_name,
                                    "slug": slugify(sub_name),
                                    "parent_id": p_id,
                                    "category_level": 2,
                                    "full_category_path": f"{parent_name} > {sub_name}"
                                })
                    else:
                        # Fallback: add the single subcategory from the link itself
                        category_tree.append({
                            "category_id": item["category_id"],
                            "category_name": item["text"],
                            "slug": slugify(item["text"]),
                            "parent_id": p_id,
                            "category_level": 2,
                            "full_category_path": f"{parent_name} > {item['text']}"
                        })

                except Exception as visit_err:
                    logger.error(f"[Playwright] Failed to load sidebar for parent {p_id}: {visit_err}")

            return category_tree

        except Exception as e:
            logger.error(f"[Playwright] Category discovery failed: {e}", exc_info=True)
            return []

    # ── Product Extraction & Parsing ──────────────────────────────────────────

    def parse_snippet_product(self, snippet: Dict) -> Optional[Dict]:
        """Parses a single listing widget product snippet into a clean dict."""
        data = snippet.get("data", {})
        tracking = snippet.get("tracking", {})
        common = tracking.get("common_attributes", {})
        click_map = tracking.get("click_map", {})

        # product_id
        product_id = data.get("product_id") or common.get("product_id") or click_map.get("product_id")
        if not product_id:
            product_id = data.get("identity", {}).get("id")
        if not product_id:
            return None

        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return None

        # product_name
        product_name = common.get("name") or click_map.get("name")
        if not product_name:
            display_name = data.get("display_name") or {}
            product_name = display_name.get("text") if isinstance(display_name, dict) else display_name
        if not product_name:
            name_obj = data.get("name") or {}
            product_name = name_obj.get("text") if isinstance(name_obj, dict) else name_obj
        if not product_name:
            return None
        product_name = str(product_name).strip()

        # brand
        brand = common.get("brand") or click_map.get("brand") or ""
        brand = str(brand).strip()

        # price & mrp
        price = common.get("price") or click_map.get("price") or data.get("normal_price")
        mrp = common.get("mrp") or click_map.get("mrp") or data.get("mrp")

        if price is None:
            return None

        try:
            price = float(price)
            mrp = float(mrp) if mrp is not None else price
        except (ValueError, TypeError):
            return None

        discount = max(0.0, mrp - price)

        # quantity / weight / volume
        quantity = data.get("variant", {}).get("text") if isinstance(data.get("variant"), dict) else data.get("variant")
        if not quantity:
            dec_actions = snippet.get("decrement_actions", {})
            default_actions = dec_actions.get("default", [])
            if default_actions:
                cart_item = default_actions[0].get("remove_from_cart", {}).get("cart_item", {})
                quantity = cart_item.get("unit")
        if quantity:
            quantity = str(quantity).strip()

        # availability
        is_sold_out = data.get("is_sold_out")
        if is_sold_out is not None:
            availability = not is_sold_out
        else:
            state = click_map.get("state") or tracking.get("impression_map", {}).get("state")
            if state:
                availability = (state == "available")
            else:
                availability = True

        # image_url
        image_url = data.get("image", {}).get("url") if isinstance(data.get("image"), dict) else data.get("image")
        if not image_url:
            media_items = data.get("media_container", {}).get("items", [])
            if media_items:
                image_url = media_items[0].get("image", {}).get("url")
        if image_url:
            image_url = str(image_url).strip()

        # product_url
        product_url = f"https://blinkit.com/prn/item/prid/{product_id}"

        return {
            "product_id": product_id,
            "product_name": product_name,
            "brand": brand if brand else None,
            "category": self.current_category_name,
            "sub_category": self.current_subcategory_name,
            "price": price,
            "mrp": mrp,
            "discount": discount,
            "quantity": quantity if quantity else None,
            "availability": 1 if availability else 0,
            "image_url": image_url if image_url else None,
            "product_url": product_url,
        }

    # ── Product Scraping & Infinite Scroll ─────────────────────────────────────

    async def scrape_subcategory_products(
        self,
        parent_id: int,
        subcategory_id: int,
        parent_name: str,
        subcategory_name: str,
        on_product_batch: Callable[[List[Dict], int], None],
    ) -> int:
        """
        Navigates to a subcategory listing page, performs infinite scroll,
        intercepts JSON product payloads, and issues callback for batches.
        """
        self.current_parent_id = parent_id
        self.current_category_id = subcategory_id
        self.current_category_name = parent_name
        self.current_subcategory_name = subcategory_name

        self._intercepted_products.clear()
        self.scraped_product_ids.clear()

        sub_slug = slugify(subcategory_name)
        url = f"https://blinkit.com/cn/{sub_slug}/cid/{parent_id}/{subcategory_id}"
        logger.info(f"[Playwright] Scraping products from subcategory page: {url}")

        try:
            await self._page.goto(url, wait_until="domcontentloaded")
            await self._page.wait_for_timeout(3000)

            # Scroll loop
            prev_height = 0
            no_change = 0
            scrolls = 0
            max_scrolls = 60  # Safe cap per subcategory

            buffered_products = []

            while scrolls < max_scrolls:
                scrolls += 1
                curr_height = await self._page.evaluate("document.body.scrollHeight")

                # Scroll down
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await self._page.wait_for_timeout(3000)

                # Process any newly intercepted API snippets in real time
                if self._intercepted_products:
                    current_batch = list(self._intercepted_products)
                    self._intercepted_products.clear()

                    new_products = []
                    for snip in current_batch:
                        prod = self.parse_snippet_product(snip)
                        if prod:
                            p_id = prod["product_id"]
                            if p_id not in self.scraped_product_ids:
                                self.scraped_product_ids.add(p_id)
                                new_products.append(prod)

                    if new_products:
                        buffered_products.extend(new_products)
                        if len(buffered_products) >= PRODUCT_BATCH_SIZE:
                            on_product_batch(buffered_products, subcategory_id)
                            buffered_products.clear()

                # Stagnation termination check
                if curr_height == prev_height:
                    no_change += 1
                    if no_change >= 3:
                        logger.info(f"[Playwright] Scrolling finished. Page height stable at {curr_height}px.")
                        break
                else:
                    no_change = 0
                prev_height = curr_height

            # Flush remaining items
            if buffered_products:
                on_product_batch(buffered_products, subcategory_id)
                buffered_products.clear()

            # Final sweeps
            if self._intercepted_products:
                new_products = []
                for snip in self._intercepted_products:
                    prod = self.parse_snippet_product(snip)
                    if prod:
                        p_id = prod["product_id"]
                        if p_id not in self.scraped_product_ids:
                            self.scraped_product_ids.add(p_id)
                            new_products.append(prod)
                if new_products:
                    on_product_batch(new_products, subcategory_id)
                self._intercepted_products.clear()

            logger.info(f"[Playwright] Subcategory '{subcategory_name}' scrape complete. Scraped {len(self.scraped_product_ids)} products.")
            return len(self.scraped_product_ids)

        except Exception as e:
            logger.error(f"[Playwright] Error scraping subcategory '{subcategory_name}': {e}", exc_info=True)
            return 0
