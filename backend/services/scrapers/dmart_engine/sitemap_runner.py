import asyncio
import json
import logging
import time
import random
from pathlib import Path
from typing import List

from .sitemap_parser import SitemapParser
from .scraper import DMartScraper
from .database import DatabaseManager
from .cleaner import DataCleaner
from .config import PDP_SELECTORS, EXPORT_DIR, JSONL_EXPORT_DIR, DEFAULT_PINCODE

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

class SitemapRunner:
    """
    Executes the Sitemap-Driven PDP Scraping Architecture.
    """
    def __init__(self, db_or_path, pincode: str = DEFAULT_PINCODE):
        if isinstance(db_or_path, DatabaseManager):
            self.db = db_or_path
            self.db_path = db_or_path.db_path
        else:
            self.db_path = db_or_path
            from .config import SCHEMA_PATH
            self.db = DatabaseManager(self.db_path, str(SCHEMA_PATH))
        self.pincode = pincode
        self.output_file = JSONL_EXPORT_DIR / "dmart_sitemap_export.jsonl"
        
    async def extract_pdp_data(self, page, url: str) -> dict:
        """Extracts data directly from a loaded PDP page."""
        raw = {'product_url': url}
        
        # URL parsing for SKU
        if 'selectedProd=' in url:
            raw['sku_id'] = url.split('selectedProd=')[-1].split('&')[0]
            
        # ── Name & Brand ──
        try:
            h1 = await page.query_selector(PDP_SELECTORS['product_name'])
            if h1:
                title = await h1.inner_text()
                raw['product_name'] = title
                # E.g. "DMart Premia Wheat (Gahu) Lokwan (Lokvan): 10 kgs"
                # First 2-3 words are usually the brand if not specified
                raw['brand'] = " ".join(title.split()[:2])
        except Exception: pass
        
        # ── Breadcrumbs (Category) ──
        try:
            crumbs = await page.query_selector_all(PDP_SELECTORS['breadcrumbs'])
            if crumbs:
                crumb_texts = []
                for c in crumbs:
                    text = await c.inner_text()
                    if text and text.strip(): crumb_texts.append(text.strip())
                if crumb_texts:
                    raw['category'] = " > ".join(crumb_texts)
        except Exception: pass
        
        # ── Prices ──
        try:
            for sel in PDP_SELECTORS['product_mrp'].split(', '):
                el = await page.query_selector(sel)
                if el:
                    parent = await el.evaluate_handle('el => el.parentElement')
                    if parent: raw['mrp'] = await parent.inner_text()
        except Exception: pass
        
        try:
            for sel in PDP_SELECTORS['product_sale_price'].split(', '):
                el = await page.query_selector(sel)
                if el:
                    parent = await el.evaluate_handle('el => el.parentElement')
                    if parent: raw['dmart_price'] = await parent.inner_text()
        except Exception: pass
        
        # ── Description ──
        try:
            for sel in PDP_SELECTORS['description'].split(', '):
                el = await page.query_selector(sel)
                if el:
                    raw['description'] = await el.inner_text()
                    break
        except Exception: pass
        
        return raw

    async def run(self, limit: int = 50, custom_urls: List[str] = None):
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        if custom_urls:
            urls = custom_urls
            logger.info(f"Using {len(urls)} custom provided URLs for PDP scraping.")
        else:
            urls = SitemapParser.fetch_product_urls(limit=limit)
            
        if not urls:
            logger.error("No URLs available for scraping.")
            return
            
        db = self.db
        
        # ── Sitemap PDP Resumability Check ──
        existing_urls = set()
        try:
            with db:
                db.cursor.execute("SELECT product_url FROM dmart_product_master WHERE description IS NOT NULL AND description != ''")
                existing_urls = {row[0] for row in db.cursor.fetchall() if row[0]}
        except Exception as e:
            logger.warning(f"Failed to load existing PDP URLs from database for resumability: {e}")
            
        original_count = len(urls)
        # Filter URLs to skip already scraped ones
        urls = [url for url in urls if url not in existing_urls]
        if len(urls) < original_count:
            logger.info(
                f"Sitemap Resumability check: skipped {original_count - len(urls)} URLs "
                f"already fully scraped in SQLite. Scraping remaining {len(urls)} URLs..."
            )
            
        if not urls:
            logger.info("All sitemap product URLs are already fully scraped. Skipping execution.")
            return

        sem = asyncio.Semaphore(1) # Max 1 concurrent parallel page for stealth serial scraping
        db_lock = asyncio.Lock()
        
        async with DMartScraper(db, self.pincode) as scraper:
            # Handle pincode on the main page once so cookies are set for context
            if len(urls) > 0:
                max_init_retries = 3
                for attempt in range(max_init_retries):
                    try:
                        response = await scraper._page.goto(urls[0], wait_until='domcontentloaded')
                        
                        # ── Rate Limit / Forbidden Backoff ──
                        if response and response.status in [403, 429]:
                            cooldown = random.uniform(60.0, 120.0)
                            logger.warning(
                                f"403 Forbidden/Rate Limited on initial sitemap page load! "
                                f"Cooling down for {cooldown:.1f}s... (Attempt {attempt+1}/{max_init_retries})"
                            )
                            await asyncio.sleep(cooldown)
                            continue  # Retry this attempt
                            
                        await scraper._handle_pincode_popup()
                        break  # Success
                    except Exception as e:
                        logger.error(f"Initial page load error on attempt {attempt+1}: {e}")
                        if attempt == max_init_retries - 1:
                            raise e
                        await asyncio.sleep(5)

 
            f = open(self.output_file, 'a', encoding='utf-8')
            
            async def process_url(i: int, url: str):
                async with sem:
                    page = await scraper._context.new_page()
                    page.set_default_timeout(30000)
                    
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            # ── Anti-Bot Stagger Delay ──
                            delay = random.uniform(5.0, 10.0)
                            logger.info(f"Stealth pause: waiting {delay:.1f}s before accessing {url}")
                            await asyncio.sleep(delay)
                            
                            logger.info(f"[{i+1}/{len(urls)}] Scraping PDP: {url} (Attempt {attempt+1})")
                            response = await page.goto(url, wait_until='domcontentloaded')
                            
                            if response and response.status in [403, 429]:
                                cooldown = random.uniform(60.0, 120.0)
                                logger.warning(f"403 Forbidden/Rate Limited on {url}. Rate limited. Backing off for {cooldown:.1f}s...")
                                await asyncio.sleep(cooldown)
                                continue # Retry
                                
                            await page.wait_for_timeout(2000) # Let React render
                            
                            raw_data = await self.extract_pdp_data(page, url)
                            clean_data = DataCleaner.clean_product_data(raw_data)
                            
                            # Strict Garbage Data Prevention
                            is_valid = (
                                bool(clean_data.get('sku_id')) and
                                bool(clean_data.get('product_name')) and
                                clean_data.get('dmart_price') is not None and
                                clean_data.get('dmart_price', 0) >= 0
                            )
                            
                            if not is_valid:
                                logger.warning(f"Garbage data rejected from {url}")
                                break # Do not retry garbage data
                                
                            # Handle Category Hierarchy dynamically
                            category_path = raw_data.get('category', 'Uncategorized')
                            
                            # Async lock for DB and file writes
                            async with db_lock:
                                with db:
                                    cat_id = db.resolve_category_path(category_path)
                                    db.upsert_product(clean_data, cat_id)
                                    
                                # Stream to JSONL
                                clean_data['breadcrumb_category'] = raw_data.get('category')
                                f.write(json.dumps(clean_data) + "\n")
                                f.flush()
                                
                            logger.info(f"Successfully saved: {clean_data['product_name']}")
                            break # Success, exit retry loop
                            
                        except Exception as e:
                            logger.error(f"Error processing {url}: {e}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(5)
                    
                    await page.close()

            # Launch all tasks concurrently
            tasks = [process_url(i, url) for i, url in enumerate(urls)]
            await asyncio.gather(*tasks)
            
            f.close()
                        
        logger.info(f"Sitemap run complete! Saved to {self.output_file}")

if __name__ == '__main__':
    runner = SitemapRunner(r'C:\Users\Dronzer\Desktop\HBD Task\tasks\task-01_dmart-scraper\output\dmart_master.db')
    asyncio.run(runner.run(limit=50))
