# ============================================================
# IndiaMART Scraper Service — Subprocess Process Runner
# ============================================================
# Standalone process launched by app routes to bypass Celery 
# asyncio conflicts. Executes Playwright in stealth, resolves 
# search query to /impcat/ category pages, extracts supplier/product 
# metadata, prevents duplicates, and updates task progress.
# ============================================================

import argparse
import asyncio
import datetime
import json
import logging
import os
import re
import sys
import traceback
from typing import List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Ensure backend folder is in sys.path when running as CLI subprocess
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app import app
from extensions import db
from model.product_model.additional_products import IndiaMart
from model.scraper_task import ScraperTask
from sqlalchemy import text
from services.category_sync_service import auto_sync_platform

logger = logging.getLogger("indiamart_service")

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text)
    return text.strip('-')

def extract_numeric(val) -> float:
    if not val:
        return 0.0
    val_str = str(val).strip()
    cleaned = re.sub(r'[^\d.]', '', val_str)
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def sync_indiamart_categories(path_parts: List[str], db_session):
    """
    Sync category parts dynamically:
      1. indiamart_mappings (clean parent-child tree)
      2. product_category_master (unified hierarchy for dashboards)
      3. platform_category_mapping (for dynamic mapping status)
    """
    if not path_parts:
        return
        
    # ── 1. Ingest into indiamart_mappings ──
    # Root (level=None, parent_id=None, path=None), L1 (level=1, parent=Root), L2 (level=2, parent=L1)
    curr_parent_id = None
    curr_path = None
    for idx, part in enumerate(path_parts):
        level = idx if idx > 0 else None
        
        if idx == 0:
            sql = "SELECT id FROM indiamart_mappings WHERE category_name = :name AND parent_id IS NULL AND category_level IS NULL"
            res = db_session.execute(text(sql), {"name": part}).fetchone()
        else:
            sql = "SELECT id FROM indiamart_mappings WHERE category_name = :name AND parent_id = :parent_id AND category_level = :level"
            res = db_session.execute(text(sql), {"name": part, "parent_id": curr_parent_id, "level": level}).fetchone()
            
        if res:
            curr_parent_id = res[0]
            if idx == 0:
                curr_path = part
            else:
                curr_path = f"{curr_path} > {part}"
        else:
            if idx == 0:
                curr_path = part
                insert_sql = """
                    INSERT INTO indiamart_mappings (category_name, category_level, parent_id, category_path)
                    VALUES (:name, NULL, NULL, NULL)
                """
                db_session.execute(text(insert_sql), {"name": part})
            else:
                curr_path = f"{curr_path} > {part}"
                insert_sql = """
                    INSERT INTO indiamart_mappings (category_name, category_level, parent_id, category_path)
                    VALUES (:name, :level, :parent_id, :category_path)
                """
                db_session.execute(text(insert_sql), {
                    "name": part,
                    "level": level,
                    "parent_id": curr_parent_id,
                    "category_path": curr_path
                })
            db_session.flush()
            
            # Fetch newly created ID
            if idx == 0:
                fetch_sql = "SELECT id FROM indiamart_mappings WHERE category_name = :name AND parent_id IS NULL AND category_level IS NULL"
                curr_parent_id = db_session.execute(text(fetch_sql), {"name": part}).fetchone()[0]
            else:
                fetch_sql = "SELECT id FROM indiamart_mappings WHERE category_name = :name AND parent_id = :parent_id AND category_level = :level"
                curr_parent_id = db_session.execute(text(fetch_sql), {"name": part, "parent_id": curr_parent_id, "level": level}).fetchone()[0]

    # ── 2. Ingest into product_category_master ──
    # Level: Root is 1, L1 is 2, L2 is 3...
    curr_pcm_parent_id = None
    curr_pcm_path = None
    for idx, part in enumerate(path_parts):
        level = idx + 1
        
        if idx == 0:
            sql = "SELECT id FROM product_category_master WHERE marketplace_name = 'IndiaMART' AND category_name = :name AND parent_id IS NULL AND category_level = 1"
            res = db_session.execute(text(sql), {"name": part}).fetchone()
        else:
            sql = "SELECT id FROM product_category_master WHERE marketplace_name = 'IndiaMART' AND category_name = :name AND parent_id = :parent_id AND category_level = :level"
            res = db_session.execute(text(sql), {"name": part, "parent_id": curr_pcm_parent_id, "level": level}).fetchone()
            
        if res:
            curr_pcm_parent_id = res[0]
            if idx == 0:
                curr_pcm_path = part
            else:
                curr_pcm_path = f"{curr_pcm_path} > {part}"
        else:
            if idx == 0:
                curr_pcm_path = part
            else:
                curr_pcm_path = f"{curr_pcm_path} > {part}"
                
            insert_sql = """
                INSERT INTO product_category_master (
                    marketplace_name, category_name, subcategory_name, child_category_name, parent_id, category_level, category_path, category_key
                ) VALUES ('IndiaMART', :name, NULL, :name, :parent_id, :level, :category_path, :category_key)
            """
            db_session.execute(text(insert_sql), {
                "name": part,
                "parent_id": curr_pcm_parent_id,
                "level": level,
                "category_path": curr_pcm_path,
                "category_key": part.lower().strip()
            })
            db_session.flush()
            
            # Fetch newly created ID
            if idx == 0:
                fetch_sql = "SELECT id FROM product_category_master WHERE marketplace_name = 'IndiaMART' AND category_name = :name AND parent_id IS NULL AND category_level = 1"
                curr_pcm_parent_id = db_session.execute(text(fetch_sql), {"name": part}).fetchone()[0]
            else:
                fetch_sql = "SELECT id FROM product_category_master WHERE marketplace_name = 'IndiaMART' AND category_name = :name AND parent_id = :parent_id AND category_level = :level"
                curr_pcm_parent_id = db_session.execute(text(fetch_sql), {"name": part, "parent_id": curr_pcm_parent_id, "level": level}).fetchone()[0]

    # ── 3. Register platform_category_mapping ──
    raw_cat = path_parts[0]
    raw_subcat = path_parts[-1] if len(path_parts) > 1 else ""
    
    map_sql = """
        SELECT id FROM platform_category_mapping 
        WHERE platform_name = 'IndiaMart' AND platform_category_raw = :raw_cat AND platform_subcategory_raw = :raw_subcat
    """
    mapping_res = db_session.execute(text(map_sql), {"raw_cat": raw_cat, "raw_subcat": raw_subcat}).fetchone()
    
    if not mapping_res:
        insert_map_sql = """
            INSERT INTO platform_category_mapping (
                platform_name, platform_category_raw, platform_subcategory_raw, mapping_status, confidence_score, is_active, created_at, updated_at
            ) VALUES ('IndiaMart', :raw_cat, :raw_subcat, 'PENDING', 0.0, 1, NOW(), NOW())
        """
        db_session.execute(text(insert_map_sql), {"raw_cat": raw_cat, "raw_subcat": raw_subcat})
        db_session.flush()

async def scrape_indiamart(search_term: str, pages_limit: int = 1, task_id: Optional[int] = None):
    logger.info(f"=== IndiaMART Scraper START | query={search_term} | pages={pages_limit} ===")
    
    # ── Retrieve Task for progress updates ──
    task = None
    if task_id:
        try:
            task = db.session.get(ScraperTask, task_id)
            if task:
                task.status = "RUNNING"
                task.progress = 5
                db.session.commit()
                logger.info(f"ScraperTask {task_id} status set to RUNNING")
        except Exception as e:
            logger.warning(f"Failed to fetch/initialize ScraperTask: {e}")

    async def update_task_progress(progress_pct: int, status_msg: str, found_count: int = 0):
        if not task_id:
            return
        try:
            t = db.session.get(ScraperTask, task_id)
            if t:
                t.progress = progress_pct
                t.status = status_msg
                if found_count > 0:
                    t.total_found = found_count
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Failed to update task progress: {e}")

    await update_task_progress(10, "Initializing Playwright stealth browser...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-extensions",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN','en-US','en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}), app: { isInstalled: false } };
            """
        )
        page = await context.new_page()

        # ── Step 1: Resolve Target Category URL ──
        await update_task_progress(15, "Resolving category page URL...")
        slug = slugify(search_term)
        urls_to_try = [
            f"https://dir.indiamart.com/impcat/{slug}.html",
        ]
        
        # Try pluralizing/bearing variants
        if not slug.endswith("s"):
            urls_to_try.append(f"https://dir.indiamart.com/impcat/{slug}s.html")
        if "bearing" in slug and not slug.endswith("bearings"):
            urls_to_try.append(f"https://dir.indiamart.com/impcat/{slug.replace('bearing', 'bearings')}.html")

        target_url = None
        for url in urls_to_try:
            logger.info(f"Checking URL variant: {url}")
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                if response and response.status == 200:
                    title = await page.title()
                    if "page not found" not in title.lower():
                        target_url = url
                        logger.info(f"Found valid category URL: {target_url}")
                        break
            except Exception as e:
                logger.debug(f"Failed to load URL {url}: {e}")

        # Google fallback if guessed category pages return 404
        if not target_url:
            logger.info("Direct category URL guess failed. Falling back to Google Search...")
            await update_task_progress(25, "Searching Google for IndiaMART category landing page...")
            google_url = f"https://www.google.com/search?q=site:indiamart.com/impcat/+{search_term.replace(' ', '+')}"
            try:
                await page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
                links = await page.evaluate("""
                    () => {
                        const arr = [];
                        document.querySelectorAll('a').forEach(a => {
                            if (a.href && a.href.includes('indiamart.com/impcat/')) {
                                arr.push(a.href);
                            }
                        });
                        return arr;
                    }
                """)
                for link in links:
                    # Clean redirect prefixes
                    m = re.search(r'(https://dir\.indiamart\.com/impcat/[^&\?]+)', link)
                    resolved = m.group(1) if m else link
                    if "dir.indiamart.com/impcat/" in resolved:
                        target_url = resolved
                        logger.info(f"Google Search resolved category URL: {target_url}")
                        break
            except Exception as e:
                logger.warning(f"Google search fallback failed: {e}")

        # Standard search page fallback
        if not target_url:
            target_url = f"https://dir.indiamart.com/search.mp?ss={search_term.replace(' ', '+')}"
            logger.info(f"Falling back to keyword search URL: {target_url}")

        # ── Step 2: Load Category / Listing page ──
        await update_task_progress(35, "Navigating to resolved IndiaMART page...")
        logger.info(f"Loading page: {target_url}")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000) # wait for overlays to mount
            
            # Dismiss overlay
            await page.evaluate("""
                () => {
                    const overlay = document.getElementById('remote-login-connect-popup-shell');
                    const modal = document.querySelector('.im-header-ver-cert-modal');
                    if (overlay) overlay.remove();
                    if (modal) modal.remove();
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }
            """)
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            raise

        # ── Step 3: Scroll Page to Load Listings ──
        scroll_count = max(1, min(pages_limit * 3, 20))
        await update_task_progress(45, f"Scrolling page ({scroll_count} times) to load products...")
        logger.info(f"Scrolling down {scroll_count} times to render listings...")
        for i in range(scroll_count):
            await page.mouse.wheel(0, 600)
            await page.wait_for_timeout(1000)
            
        await page.wait_for_timeout(3000) # Let it settle
        
        # ── Step 4: Parse DOM content with BeautifulSoup ──
        await update_task_progress(60, "Extracting page source HTML...")
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        # Parse Breadcrumbs
        breadcrumbs = []
        nav = soup.find("nav", class_="breadcrumb")
        if nav:
            breadcrumbs = [a.get_text(strip=True) for a in nav.find_all("a")]
            # Extract the leaf category (non-link text at the end)
            nav_text = nav.get_text(">", strip=True)
            text_parts = [p.strip() for p in nav_text.split(">") if p.strip()]
            if text_parts and text_parts[-1] not in breadcrumbs:
                breadcrumbs.append(text_parts[-1])
            
            # Filter root link (IndiaMART)
            if breadcrumbs and "indiamart" in breadcrumbs[0].lower():
                breadcrumbs.pop(0)

        # Fallback to search term if breadcrumbs are missing
        if not breadcrumbs:
            breadcrumbs = [search_term.title()]
            title = await page.title()
            # Clean title as leaf category
            clean_title = title.split("-")[0].strip()
            if clean_title and clean_title.lower() != "indiamart" and clean_title not in breadcrumbs:
                breadcrumbs.append(clean_title)

        logger.info(f"Resolved Breadcrumb Category Path: {breadcrumbs}")
        root_cat = breadcrumbs[0]
        leaf_cat = breadcrumbs[-1]

        # Sync resolved category nodes
        try:
            sync_indiamart_categories(breadcrumbs, db.session)
            db.session.commit()
            logger.info("Category nodes synced successfully.")
        except Exception as cat_err:
            db.session.rollback()
            logger.error(f"Failed to sync category nodes: {cat_err}")

        # Parse Cards
        cards = soup.find_all("article", class_="template7-product-card")
        if not cards:
            # Fallback search selector in case structure differs
            cards = soup.find_all(class_=re.compile("product-card|card|mcard"))
            
        logger.info(f"Found {len(cards)} listing cards on the page.")
        await update_task_progress(75, f"Found {len(cards)} products. Syncing records to database...")

        inserted = 0
        updated = 0
        failed = 0
        duplicates_prevented = 0

        for card in cards:
            try:
                # Find product link
                a_title = card.find("a", class_=re.compile("product-name|prdtitle|template7-product-name"))
                if not a_title or not a_title.get("href"):
                    # Fallback lookup in all links
                    a_title = None
                    for a in card.find_all("a", href=True):
                        if "proddetail" in a["href"]:
                            a_title = a
                            break
                
                if not a_title or not a_title.get("href"):
                    continue

                prod_url = a_title["href"]
                prod_name = a_title.get_text(strip=True)
                
                # Extract numeric ASIN ID from URL
                m_asin = re.search(r'-(\d+)\.html$', prod_url)
                if not m_asin:
                    continue
                asin = m_asin.group(1)

                # Price Details
                price_span = card.find(class_=re.compile("product-price|prc|template7-product-price"))
                price_str = price_span.get_text(strip=True) if price_span else ""
                
                price_unit_span = card.find(class_=re.compile("prcut|template7-product-price"))
                price_unit = price_unit_span.get_text(strip=True) if price_unit_span else ""
                if price_unit and price_unit not in price_str:
                    full_price_str = f"{price_str}/{price_unit}"
                else:
                    full_price_str = price_str
                
                price_numeric = extract_numeric(price_str)

                # Image URL
                img = card.find("img", class_=re.compile("product-image|lazy-src|zoom"))
                img_url = ""
                if img:
                    img_url = img.get("src") or img.get("data-src") or img.get("lazy-src") or img.get("zoom-image") or ""
                
                # Supplier / Manufacturer details
                seller_a = card.find("a", class_=re.compile("seller-name|template7-seller-name"))
                manufacturer = seller_a.get_text(strip=True) if seller_a else ""

                # City Location
                loc_div = card.find(class_=re.compile("seller-row|template7-seller-row"))
                location = loc_div.get_text(strip=True) if loc_div else ""

                # Specs Description
                specs_div = card.find(class_=re.compile("product-specs|template7-product-specs"))
                description = specs_div.get_text("; ", strip=True) if specs_div else ""

                # Badges (TrustSEAL, Years in Business)
                badges_list = []
                trust_span = card.find(text=lambda t: t and "TrustSEAL" in t)
                if trust_span:
                    badges_list.append("TrustSEAL")
                yrs_span = card.find(text=lambda t: t and "yrs" in t)
                if yrs_span:
                    badges_list.append(yrs_span.strip())
                badges = ", ".join(badges_list)

                # Star Rating
                star_span = card.find("span", class_="b")
                stars = 0.0
                if star_span:
                    try:
                        stars = float(star_span.get_text(strip=True))
                    except ValueError:
                        pass

                # Reviews
                reviews = 0
                rev_div = card.find(class_=re.compile("dag5"))
                if rev_div:
                    m_rev = re.search(r'\((\d+)\)', rev_div.get_text(strip=True))
                    if m_rev:
                        try:
                            reviews = int(m_rev.group(1))
                        except ValueError:
                            pass

                # Phone/Contact details
                contact_button = card.find("button", class_=re.compile("view-mobile-btn|template7-view-mobile"))
                contact_number = ""
                if contact_button:
                    contact_number = contact_button.get("data-vmn") or ""

                # ── Upsert Logic with Duplicate Prevention ──
                existing = IndiaMart.query.filter_by(asin=asin).first()
                if existing:
                    # Existing product: update details instead of duplicate insert
                    existing.category_name = root_cat
                    existing.sub_category_name = leaf_cat
                    existing.product_name = prod_name
                    existing.description = description or existing.description
                    existing.Price = full_price_str or existing.Price
                    existing.stars = stars or existing.stars
                    existing.reviews = reviews or existing.reviews
                    existing.manufacturer = manufacturer or existing.manufacturer
                    existing.contact_number = contact_number or existing.contact_number
                    existing.location = location or existing.location
                    existing.badges = badges or existing.badges
                    existing.productUrl = prod_url
                    existing.imgUrl = img_url or existing.imgUrl
                    existing.price_numeric = price_numeric or existing.price_numeric
                    existing.added_time = datetime.datetime.utcnow()
                    updated += 1
                    duplicates_prevented += 1
                else:
                    new_prod = IndiaMart(
                        asin=asin,
                        category_name=root_cat,
                        sub_category_name=leaf_cat,
                        product_name=prod_name,
                        description=description,
                        Price=full_price_str,
                        stars=stars,
                        reviews=reviews,
                        manufacturer=manufacturer,
                        contact_number=contact_number,
                        location=location,
                        badges=badges,
                        productUrl=prod_url,
                        imgUrl=img_url,
                        price_numeric=price_numeric,
                        added_time=datetime.datetime.utcnow()
                    )
                    db.session.add(new_prod)
                    inserted += 1

                # Commit every 10 records to prevent long locks
                if (inserted + updated) % 10 == 0:
                    db.session.commit()
                    await update_task_progress(
                        75 + min(20, int(((inserted + updated) / len(cards)) * 20)),
                        f"Database Sync: Ingested {inserted + updated}/{len(cards)} products...",
                        inserted + updated
                    )

            except Exception as card_err:
                failed += 1
                logger.error(f"Error parsing product card: {card_err}", exc_info=True)

        try:
            db.session.commit()
        except Exception as final_commit_err:
            db.session.rollback()
            logger.error(f"Final commit failed: {final_commit_err}")

        logger.info(
            f"Run completed: {inserted} inserted, {updated} updated, "
            f"{failed} failed. Duplicates Prevented: {duplicates_prevented}"
        )
        
        # ── Step 5: Automatically Sync Platforms & Mappings ──
        await update_task_progress(95, "Triggering central Category mapping synchronizer...")
        try:
            auto_sync_platform("IndiaMart")
            logger.info("Category Auto-Sync Triggered successfully.")
        except Exception as sync_err:
            logger.error(f"Category sync failed: {sync_err}")

        # Mark ScraperTask as COMPLETED
        if task_id:
            try:
                active_task = db.session.get(ScraperTask, task_id)
                if active_task:
                    active_task.status = "COMPLETED"
                    active_task.progress = 100
                    active_task.total_found = inserted + updated
                    db.session.commit()
                    logger.info(f"ScraperTask {task_id} successfully marked COMPLETED")
            except Exception as t_err:
                logger.error(f"Failed to set task as COMPLETED: {t_err}")

        logger.info("=== IndiaMART Scraper Automation COMPLETE ===")

def main():
    parser = argparse.ArgumentParser(description="IndiaMART Scraper Process Runner")
    parser.add_argument("--search_term", type=str, required=True)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--task_id", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s : %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    with app.app_context():
        try:
            asyncio.run(scrape_indiamart(
                search_term=args.search_term,
                pages_limit=args.pages,
                task_id=args.task_id
            ))
        except Exception as e:
            logger.critical(f"Scraper process crashed: {e}")
            if args.task_id:
                try:
                    active_task = db.session.get(ScraperTask, args.task_id)
                    if active_task:
                        active_task.status = "ERROR"
                        active_task.error_message = traceback.format_exc()[-1000:]
                        db.session.commit()
                except Exception:
                    pass
            sys.exit(1)

if __name__ == "__main__":
    main()
