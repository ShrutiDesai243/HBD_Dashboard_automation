# ============================================================
# DMart Web Scraper — Core Scraper Module
# ============================================================
# Async Playwright-based scraper with stealth integration,
# pincode injection, infinite scroll handling, API response
# interception, and streaming JSONL output.
# ============================================================

import asyncio
import json
import csv
import random
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Response,
    Playwright,
)

from .config import (
    BASE_URL,
    DEFAULT_PINCODE,
    SELECTORS,
    SCROLL_PAUSE_MS,
    SCROLL_TIMEOUT_MS,
    MAX_SCROLL_ATTEMPTS,
    NETWORK_IDLE_TIMEOUT_MS,
    PAGE_LOAD_TIMEOUT_MS,
    MAX_RETRIES,
    RETRY_DELAY_S,
    REQUEST_DELAY_RANGE,
    EXPORT_DIR,
    CATEGORY_EXPORT_DIR,
    JSONL_EXPORT_DIR,
    get_random_user_agent,
    get_random_viewport,
)
from .cleaner import DataCleaner
from .database import DatabaseManager

logger = logging.getLogger(__name__)


class DMartScraper:
    """
    Production-grade async web scraper for DMart (dmart.in).
    
    Architecture:
        - Uses Playwright in async mode with stealth patches
        - Intercepts internal API responses for structured JSON data
        - Falls back to DOM scraping if API interception fails
        - Streams cleaned data to JSONL in real-time (crash recovery)
        - Converts JSONL → CSV per category on completion
        - Loads verified data into SQLite via DatabaseManager
    
    Usage:
        async with DMartScraper(db_manager) as scraper:
            await scraper.run()
    """

    def __init__(self, db_manager: DatabaseManager, pincode: str = DEFAULT_PINCODE):
        """
        Initialize the scraper.
        
        Args:
            db_manager: DatabaseManager instance for SQLite operations.
            pincode: Delivery pincode for location gating (default: 400001).
        """
        self.db = db_manager
        self.pincode = pincode

        # Playwright instances (initialized in __aenter__)
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # API response interception buffer
        self._api_products: List[dict] = []
        self._api_categories: List[dict] = []

        # Scraping statistics
        self.stats = {
            'categories_scraped': 0,
            'products_scraped': 0,
            'products_failed': 0,
            'api_responses_captured': 0,
        }

        # Resumability & Incremental processing state
        self.current_category_id: Optional[int] = None
        self.current_category_name: Optional[str] = None
        self.current_jsonl_path: Optional[Path] = None
        self.scraped_skus: set = set()
        self.scraped_names: set = set()
        self._category_products_scraped = 0


    # ── Context Manager Protocol ──────────────────────────────

    async def __aenter__(self):
        """Async context manager entry: launch browser."""
        await self._launch_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit: always close browser."""
        await self._close_browser()
        return False

    # ── Browser Lifecycle ─────────────────────────────────────

    async def _launch_browser(self):
        """
        Launch a stealth Chromium browser with anti-detection patches.
        
        Applies:
            - Random user agent and viewport
            - WebDriver flag removal
            - Navigator property masking
            - Disabled automation signals
        """
        self._playwright = await async_playwright().start()

        viewport = get_random_viewport()
        user_agent = get_random_user_agent()

        logger.info(f"Launching browser | UA: {user_agent[:50]}... | Viewport: {viewport}")

        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--disable-extensions',
                f'--window-size={viewport["width"]},{viewport["height"]}',
            ]
        )

        self._context = await self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale='en-IN',
            timezone_id='Asia/Kolkata',
            # Stealth: mask webdriver detection
            java_script_enabled=True,
            bypass_csp=True,
            extra_http_headers={
                'Accept-Language': 'en-IN,en;q=0.9,hi;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
        )

        # ── Stealth Patches ──
        # Remove navigator.webdriver flag and mask automation signals
        await self._context.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: { isInstalled: false },
            };
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-IN', 'en-US', 'en'],
            });
            
            // Mask platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
            });
        """)

        self._page = await self._context.new_page()

        # Set default navigation timeout
        self._page.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
        self._page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)

        # ── Register API response interceptor ──
        self._page.on('response', self._on_response)

        logger.info("Browser launched with stealth patches applied.")

    async def _close_browser(self):
        """Gracefully close all Playwright resources."""
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("Browser closed successfully.")
        except Exception as e:
            logger.warning(f"Error during browser cleanup: {e}")

    # ── API Response Interception ─────────────────────────────

    async def _on_response(self, response: Response, page: Optional[Page] = None):
        """
        Intercept DMart's internal API responses to capture
        structured JSON product data directly.
        
        Targets:
            - /api/v1/clp/   (Category Listing Page)
            - /api/v1/search (Search Result Page)
        """
        url = response.url
        if "/api/v" not in url.lower() and "clp" not in url.lower() and "search" not in url.lower():
            return

        # Ignore promotional components and non-product data
        if any(skip in url.lower() for skip in ['espots', 'footer', 'header', 'menu', 'banner']):
            return

        try:
            if response.status == 200:
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type or 'javascript' in content_type:
                    body = await response.json()

                    # Extract products from various response shapes
                    products = []
                    if isinstance(body, dict):
                        # Try common response shapes
                        products = (
                            body.get('products', [])
                            or body.get('data', {}).get('products', [])
                            or body.get('results', [])
                            or body.get('items', [])
                            or body.get('data', {}).get('items', [])
                        )

                        # Capture category data if present
                        categories = (
                            body.get('categories', [])
                            or body.get('data', {}).get('categories', [])
                        )
                        if categories:
                            self._api_categories.extend(categories)

                    if products:
                        target_page = page if page is not None else self._page
                        if target_page and hasattr(target_page, 'api_products'):
                            target_page.api_products.extend(products)
                        else:
                            self._api_products.extend(products)
                            
                        self.stats['api_responses_captured'] += 1
                        logger.info(
                            f"API intercepted: {len(products)} products from {url[:80]}"
                        )

        except Exception as e:
            # Non-critical: log and continue
            logger.debug(f"API interception skipped for {url[:60]}: {e}")

    # ── Pincode Injection ─────────────────────────────────────

    async def _handle_pincode_popup(self, page: Optional[Page] = None):
        """
        Handle DMart's location gating popup.
        
        Strategy (ordered by reliability):
            1. Inject localStorage/cookies directly (fastest)
            2. Interact with the pincode popup UI (fallback)
        """
        active_page = page if page is not None else self._page
        logger.info(f"Handling pincode injection: {self.pincode}")

        try:
            # ── Strategy 1: Direct storage injection ──
            # Set localStorage values that DMart uses for location
            await active_page.evaluate(f"""
                localStorage.setItem('pincode', '{self.pincode}');
                localStorage.setItem('userPincode', '{self.pincode}');
                localStorage.setItem('selectedPincode', '{self.pincode}');
                localStorage.setItem('deliveryPincode', '{self.pincode}');
                localStorage.setItem('location', JSON.stringify({{
                    "pincode": "{self.pincode}",
                    "city": "Mumbai",
                    "state": "Maharashtra"
                }}));
                localStorage.setItem('user_location', JSON.stringify({{
                    "pincode": "{self.pincode}"
                }}));
            """)

            # Set cookies for pincode
            await self._context.add_cookies([
                {
                    'name': 'pincode',
                    'value': self.pincode,
                    'domain': '.dmart.in',
                    'path': '/',
                },
                {
                    'name': 'userPincode',
                    'value': self.pincode,
                    'domain': '.dmart.in',
                    'path': '/',
                },
                {
                    'name': 'deliveryPincode',
                    'value': self.pincode,
                    'domain': '.dmart.in',
                    'path': '/',
                },
            ])

            logger.info("Pincode injected via localStorage + cookies.")

            # Reload page to apply the location change
            await active_page.reload(wait_until='domcontentloaded')
            await active_page.wait_for_timeout(2000)

            # ── Strategy 2: UI interaction (fallback) ──
            # Check if the popup is still visible
            popup_visible = False
            for selector in SELECTORS['pincode_input'].split(', '):
                try:
                    locator = active_page.locator(selector)
                    if await locator.count() > 0 and await locator.first.is_visible():
                        popup_visible = True
                        # Type pincode into the input
                        await locator.first.fill(self.pincode)
                        await active_page.wait_for_timeout(500)

                        # Click submit button
                        for btn_sel in SELECTORS['pincode_submit'].split(', '):
                            try:
                                btn = active_page.locator(btn_sel)
                                if await btn.count() > 0 and await btn.first.is_visible():
                                    await btn.first.click()
                                    logger.info("Pincode submitted via UI popup.")
                                    break
                            except Exception:
                                continue

                        await active_page.wait_for_timeout(3000)
                        break
                except Exception:
                    continue

            if not popup_visible:
                logger.info("No pincode popup detected — location already set.")

            # Final wait for page to settle with new location
            try:
                await active_page.wait_for_load_state('networkidle', timeout=NETWORK_IDLE_TIMEOUT_MS)
            except Exception:
                logger.debug("Network idle timeout after pincode — continuing.")

        except Exception as e:
            logger.error(f"Pincode injection failed: {e}")
            # Don't raise — attempt to continue anyway

    # ── Category Discovery ────────────────────────────────────

    async def debug_pdp(self, url: str):
        """Debug method to load a PDP with pincode bypassed and dump HTML."""
        logger.info(f"Navigating to PDP: {url}")
        await self._page.goto(url, wait_until='domcontentloaded')
        await self._handle_pincode_popup()
        await self._page.wait_for_timeout(3000)
        html = await self._page.content()
        with open(EXPORT_DIR / "debug_pdp.html", "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("Dumped PDP HTML.")
        
    async def discover_categories(self) -> List[Dict[str, Any]]:
        """
        Discover product categories from DMart's navigation menu.
        
        Strategy:
            1. Try to intercept category API responses
            2. Fall back to parsing DOM navigation links
            3. Use known category URL patterns as last resort
            
        Returns:
            List of category dicts with name, slug, url, level, parent.
        """
        logger.info("Discovering categories from navigation...")
        categories = []

        try:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    # Navigate to homepage
                    response = await self._page.goto(
                        BASE_URL,
                        wait_until='domcontentloaded',
                        timeout=PAGE_LOAD_TIMEOUT_MS
                    )

                    # ── Rate Limit / Forbidden Backoff ──
                    if response and response.status in [403, 429]:
                        cooldown = random.uniform(60.0, 120.0)
                        logger.warning(
                            f"403 Forbidden/Rate Limited on Homepage! "
                            f"Cooling down for {cooldown:.1f}s... (Attempt {attempt}/{MAX_RETRIES})"
                        )
                        await asyncio.sleep(cooldown)
                        continue  # Retry this attempt

                    await self._handle_pincode_popup()

                    # Wait for navigation to render
                    await self._page.wait_for_timeout(3000)
                    break  # Success — exit retry loop
                except Exception as e:
                    logger.error(f"Homepage navigation error on attempt {attempt}: {e}")
                    if attempt == MAX_RETRIES:
                        logger.warning("Max retries reached for homepage navigation. Falling back to default categories.")
                    else:
                        await asyncio.sleep(RETRY_DELAY_S)


            # ── Try API-intercepted categories ──
            if self._api_categories:
                logger.info(f"Found {len(self._api_categories)} categories from API.")
                for cat in self._api_categories:
                    categories.append({
                        'name': cat.get('name') or cat.get('category_name', ''),
                        'slug': cat.get('slug', ''),
                        'url': cat.get('url', ''),
                        'level': cat.get('level', 1),
                        'parent': cat.get('parent', ''),
                        'children': cat.get('children', []),
                    })

            # ── Parse DOM navigation links ──
            if not categories:
                logger.info("Parsing categories from DOM navigation...")

                # Try multiple selector strategies for category links
                link_selectors = [
                    'a[href*="/category/"]',
                    'nav a[href*="/"]',
                    '[class*="menu"] a[href*="/"]',
                    '[class*="categ"] a',
                    '[class*="nav"] a[href*="/category"]',
                ]

                seen_urls = set()
                for selector in link_selectors:
                    try:
                        links = await self._page.query_selector_all(selector)
                        for link in links:
                            href = await link.get_attribute('href') or ''
                            text = (await link.inner_text()).strip()

                            if not href or not text:
                                continue
                            if href in seen_urls:
                                continue
                            if any(skip in href.lower() for skip in [
                                'cart', 'login', 'profile', 'order',
                                'checkout', '#', 'javascript'
                            ]):
                                continue

                            seen_urls.add(href)
                            slug = href.rstrip('/').split('/')[-1]

                            # Determine level from URL depth
                            parts = [p for p in href.split('/') if p and p != 'category']
                            level = min(len(parts), 3)

                            categories.append({
                                'name': text,
                                'slug': slug,
                                'url': href if href.startswith('http') else f"{BASE_URL}{href}",
                                'level': level,
                                'parent': '',
                            })
                    except Exception as e:
                        logger.debug(f"Selector '{selector}' failed: {e}")

            # ── Fallback: Known DMart categories ──
            if not categories:
                logger.warning("Using fallback category list.")
                categories = self._get_fallback_categories()

            logger.info(f"Total categories discovered: {len(categories)}")
            return categories

        except Exception as e:
            logger.error(f"Category discovery failed: {e}")
            return self._get_fallback_categories()

    def _get_fallback_categories(self) -> List[Dict[str, Any]]:
        """
        Hardcoded fallback category list based on known DMart structure.
        Used only when dynamic discovery fails.
        """
        known_categories = [
            {"name": "Food & Gourmet", "slug": "food-and-gourmet", "level": 1},
            {"name": "Grocery & Staples", "slug": "grocery-and-staples", "level": 1},
            {"name": "Dairy & Frozen", "slug": "dairy-and-frozen", "level": 1},
            {"name": "Personal Care", "slug": "personal-care", "level": 1},
            {"name": "Home Care", "slug": "home-care", "level": 1},
            {"name": "Home & Kitchen", "slug": "home-and-kitchen", "level": 1},
            {"name": "Fruits & Vegetables", "slug": "fruits-and-vegetables", "level": 1},
            {"name": "Beverages", "slug": "beverages", "level": 1},
            {"name": "Baby Care", "slug": "baby-care", "level": 1},
            {"name": "Bed & Bath", "slug": "bed-and-bath", "level": 1},
            {"name": "Footwear", "slug": "footwear", "level": 1},
            {"name": "Men's Apparel", "slug": "mens-apparel", "level": 1},
            {"name": "Women's Apparel", "slug": "womens-apparel", "level": 1},
            {"name": "Toys & Games", "slug": "toys-and-games", "level": 1},
        ]

        return [
            {
                **cat,
                'url': f"{BASE_URL}/category/{cat['slug']}",
                'parent': '',
            }
            for cat in known_categories
        ]

    # ── Infinite Scroll ───────────────────────────────────────

    async def _scroll_to_load_all(self, page: Optional[Page] = None):
        """
        Robust infinite scroll implementation.
        
        Algorithm:
            1. Scroll to page bottom
            2. Compare page height and product card counts before/after scroll
            3. Repeat until height is unchanged or product counts stagnate
            4. Safety cap at MAX_SCROLL_ATTEMPTS iterations
        """
        active_page = page if page is not None else self._page
        logger.info("Starting infinite scroll to load all products...")

        prev_height = 0
        no_change_count = 0
        scroll_count = 0
        max_no_change = 3  # How many times height can stay same before stopping

        # Smart Stagnation Check tracking variables
        last_card_count = 0
        stagnant_scroll_count = 0

        while scroll_count < MAX_SCROLL_ATTEMPTS:
            scroll_count += 1

            # Get current page height
            curr_height = await active_page.evaluate("document.body.scrollHeight")

            # ── Smart Card Stagnation Check ──
            card_count = await self._count_product_cards(active_page)
            api_has_items = False
            if active_page is not None:
                api_products_list = getattr(active_page, 'api_products', None)
                if api_products_list:
                    api_has_items = True
            else:
                if self._api_products:
                    api_has_items = True

            if card_count > 0 and card_count == last_card_count:
                stagnant_scroll_count += 1
                # If product card count remains completely identical for 2 consecutive scrolls,
                # and no new intercepted API products are pending, exit early.
                if stagnant_scroll_count >= 2 and not api_has_items:
                    logger.info(
                        f"Smart scroll exit: product card count remained stagnant at {card_count} "
                        f"for 2 consecutive scrolls and no new API products are intercepted."
                    )
                    break
            else:
                stagnant_scroll_count = 0

            last_card_count = card_count

            if curr_height == prev_height:
                no_change_count += 1
                if no_change_count >= max_no_change:
                    logger.info(
                        f"Scroll complete: height stable at {curr_height}px "
                        f"after {scroll_count} scrolls."
                    )
                    break
            else:
                no_change_count = 0

            prev_height = curr_height

            # Scroll to bottom with smooth behavior
            await active_page.evaluate(
                "window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })"
            )

            # Check for 'Load More' button and click if present
            for selector in SELECTORS['load_more_button'].split(', '):
                try:
                    locator = active_page.locator(selector)
                    if await locator.count() > 0 and await locator.first.is_visible():
                        await locator.first.click()
                        logger.info("Clicked 'Load More' button to continue scrolling.")
                        no_change_count = 0  # Reset stagnation counter
                        break
                except Exception:
                    continue

            # Pause for React rendering (Network idle wait eliminated for maximum speed)
            await active_page.wait_for_timeout(SCROLL_PAUSE_MS)

            # ── Incremental Saving ──
            # Process any intercepted API products immediately to free up memory and save progress
            if active_page is not None and getattr(active_page, 'api_products', None):
                api_saved = await self._process_and_save_api_products(active_page)
                if api_saved > 0:
                    logger.info(f"Incrementally saved {api_saved} new products from API interception.")
            elif active_page is None and self._api_products:
                api_saved = await self._process_and_save_api_products()
                if api_saved > 0:
                    logger.info(f"Incrementally saved {api_saved} new products from API interception.")
            
            # If no API products have been captured, and DOM fallback is likely active, 
            # process DOM products periodically (every 5 scrolls)
            elif scroll_count % 5 == 0:
                dom_saved = await self._process_and_save_dom_products(active_page)
                if dom_saved > 0:
                    logger.info(f"Incrementally saved {dom_saved} new products from DOM fallback.")

            if scroll_count % 10 == 0:
                product_count = await self._count_product_cards(active_page)
                logger.info(
                    f"Scroll #{scroll_count}: {product_count} products loaded, "
                    f"height={curr_height}px"
                )

        logger.info(f"Infinite scroll finished after {scroll_count} iterations.")

    async def _count_product_cards(self, page: Optional[Page] = None) -> int:
        """Count the number of product cards currently in the DOM."""
        active_page = page if page is not None else self._page
        for selector in SELECTORS['product_card'].split(', '):
            try:
                count = await active_page.locator(selector).count()
                if count > 0:
                    return count
            except Exception:
                continue
        return 0

    # ── Product Extraction ────────────────────────────────────

    async def _extract_products_from_dom(self, page: Optional[Page] = None) -> List[dict]:
        """
        Extract product data from DOM elements on the current page.
        
        Uses aggressive try/except per product card — if one card
        fails to parse, logs the error and moves to the next.
        
        Returns:
            List of raw product dictionaries.
        """
        active_page = page if page is not None else self._page
        products = []

        # Find product cards using multiple selector strategies
        cards = []
        for selector in SELECTORS['product_card'].split(', '):
            try:
                found = await active_page.query_selector_all(selector.strip())
                if found:
                    cards = found
                    logger.info(f"Found {len(cards)} product cards via '{selector.strip()}'")
                    break
            except Exception:
                continue

        if not cards:
            logger.warning("No product cards found in DOM. Dumping HTML for debugging.")
            html = await active_page.content()
            with open(EXPORT_DIR / "debug_dom.html", "w", encoding="utf-8") as f:
                f.write(html)
            return products

        for idx, card in enumerate(cards):
            try:
                product = await self._extract_single_product(card)
                if product and product.get('product_name'):
                    products.append(product)
                else:
                    self.stats['products_failed'] += 1

            except Exception as e:
                # ── Critical: Never crash the loop for a single card ──
                logger.warning(f"Failed to parse product card #{idx}: {e}")
                self.stats['products_failed'] += 1
                continue

        return products

    async def _extract_single_product(self, card) -> Optional[dict]:
        """
        Extract data from a single product card element.
        
        Args:
            card: Playwright ElementHandle for the product card.
            
        Returns:
            Raw product dict or None if extraction fails.
        """
        raw = {}

        # ── Product URL & SKU ──
        for sel in SELECTORS['product_link'].split(', '):
            try:
                link = await card.query_selector(sel.strip())
                if link:
                    raw['product_url'] = await link.get_attribute('href')
                    break
            except Exception:
                continue

        # Try to get SKU from data attributes
        for sel in SELECTORS['product_sku'].split(', '):
            try:
                sku_el = await card.query_selector(sel.strip())
                if sku_el:
                    raw['sku_id'] = (
                        await sku_el.get_attribute('data-sku')
                        or await sku_el.get_attribute('data-product-id')
                        or await sku_el.get_attribute('data-id')
                    )
                    break
            except Exception:
                continue

        # ── Product Name ──
        for sel in SELECTORS['product_name'].split(', '):
            try:
                el = await card.query_selector(sel.strip())
                if el:
                    text = await el.inner_text()
                    if text and text.strip():
                        raw['product_name'] = text
                        break
            except Exception:
                continue

        # ── Brand ──
        for sel in SELECTORS['product_brand'].split(', '):
            try:
                el = await card.query_selector(sel.strip())
                if el:
                    text = await el.inner_text()
                    if text and text.strip():
                        raw['brand'] = text
                        break
            except Exception:
                continue

        # ── MRP (Original Price) ──
        for sel in SELECTORS['product_mrp'].split(', '):
            try:
                el = await card.query_selector(sel.strip())
                if el:
                    text = await el.inner_text()
                    if text and text.strip():
                        raw['mrp'] = text
                        break
            except Exception:
                continue

        # ── DMart Price (Selling Price) ──
        for sel in SELECTORS['product_sale_price'].split(', '):
            try:
                el = await card.query_selector(sel.strip())
                if el:
                    text = await el.inner_text()
                    if text and text.strip():
                        raw['dmart_price'] = text
                        break
            except Exception:
                continue

        # ── Pack Size ──
        for sel in SELECTORS['product_pack_size'].split(', '):
            try:
                el = await card.query_selector(sel.strip())
                if el:
                    text = await el.inner_text()
                    if text and text.strip():
                        raw['pack_size'] = text
                        break
            except Exception:
                continue

        # ── Availability ──
        # Default to available; check for out-of-stock indicators
        raw['availability'] = 'In Stock'
        for sel in SELECTORS['product_availability'].split(', '):
            try:
                el = await card.query_selector(sel.strip())
                if el:
                    text = await el.inner_text()
                    if text and text.strip():
                        raw['availability'] = text
                        break
            except Exception:
                continue

        return raw if raw.get('product_name') or raw.get('product_url') else None

    def _extract_products_from_api(self, page: Optional[Page] = None) -> List[dict]:
        """
        Process products captured via API response interception.
        
        Returns:
            List of raw product dictionaries from API JSON.
        """
        api_products_list = []
        if page is not None:
            api_products_list = getattr(page, 'api_products', [])
        else:
            api_products_list = self._api_products

        # Flatten product variants
        flattened_items = []
        for item in api_products_list:
            skus = item.get('sKUs') or item.get('skus') or [item]
            for sku in skus:
                # Merge root properties with SKU properties (SKU overrides)
                merged = {**item, **sku}
                flattened_items.append(merged)

        products = []
        for item in flattened_items:
            try:
                raw = {
                    'product_name': (
                        item.get('name')
                        or item.get('product_name')
                        or item.get('displayName')
                        or item.get('title')
                    ),
                    'sku_id': (
                        item.get('skuUniqueID')
                        or item.get('sku_id')
                        or item.get('sku')
                        or item.get('id')
                    ),
                    'brand': (
                        item.get('brand')
                        or item.get('manufacturer')
                        or item.get('brandName')
                    ),
                    'mrp': (
                        item.get('priceMRP')
                        or item.get('mrp')
                        or item.get('maximum_retail_price')
                        or item.get('originalPrice')
                    ),
                    'dmart_price': (
                        item.get('priceSALE')
                        or item.get('selling_price')
                        or item.get('sale_price')
                        or item.get('price')
                        or item.get('offerPrice')
                        or item.get('dmartPrice')
                    ),
                    'pack_size': (
                        item.get('variantTextValue')
                        or item.get('pack_size')
                        or item.get('packSize')
                        or item.get('uom')
                        or item.get('weight')
                        or item.get('variant')
                    ),
                    'availability': (
                        item.get('availabilityType')
                        or item.get('is_available')
                        or item.get('stock_status')
                        or item.get('inStock')
                        or item.get('available')
                        or item.get('buyable')
                    ),
                    'product_url': (
                        (f"/product/{item.get('seo_token_ntk')}?selectedProd={item.get('skuUniqueID')}" if item.get('seo_token_ntk') else None)
                        or item.get('targetUrl')
                        or item.get('url')
                        or item.get('product_url')
                        or item.get('pdpUrl')
                        or item.get('link')
                    ),
                    'image_url': (
                        item.get('imageKey')
                        or item.get('productImageKey')
                        or item.get('image_url')
                        or item.get('image')
                    ),
                    'description': (
                        item.get('seo_meta_desc')
                        or item.get('description')
                    ),
                    'category_name': (
                        item.get('categoryName')
                        or item.get('category')
                        or item.get('category_name')
                    ),
                }

                if raw.get('product_name') or raw.get('sku_id'):
                    products.append(raw)

            except Exception as e:
                logger.warning(f"Failed to process API product: {e}")
                continue

        return products

    async def _process_and_save_api_products(self, page: Optional[Page] = None) -> int:
        """
        Process and save newly intercepted API products incrementally.
        
        Returns:
            Number of new unique products processed and saved in this batch.
        """
        api_products_list = []
        if page is not None:
            api_products_list = getattr(page, 'api_products', [])
        else:
            api_products_list = self._api_products

        if not api_products_list:
            return 0

        raw_products = self._extract_products_from_api(page)
        api_products_list.clear() # Clear so they are not re-processed

        scraped_skus_set = page.scraped_skus if page is not None else self.scraped_skus
        scraped_names_set = page.scraped_names if page is not None else self.scraped_names
        current_jsonl_path_val = page.current_jsonl_path if page is not None else self.current_jsonl_path
        current_category_name_val = page.current_category_name if page is not None else self.current_category_name
        current_category_id_val = page.current_category_id if page is not None else self.current_category_id

        new_saved = 0
        for raw in raw_products:
            try:
                sku_id = str(raw.get('sku_id', '')).strip()
                p_name = raw.get('product_name')
                p_size = raw.get('pack_size')

                # Skip if empty name/sku
                if not sku_id or not p_name:
                    continue

                # Normalization for deduplication comparison
                sku_key = sku_id
                name_key = (str(p_name).strip().lower(), str(p_size).strip().lower() if p_size else "")

                # Check double-layered resumability cache
                if sku_key in scraped_skus_set or name_key in scraped_names_set:
                    continue

                cleaned = DataCleaner.clean_product_data(raw)

                # Strict Garbage Data Prevention
                is_valid = (
                    bool(cleaned.get('sku_id')) and
                    bool(cleaned.get('product_name')) and
                    cleaned.get('dmart_price') is not None and
                    cleaned.get('dmart_price', 0) >= 0
                )

                if is_valid:
                    cleaned_sku = str(cleaned.get('sku_id')).strip()
                    cleaned_name = cleaned.get('product_name')
                    cleaned_size = cleaned.get('pack_size')
                    cleaned_name_key = (str(cleaned_name).strip().lower(), str(cleaned_size).strip().lower() if cleaned_size else "")

                    if current_jsonl_path_val:
                        self._stream_to_jsonl(cleaned, current_jsonl_path_val)

                    # Dynamically resolve category path in real-time
                    product_cat_path = cleaned.get('category_name') or raw.get('category_name')
                    if isinstance(product_cat_path, list):
                        product_cat_path = " > ".join(product_cat_path)
                    if not product_cat_path:
                        product_cat_path = current_category_name_val or "Uncategorized"

                    try:
                        cat_id = self.db.resolve_category_path(product_cat_path)
                    except Exception as cat_err:
                        logger.error(f"Failed to resolve product category path '{product_cat_path}': {cat_err}")
                        cat_id = current_category_id_val

                    # Insert into SQLite (which has secondary name+pack deduplication)
                    self.db.upsert_product(cleaned, cat_id)

                    scraped_skus_set.add(cleaned_sku)
                    scraped_names_set.add(cleaned_name_key)
                    new_saved += 1
                else:
                    self.stats['products_failed'] += 1
                    logger.debug(f"Garbage data rejected: SKU={cleaned.get('sku_id')} Name={cleaned.get('product_name')} Price={cleaned.get('dmart_price')}")

            except Exception as e:
                logger.warning(f"Incremental API product processing failed: {e}")
                self.stats['products_failed'] += 1

        if page is not None:
            page.category_products_scraped += new_saved
        else:
            self._category_products_scraped += new_saved
        return new_saved

    async def _get_card_sku(self, card) -> Optional[str]:
        """Quickly extract SKU ID from a product card without doing full extraction."""
        # Try attributes directly on the card
        for attr in ['data-sku', 'data-product-id', 'data-id']:
            try:
                val = await card.get_attribute(attr)
                if val:
                    return val.strip()
            except Exception:
                pass

        # Try sub-elements
        for sel in SELECTORS['product_sku'].split(', '):
            try:
                sku_el = await card.query_selector(sel.strip())
                if sku_el:
                    val = (
                        await sku_el.get_attribute('data-sku')
                        or await sku_el.get_attribute('data-product-id')
                        or await sku_el.get_attribute('data-id')
                    )
                    if val:
                        return val.strip()
            except Exception:
                continue
        return None

    async def _process_and_save_dom_products(self, page: Optional[Page] = None) -> int:
        """
        Process and save products from DOM elements, skipping cached ones.
        
        Returns:
            Number of new unique products processed and saved in this batch.
        """
        active_page = page if page is not None else self._page

        # Find product cards using multiple selector strategies
        cards = []
        for selector in SELECTORS['product_card'].split(', '):
            try:
                found = await active_page.query_selector_all(selector.strip())
                if found:
                    cards = found
                    break
            except Exception:
                continue

        if not cards:
            return 0

        scraped_skus_set = page.scraped_skus if page is not None else self.scraped_skus
        scraped_names_set = page.scraped_names if page is not None else self.scraped_names
        current_jsonl_path_val = page.current_jsonl_path if page is not None else self.current_jsonl_path
        current_category_name_val = page.current_category_name if page is not None else self.current_category_name
        current_category_id_val = page.current_category_id if page is not None else self.current_category_id

        new_saved = 0
        for idx, card in enumerate(cards):
            try:
                # Fast-skip: extract only SKU first
                sku_id = await self._get_card_sku(card)
                if sku_id and sku_id in scraped_skus_set:
                    continue

                # If not skipped, perform full card extraction
                raw = await self._extract_single_product(card)
                if not raw or not raw.get('product_name'):
                    continue

                sku_id = str(raw.get('sku_id', '')).strip() or sku_id
                p_name = raw.get('product_name')
                p_size = raw.get('pack_size')

                if not sku_id or not p_name:
                    continue

                sku_key = sku_id
                name_key = (str(p_name).strip().lower(), str(p_size).strip().lower() if p_size else "")

                if sku_key in scraped_skus_set or name_key in scraped_names_set:
                    continue

                cleaned = DataCleaner.clean_product_data(raw)

                # Strict Garbage Data Prevention
                is_valid = (
                    bool(cleaned.get('sku_id')) and
                    bool(cleaned.get('product_name')) and
                    cleaned.get('dmart_price') is not None and
                    cleaned.get('dmart_price', 0) >= 0
                )

                if is_valid:
                    cleaned_sku = str(cleaned.get('sku_id')).strip()
                    cleaned_name = cleaned.get('product_name')
                    cleaned_size = cleaned.get('pack_size')
                    cleaned_name_key = (str(cleaned_name).strip().lower(), str(cleaned_size).strip().lower() if cleaned_size else "")

                    if current_jsonl_path_val:
                        self._stream_to_jsonl(cleaned, current_jsonl_path_val)

                    # Dynamically resolve category path in real-time
                    product_cat_path = cleaned.get('category_name') or raw.get('category_name')
                    if isinstance(product_cat_path, list):
                        product_cat_path = " > ".join(product_cat_path)
                    if not product_cat_path:
                        product_cat_path = current_category_name_val or "Uncategorized"

                    try:
                        cat_id = self.db.resolve_category_path(product_cat_path)
                    except Exception as cat_err:
                        logger.error(f"Failed to resolve product category path '{product_cat_path}': {cat_err}")
                        cat_id = current_category_id_val

                    self.db.upsert_product(cleaned, cat_id)

                    scraped_skus_set.add(cleaned_sku)
                    scraped_names_set.add(cleaned_name_key)
                    new_saved += 1
                else:
                    self.stats['products_failed'] += 1
            except Exception as e:
                logger.warning(f"Incremental DOM card parsing failed at index {idx}: {e}")
                self.stats['products_failed'] += 1

        if page is not None:
            page.category_products_scraped += new_saved
        else:
            self._category_products_scraped += new_saved
        return new_saved

    # ── Streaming Data Pipeline ───────────────────────────────

    def _get_jsonl_path(self, category_slug: str) -> Path:
        """Get JSONL file path for a category scoped by pincode."""
        safe_slug = re.sub(r'[^\w\-]', '_', category_slug)
        return JSONL_EXPORT_DIR / f"{safe_slug}_{self.pincode}.jsonl"


    def _get_csv_path(self, category_slug: str) -> Path:
        """Generate safe file path for category CSV export scoped by pincode."""
        safe_name = category_slug.replace('/', '_').replace('\\', '_')
        return CATEGORY_EXPORT_DIR / f"{safe_name}_{self.pincode}.csv"

    def _get_completion_path(self, category_slug: str) -> Path:
        """Generate safe file path for category completion marker scoped by pincode."""
        safe_name = category_slug.replace('/', '_').replace('\\', '_')
        return CATEGORY_EXPORT_DIR / f"{safe_name}_{self.pincode}.completed"


    @staticmethod
    def _stream_to_jsonl(product: dict, jsonl_path: Path):
        """
        Stage 1: Append a single cleaned product to JSONL immediately.
        
        JSONL format = one JSON object per line, enabling:
            - Crash recovery (data saved instantly)
            - Line-by-line processing
            - Easy append without loading full file
        """
        try:
            with open(jsonl_path, 'a', encoding='utf-8') as f:
                json.dump(product, f, ensure_ascii=False, default=str)
                f.write('\n')
        except IOError as e:
            logger.error(f"JSONL write failed: {e}")

    @staticmethod
    def _jsonl_to_csv(jsonl_path: Path, csv_path: Path) -> int:
        """
        Stage 2: Convert JSONL to tabular CSV report.
        
        Args:
            jsonl_path: Input JSONL file.
            csv_path: Output CSV file.
            
        Returns:
            Number of rows written.
        """
        if not jsonl_path.exists():
            logger.warning(f"JSONL file not found: {jsonl_path}")
            return 0

        rows = {}
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        sku = data.get('sku_id')
                        if sku:
                            # Overwrite older duplicate with the latest scraped data
                            rows[sku] = data
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping malformed JSONL line: {e}")

        if not rows:
            return 0
            
        final_rows = list(rows.values())

        # Write CSV with all fields
        fieldnames = [
            'sku_id', 'product_name', 'brand', 'pack_size',
            'mrp', 'dmart_price', 'discount_amount',
            'availability', 'product_url', 'image_url', 'description', 'category_name'
        ]

        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=fieldnames,
                    extrasaction='ignore'
                )
                writer.writeheader()
                writer.writerows(final_rows)

            logger.info(f"CSV report written: {csv_path} ({len(final_rows)} unique rows)")
            return len(final_rows)

        except IOError as e:
            logger.error(f"CSV write failed: {e}")
            return 0

    # ── Category Scraping ─────────────────────────────────────

    async def scrape_category(
        self,
        category_url: str,
        category_name: str,
        category_slug: str,
        category_id: Optional[int] = None,
        page: Optional[Page] = None,
    ) -> int:
        """
        Scrape all products from a single category page.
        
        Implements the full 3-stage streaming pipeline:
            Stage 1: Stream each product to JSONL
            Stage 2: Convert JSONL → CSV on completion
            Stage 3: Load into SQLite
        
        Args:
            category_url: Full URL of the category page.
            category_name: Display name for logging.
            category_slug: URL slug for file naming.
            category_id: FK for database insertion.
            page: Optional Playwright Page tab for parallel execution.
            
        Returns:
            Number of products scraped from this category.
        """
        logger.info(f"{'='*60}")
        logger.info(f"Scraping category: {category_name}")
        logger.info(f"URL: {category_url}")
        logger.info(f"{'='*60}")

        active_page = page if page is not None else self._page

        # Clear API buffer for this category
        if active_page is not None:
            if not hasattr(active_page, 'api_products'):
                active_page.api_products = []
            active_page.api_products.clear()
        else:
            self._api_products.clear()

        jsonl_path = self._get_jsonl_path(category_slug)
        csv_path = self._get_csv_path(category_slug)
        
        # Initialize category state variables
        if active_page is not None:
            active_page.current_category_id = category_id
            active_page.current_category_name = category_name
            active_page.current_jsonl_path = jsonl_path
            active_page.category_products_scraped = 0
            if not hasattr(active_page, 'scraped_skus'):
                active_page.scraped_skus = set()
            if not hasattr(active_page, 'scraped_names'):
                active_page.scraped_names = set()
            active_page.scraped_skus.clear()
            active_page.scraped_names.clear()
            
            scraped_skus_set = active_page.scraped_skus
            scraped_names_set = active_page.scraped_names
        else:
            self.current_category_id = category_id
            self.current_category_name = category_name
            self.current_jsonl_path = jsonl_path
            self._category_products_scraped = 0
            self.scraped_skus.clear()
            self.scraped_names.clear()
            
            scraped_skus_set = self.scraped_skus
            scraped_names_set = self.scraped_names

        # Pre-load SQLite and JSONL caches
        existing_products = self.db.get_existing_products_for_category(category_id)
        for p in existing_products:
            sku = str(p.get('sku_id', '')).strip()
            name = p.get('product_name')
            size = p.get('pack_size')
            if sku:
                scraped_skus_set.add(sku)
            if name:
                scraped_names_set.add((str(name).strip().lower(), str(size).strip().lower() if size else ""))

        if jsonl_path.exists():
            try:
                with open(jsonl_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                sku = str(data.get('sku_id', '')).strip()
                                name = data.get('product_name')
                                size = data.get('pack_size')
                                if sku:
                                    scraped_skus_set.add(sku)
                                if name:
                                    scraped_names_set.add((str(name).strip().lower(), str(size).strip().lower() if size else ""))
                            except json.JSONDecodeError as je:
                                logger.warning(f"Skipping malformed/corrupted JSONL line {line_num} in {jsonl_path.name}: {je}")
            except Exception as e:
                logger.warning(f"Error reading existing JSONL for resumability caches: {e}")

        logger.info(
            f"Pre-loaded resumability caches | Unique SKUs: {len(scraped_skus_set)} | Unique Names: {len(scraped_names_set)}"
        )

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Navigate to category page
                response = await active_page.goto(
                    category_url,
                    wait_until='domcontentloaded',
                    timeout=PAGE_LOAD_TIMEOUT_MS
                )

                # ── Rate Limit / Forbidden Backoff ──
                if response and response.status in [403, 429]:
                    cooldown = random.uniform(60.0, 120.0)
                    logger.warning(
                        f"403 Forbidden/Rate Limited on Category Page! Pincode: {self.pincode}. "
                        f"Cooling down for {cooldown:.1f}s..."
                    )
                    await asyncio.sleep(cooldown)
                    continue  # Retry this attempt

                # Wait for initial products to appear in the DOM (blindingly fast wait)
                try:
                    await active_page.wait_for_selector(SELECTORS['product_card'].split(', ')[0], timeout=5000)
                except Exception:
                    # Fallback to a quick 1-second delay if cards aren't visible immediately (e.g. empty category)
                    await active_page.wait_for_timeout(1000)

                # Random delay to mimic human behavior
                delay = random.uniform(*REQUEST_DELAY_RANGE)
                await active_page.wait_for_timeout(int(delay * 1000))

                # Load all products via infinite scroll (incremental processing occurs inside)
                await self._scroll_to_load_all(active_page)

                # ── Final Sweep: Process remaining items ──
                api_products_list = []
                if active_page is not None:
                    api_products_list = getattr(active_page, 'api_products', [])
                else:
                    api_products_list = self._api_products

                if api_products_list:
                    logger.info(f"Final sweep: processing {len(api_products_list)} remaining API products.")
                    await self._process_and_save_api_products(active_page)
                else:
                    logger.info("Final sweep: performing final DOM product sweep.")
                    await self._process_and_save_dom_products(active_page)

                # ── Stage 2: Generate CSV report ──
                self._jsonl_to_csv(jsonl_path, csv_path)

                # ── Stage 3: Write Strict Completion Checkpoint File ──
                completion_path = self._get_completion_path(category_slug)
                products_scraped_count = active_page.category_products_scraped if active_page is not None else self._category_products_scraped
                try:
                    completion_data = {
                        "category_name": category_name,
                        "category_slug": category_slug,
                        "pincode": self.pincode,
                        "completed_at": datetime.now().isoformat(),
                        "products_scraped_this_run": products_scraped_count
                    }
                    with open(completion_path, 'w', encoding='utf-8') as cf:
                        json.dump(completion_data, cf, indent=2)
                    logger.info(f"Completion checkpoint written: {completion_path.name}")
                except Exception as ce:
                    logger.warning(f"Failed to write completion marker for '{category_name}': {ce}")

                self.stats['products_scraped'] += products_scraped_count
                self.stats['categories_scraped'] += 1

                logger.info(
                    f"Category '{category_name}' complete: "
                    f"{products_scraped_count} products scraped."
                )
                break  # Success — exit retry loop

            except Exception as e:
                logger.error(
                    f"Category '{category_name}' failed (attempt {attempt}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_S)
                else:
                    logger.error(f"All retries exhausted for '{category_name}'.")

        # Tear down state variables on exit
        if active_page is not None:
            products_scraped = active_page.category_products_scraped
            active_page.current_category_id = None
            active_page.current_category_name = None
            active_page.current_jsonl_path = None
            active_page.category_products_scraped = 0
            active_page.scraped_skus.clear()
            active_page.scraped_names.clear()
        else:
            products_scraped = self._category_products_scraped
            self.current_category_id = None
            self.current_category_name = None
            self.current_jsonl_path = None
            self._category_products_scraped = 0
            self.scraped_skus.clear()
            self.scraped_names.clear()

        return products_scraped

    # ── Main Run Orchestrator ─────────────────────────────────

    async def run(self, max_categories: Optional[int] = None):
        """
        Main entry point: discover categories and scrape each one.
        
        Args:
            max_categories: Limit the number of categories to scrape
                           (useful for testing). None = scrape all.
        """
        logger.info("=" * 60)
        logger.info("DMart Scraper — Starting")
        logger.info(f"Pincode: {self.pincode}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 60)

        # Step 1: Discover categories
        categories = await self.discover_categories()

        # ── Dynamic Pincode Completion Check ──
        # A pincode is dynamically completed ONLY if all discovered categories
        # have successfully compiled and completed metadata markers on disk.
        if len(categories) > 0 and not max_categories:
            non_completed_slugs = []
            for cat in categories:
                completion_path = self._get_completion_path(cat['slug'])
                if not completion_path.exists():
                    non_completed_slugs.append(cat['slug'])

            if not non_completed_slugs:
                logger.info(
                    f"\n" + "=" * 60 + "\n"
                    f"[Skip] PINCODE {self.pincode} IS ALREADY FULLY SCRAPED!\n"
                    f"All {len(categories)} discovered categories have verified completion markers on disk.\n"
                    f"Skipping entire loop for this pincode...\n" + "=" * 60
                )
                return

            logger.info(
                f"Pincode {self.pincode} status: {len(categories) - len(non_completed_slugs)} of "
                f"{len(categories)} discovered categories are completed. "
                f"Scraping remaining {len(non_completed_slugs)} categories..."
            )


        if max_categories:
            categories = categories[:max_categories]
            logger.info(f"Limited to {max_categories} categories for this run.")

        # Step 2: Register categories in database
        category_map = {}  # slug → category_id
        for cat in categories:
            try:
                cat_id = self.db.resolve_category_path(cat['name'])
                category_map[cat['slug']] = cat_id
            except Exception as e:
                logger.error(f"Failed to register category '{cat['name']}': {e}")

        # Step 3: Scrape categories concurrently using a worker pool
        from .config import CONCURRENT_CATEGORIES
        sem = asyncio.Semaphore(CONCURRENT_CATEGORIES)

        async def worker(cat: Dict[str, Any], idx: int):
            async with sem:
                completion_path = self._get_completion_path(cat['slug'])
                if completion_path.exists():
                    logger.info(f"[Skip] Category '{cat['name']}' already fully scraped. Skipping...")
                    return

                # Stagger startup delay to prevent simultaneous navigation bursts
                stagger_delay = random.uniform(0.1, 1.5)
                logger.info(f"Staggering worker startup by {stagger_delay:.2f}s for category '{cat['name']}'...")
                await asyncio.sleep(stagger_delay)

                cat_id = category_map.get(cat['slug'])

                # Dynamically allocate an isolated page tab for this worker
                page = await self._context.new_page()
                page.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
                page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)

                # Initialize state variables on page object to preserve task isolation
                page.api_products = []
                page.category_products_scraped = 0
                page.scraped_skus = set()
                page.scraped_names = set()
                page.current_category_id = cat_id
                page.current_category_name = cat['name']
                page.current_jsonl_path = self._get_jsonl_path(cat['slug'])

                # Register page-scoped API response interceptor
                page.on('response', lambda response: asyncio.create_task(self._on_response(response, page)))

                try:
                    logger.info(f"[{idx}/{len(categories)}] Starting concurrent scrape for category: {cat['name']}")
                    await self.scrape_category(
                        category_url=cat['url'],
                        category_name=cat['name'],
                        category_slug=cat['slug'],
                        category_id=cat_id,
                        page=page
                    )
                except Exception as e:
                    logger.error(f"Failed to scrape category '{cat['name']}' concurrently: {e}")
                finally:
                    try:
                        await page.close()
                    except Exception as ce:
                        logger.warning(f"Error closing worker page for '{cat['name']}': {ce}")

        # Run the worker pool using asyncio.gather
        tasks = [worker(cat, i) for i, cat in enumerate(categories, 1)]
        await asyncio.gather(*tasks)

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("DMart Scraper — Complete")
        logger.info(f"Categories scraped: {self.stats['categories_scraped']}")
        logger.info(f"Products scraped:   {self.stats['products_scraped']}")
        logger.info(f"Products failed:    {self.stats['products_failed']}")
        logger.info(f"API captures:       {self.stats['api_responses_captured']}")
        logger.info(f"DB Stats:           {self.db.get_stats()}")
        logger.info("=" * 60)
