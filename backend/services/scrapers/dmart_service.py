# ============================================================
# DMart Scraper Service — Celery Integration Adapter
# ============================================================
# Thin adapter between Celery tasks and the dmart_engine package.
#
# Flow:
#   Frontend  →  POST /api/scrape_dmart  →  dmart_routes.py
#   dmart_routes.py  →  run_dmart_scraper.delay()  (Celery)
#   Celery worker  →  scrape_dmart_search()  (this file)
#   scrape_dmart_search()  →  DMartScraper (dmart_engine)
#                         →  SQLite (dmart_master.db)  [engine writes directly]
#                         →  MySQL  (dmart_products)   [this adapter syncs]
#
# The scraper engine (dmart_engine/scraper.py) streams every
# product to SQLite in real-time. After scraping completes,
# this adapter reads new rows from SQLite and upserts them to MySQL.
# ============================================================

import asyncio
import logging
from typing import Optional

from services.scrapers.dmart_engine.scraper import DMartScraper
from services.scrapers.dmart_engine.database import DatabaseManager
from services.scrapers.dmart_engine.config import DB_PATH, SCHEMA_PATH, EXPORT_DIR

logger = logging.getLogger(__name__)


def scrape_dmart_search(
    search_term: str,
    mode: str = "category",
    pincodes: str = "all",
    max_categories: Optional[int] = None,
    task_id: Optional[int] = None,
    categories: Optional[str] = None
):
    """
    Celery-compatible entry point for the DMart scraper.

    Modes:
        category — Infinite scroll PLP scraping (default)

    After each pincode's scrape completes, all products in SQLite
    (dmart_product_master) are synced to MySQL (dmart_products table).
    """
    # Force Category mode exclusively as sitemaps and hybrid approaches are deprecated
    mode = "category"

    from app import app
    from extensions import db
    from model.product_model.additional_products import DMart, DMartCategory
    from model.scraper_task import ScraperTask

    with app.app_context():
        # ── Retrieve Task for progress updates ──
        task = None
        if task_id:
            try:
                task = db.session.get(ScraperTask, task_id)
                if task:
                    task.status = "RUNNING"
                    task.progress = 0
                    db.session.commit()
                    logger.info(f"ScraperTask {task_id} initialized to RUNNING")
            except Exception as e:
                logger.warning(f"Failed to fetch/initialize ScraperTask in start: {e}")

        # ── Parse pincode list ──
        if str(pincodes).strip().lower() == "all" or not pincodes:
            from services.scrapers.dmart_engine.config import PINCODE_LIST
            pincode_list = PINCODE_LIST
        else:
            pincode_list = [p.strip() for p in str(pincodes).split(",") if p.strip()]

        limit = int(max_categories) if max_categories else None
        
        # ── Parse categories list ──
        categories_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None


        logger.info(
            f"=== DMart Scraper START | mode={mode} | "
            f"pincodes={pincode_list[:3]}... | max_cat={limit} ==="
        )

        for idx, pin in enumerate(pincode_list, 1):
            logger.info(f"[{idx}/{len(pincode_list)}] Running scrape for pincode: {pin}")

            import datetime
            # Buffer by 5 minutes to prevent missing rows due to execution lag or time difference
            run_start_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

            if task_id:
                try:
                    active_task = db.session.get(ScraperTask, task_id)
                    if active_task:
                        active_task.status = f"Pincode {pin} ({idx}/{len(pincode_list)}): Initializing browser..."
                        db.session.commit()
                except Exception:
                    pass

            # ── Open SQLite (shared across modes for this pincode) ──
            sqlite_db = DatabaseManager(str(DB_PATH), str(SCHEMA_PATH))

            # ── Register real-time simultaneous MySQL & Task updates callback ──
            def on_category_saved_callback(category: dict):
                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        name = category.get('category_name')
                        slug = category.get('slug')
                        parent_id = category.get('parent_id')
                        level = category.get('category_level')
                        category_path = category.get('category_path')

                        # Resolve the parent's MySQL category_id if parent_id exists
                        parent_mysql_id = None
                        if parent_id is not None:
                            try:
                                sqlite_db.cursor.execute(
                                    "SELECT category_path FROM dmart_category_master WHERE category_id = ?",
                                    (parent_id,)
                                )
                                parent_row = sqlite_db.cursor.fetchone()
                                if parent_row and parent_row[0]:
                                    parent_path = parent_row[0]
                                    parent_mysql_cat = DMartCategory.query.filter_by(category_path=parent_path).first()
                                    if parent_mysql_cat:
                                        parent_mysql_id = parent_mysql_cat.category_id
                            except Exception as parent_err:
                                logger.warning(f"Failed to resolve parent path/ID for SQLite parent ID {parent_id}: {parent_err}")

                        existing_cat = DMartCategory.query.filter_by(category_path=category_path).first()
                        if existing_cat:
                            existing_cat.category_name = name
                            existing_cat.slug = slug
                            existing_cat.parent_id = parent_mysql_id
                            existing_cat.category_level = level
                        else:
                            new_cat = DMartCategory(
                                category_name = name,
                                slug = slug,
                                parent_id = parent_mysql_id,
                                category_level = level,
                                category_path = category_path
                            )
                            db.session.add(new_cat)
                        db.session.commit()
                        logger.info(f"Synchronized category '{name}' (Path={category_path}) to MySQL")
                        break  # Success
                    except Exception as cat_err:
                        db.session.rollback()
                        db.session.remove()  # Crucial: discard dead connection context
                        if attempt == max_retries:
                            logger.error(f"Real-time MySQL category sync failed for path {category.get('category_path')} after {max_retries} attempts: {cat_err}")
                            break
                        logger.warning(f"Category sync failed on attempt {attempt}/{max_retries}. Discarded connection, retrying in 2s...")
                        import time
                        time.sleep(2)

            pending_products = []
            processed_count = 0

            def flush_pending_products():
                nonlocal pending_products
                if not pending_products:
                    return

                logger.info(f"Flushing {len(pending_products)} buffered products to MySQL...")
                import datetime

                for prod, cat_id in pending_products:
                    sku_id = str(prod.get('sku_id', '')).strip()
                    if not sku_id:
                        continue

                    product_name = prod.get('product_name') or "Unknown Product"
                    brand = prod.get('brand')
                    pack_size = prod.get('pack_size')
                    mrp = prod.get('mrp')
                    dmart_price = prod.get('dmart_price')
                    availability = prod.get('availability')
                    category_name = prod.get('category_name') or "Uncategorized"
                    product_url = prod.get('product_url')
                    image_url = prod.get('image_url')

                    price_str = str(dmart_price) if dmart_price is not None else "0.0"
                    mrp_str = str(mrp) if mrp is not None else "0.0"

                    # Resolve SQLite category_id to MySQL category_id by path
                    mysql_cat_id = None
                    if cat_id:
                        try:
                            sqlite_db.cursor.execute(
                                "SELECT category_path FROM dmart_category_master WHERE category_id = ?",
                                (cat_id,)
                            )
                            row = sqlite_db.cursor.fetchone()
                            if row and row[0]:
                                cat_path = row[0]
                                mysql_cat = DMartCategory.query.filter_by(category_path=cat_path).first()
                                if mysql_cat:
                                    mysql_cat_id = mysql_cat.category_id
                        except Exception as path_err:
                            logger.warning(f"Failed to map SQLite category ID {cat_id} to MySQL category ID: {path_err}")
                    
                    if not mysql_cat_id and category_name:
                        mysql_cat = DMartCategory.query.filter_by(category_path=category_name).first()
                        if mysql_cat:
                            mysql_cat_id = mysql_cat.category_id

                    max_db_retries = 3
                    for db_attempt in range(1, max_db_retries + 1):
                        try:
                            existing = DMart.query.filter_by(ASIN=sku_id).first()
                            if existing:
                                existing.title       = product_name or existing.title
                                if image_url:
                                    existing.imgUrl  = image_url
                                existing.productUrl  = product_url or existing.productUrl
                                existing.price       = price_str
                                existing.listPrice   = mrp_str
                                if category_name and category_name not in ("Uncategorized", "null"):
                                    existing.categoryName = category_name
                                if mysql_cat_id is not None:
                                    existing.category_id = mysql_cat_id
                                existing.brand       = brand or existing.brand
                                existing.quantity    = pack_size or existing.quantity
                                existing.availability = availability
                                existing.scraped_at  = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                            else:
                                new_product = DMart(
                                    asin         = sku_id,
                                    title        = product_name,
                                    imgUrl       = image_url,
                                    productUrl   = product_url,
                                    price        = price_str,
                                    listPrice    = mrp_str,
                                    categoryName = category_name,
                                    brand        = brand,
                                    category_id  = mysql_cat_id,
                                    quantity     = pack_size,
                                    availability = availability,
                                    scraped_at   = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                                )
                                db.session.add(new_product)

                            db.session.commit()
                            break  # Success for this product
                        except Exception as db_err:
                            db.session.rollback()
                            db.session.remove()
                            if db_attempt == max_db_retries:
                                logger.error(f"MySQL sync failed for SKU {sku_id} after {max_db_retries} attempts: {db_err}")
                                break
                            logger.warning(f"MySQL sync failed for SKU {sku_id} on attempt {db_attempt}/{max_db_retries}. Retrying in 1s...")
                            import time
                            time.sleep(1)

                if task_id:
                    max_task_retries = 3
                    for task_attempt in range(1, max_task_retries + 1):
                        try:
                            active_task = db.session.get(ScraperTask, task_id)
                            if active_task:
                                active_task.total_found = processed_count
                                estimated_prog = min(99, int((active_task.total_found / (limit * len(pincode_list) if limit else 300)) * 100))
                                active_task.progress = max(active_task.progress, estimated_prog)

                                last_prod = pending_products[-1][0]
                                cat_lbl = last_prod.get('category_name') or "products"
                                active_task.status = f"Pincode {pin} ({idx}/{len(pincode_list)}): Scraped {active_task.total_found} products (last: {cat_lbl})"
                                db.session.commit()
                                break  # Success
                        except Exception as t_err:
                            db.session.rollback()
                            db.session.remove()
                            if task_attempt == max_task_retries:
                                logger.error(f"Failed to update task progress after {max_task_retries} attempts: {t_err}")
                                break
                            logger.warning(f"Task progress update failed on attempt {task_attempt}/{max_task_retries}. Retrying in 1s...")
                            import time
                            time.sleep(1)

                pending_products.clear()

            def on_product_saved_callback(product: dict, category_id: Optional[int] = None):
                nonlocal processed_count
                try:
                    sku_id = str(product.get('sku_id', '')).strip()
                    if not sku_id:
                        return

                    processed_count += 1
                    pending_products.append((product, category_id))

                    if len(pending_products) >= 50:
                        flush_pending_products()

                except Exception as sync_err:
                    logger.error(f"Real-time MySQL sync buffering failed for SKU {product.get('sku_id')}: {sync_err}")

            sqlite_db.on_category_saved = on_category_saved_callback
            sqlite_db.on_product_saved = on_product_saved_callback
            sqlite_db.connect()

            # Record run start time in UTC to match SQLite's CURRENT_TIMESTAMP
            import datetime
            # Buffer by 5 minutes to avoid clock discrepancies
            run_start_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

            try:
                # Count products already in SQLite before this run
                products_before = sqlite_db.get_product_count()

                # ── Category Infinite Scroll Scrape ──
                logger.info(f"Category PLP scrape for pincode {pin}...")

                async def _run_category():
                    async with DMartScraper(sqlite_db, pincode=pin) as scraper:
                        await scraper.run(max_categories=limit, categories_to_scrape=categories_list)

                asyncio.run(_run_category())
                try:
                    flush_pending_products()
                except Exception as flush_err:
                    logger.error(f"Final flush of buffered products failed: {flush_err}")
                products_after_cat = sqlite_db.get_product_count()
                logger.info(
                    f"Category scrape done. SQLite: {products_before} → {products_after_cat} "
                    f"(+{products_after_cat - products_before} new products)"
                )

                # ── Read categories from SQLite → Sync to MySQL (Double-safety fallback) ──
                logger.info("Syncing categories from SQLite → MySQL...")
                max_fallback_cat_retries = 3
                for fb_cat_attempt in range(1, max_fallback_cat_retries + 1):
                    try:
                        sqlite_db.cursor.execute("""
                            SELECT category_id, category_name, slug, parent_id, category_level, category_path
                            FROM dmart_category_master
                            ORDER BY category_level ASC
                        """)
                        cat_rows = sqlite_db.cursor.fetchall()
                        for cat_row in cat_rows:
                            c_id, c_name, c_slug, c_parent, c_level, c_path = cat_row

                            # Resolve MySQL parent ID
                            parent_mysql_id = None
                            if c_parent is not None:
                                try:
                                    sqlite_db.cursor.execute(
                                        "SELECT category_path FROM dmart_category_master WHERE category_id = ?",
                                        (c_parent,)
                                    )
                                    parent_row = sqlite_db.cursor.fetchone()
                                    if parent_row and parent_row[0]:
                                        parent_path = parent_row[0]
                                        parent_mysql_cat = DMartCategory.query.filter_by(category_path=parent_path).first()
                                        if parent_mysql_cat:
                                            parent_mysql_id = parent_mysql_cat.category_id
                                except Exception as parent_err:
                                    logger.warning(f"Fallback parent resolution failed: {parent_err}")

                            existing_cat = DMartCategory.query.filter_by(category_path=c_path).first()
                            if existing_cat:
                                existing_cat.category_name = c_name
                                existing_cat.slug = c_slug
                                existing_cat.parent_id = parent_mysql_id
                                existing_cat.category_level = c_level
                            else:
                                new_cat = DMartCategory(
                                    category_name = c_name,
                                    slug = c_slug,
                                    parent_id = parent_mysql_id,
                                    category_level = c_level,
                                    category_path = c_path
                                )
                                db.session.add(new_cat)
                        db.session.commit()
                        logger.info("Category fallback sync complete.")
                        break  # Success
                    except Exception as cat_fallback_err:
                        db.session.rollback()
                        db.session.remove()  # Crucial: discard dead connection context
                        if fb_cat_attempt == max_fallback_cat_retries:
                            logger.error(f"Fallback category sync failed after {max_fallback_cat_retries} attempts: {cat_fallback_err}")
                            break
                        logger.warning(f"Fallback category sync failed on attempt {fb_cat_attempt}/{max_fallback_cat_retries}. Retrying in 3s...")
                        import time
                        time.sleep(3)

                # ── Read new products from SQLite → Sync to MySQL (Double-safety fallback) ──
                logger.info(f"Reading products from SQLite modified since {run_start_time} for MySQL sync...")
                try:
                    sqlite_db.cursor.execute("""
                        SELECT
                            sku_id, product_name, brand, pack_size,
                            mrp, dmart_price, availability,
                            category_name, product_url, image_url, category_id
                        FROM dmart_product_master
                        WHERE scraped_at >= ?
                        ORDER BY scraped_at DESC
                    """, (run_start_time,))
                    rows = sqlite_db.cursor.fetchall()
                except Exception as e:
                    logger.error(f"SQLite read failed: {e}")
                    rows = []

                logger.info(f"Syncing {len(rows)} products from SQLite → MySQL...")
                inserted = 0
                updated = 0
                failed = 0

                for row in rows:
                    sku_id = None
                    max_fb_p_retries = 3
                    for fb_p_attempt in range(1, max_fb_p_retries + 1):
                        try:
                            (
                                sku_id, product_name, brand, pack_size,
                                mrp, dmart_price, availability,
                                category_name, product_url, image_url, category_id
                            ) = row

                            if not sku_id:
                                break

                            price_str    = str(dmart_price) if dmart_price is not None else "0.0"
                            mrp_str      = str(mrp) if mrp is not None else "0.0"
                            cat_str      = category_name or "Uncategorized"
                            name_str     = product_name or "Unknown Product"
                            from services.scrapers.dmart_engine.cleaner import DataCleaner
                            clean_name   = DataCleaner.clean_product_name(name_str)

                            # Resolve SQLite category_id to MySQL category_id by path
                            mysql_cat_id = None
                            if category_id:
                                try:
                                    sqlite_db.cursor.execute(
                                        "SELECT category_path FROM dmart_category_master WHERE category_id = ?",
                                        (category_id,)
                                    )
                                    row_path = sqlite_db.cursor.fetchone()
                                    if row_path and row_path[0]:
                                        cat_path = row_path[0]
                                        mysql_cat = DMartCategory.query.filter_by(category_path=cat_path).first()
                                        if mysql_cat:
                                            mysql_cat_id = mysql_cat.category_id
                                except Exception as path_err:
                                    logger.warning(f"Failed to map SQLite category ID {category_id} to MySQL category ID: {path_err}")
                            
                            if not mysql_cat_id and cat_str:
                                mysql_cat = DMartCategory.query.filter_by(category_path=cat_str).first()
                                if mysql_cat:
                                    mysql_cat_id = mysql_cat.category_id

                            import datetime
                            is_update = False
                            existing = DMart.query.filter_by(ASIN=sku_id).first()
                            if existing:
                                is_update = True
                                existing.title       = clean_name or existing.title
                                if image_url:
                                    existing.imgUrl  = image_url
                                existing.productUrl  = product_url or existing.productUrl
                                existing.price       = price_str
                                existing.listPrice   = mrp_str
                                # Defensively avoid overwriting categories with Uncategorized or null
                                if cat_str and cat_str not in ("Uncategorized", "null"):
                                    existing.categoryName = cat_str
                                if mysql_cat_id is not None:
                                    existing.category_id = mysql_cat_id
                                existing.brand       = brand or existing.brand
                                existing.quantity    = pack_size or existing.quantity
                                existing.availability = availability
                                existing.scraped_at  = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                            else:
                                new_product = DMart(
                                    asin         = sku_id,
                                    title        = clean_name,
                                    imgUrl       = image_url,
                                    productUrl   = product_url,
                                    price        = price_str,
                                    listPrice    = mrp_str,
                                    categoryName = cat_str,
                                    brand        = brand,
                                    category_id  = mysql_cat_id,
                                    quantity     = pack_size,
                                    availability = availability,
                                    scraped_at   = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                                )
                                db.session.add(new_product)

                            if is_update:
                                updated += 1
                            else:
                                inserted += 1

                            if (inserted + updated) % 200 == 0:
                                db.session.commit()
                            
                            break  # Success
                        except Exception as row_err:
                            db.session.rollback()
                            db.session.remove()  # Crucial: discard dead connection context
                            if fb_p_attempt == max_fb_p_retries:
                                failed += 1
                                logger.error(f"MySQL upsert failed for SKU {sku_id} after {max_fb_p_retries} attempts: {row_err}")
                                break
                            logger.warning(
                                f"Product sync for SKU {sku_id} failed on attempt {fb_p_attempt}/{max_fb_p_retries}. "
                                f"Discarded session, retrying in 2s..."
                            )
                            import time
                            time.sleep(2)

                # Final commit for remaining items
                try:
                    db.session.commit()
                except Exception as final_commit_err:
                    db.session.rollback()
                    db.session.remove()
                    logger.error(f"Final fallback commit failed: {final_commit_err}")

                logger.info(
                    f"MySQL sync complete: {inserted} new products inserted, {updated} existing products updated, {failed} failed "
                    f"from {len(rows)} total SQLite rows."
                )


                # ── Export master CSV from SQLite ──
                try:
                    master_csv = EXPORT_DIR / "dmart_master_report.csv"
                    rows_exported = sqlite_db.export_master_csv(master_csv)
                    logger.info(f"Master CSV exported: {master_csv} ({rows_exported} rows)")
                except Exception as csv_err:
                    logger.error(f"CSV export failed: {csv_err}")

            except Exception as e:
                db.session.rollback()
                db.session.remove()
                logger.error(f"Scrape failed for pincode {pin}: {e}", exc_info=True)
                if task_id:
                    try:
                        active_task = db.session.get(ScraperTask, task_id)
                        if active_task:
                            active_task.status = "ERROR"
                            active_task.error_message = str(e)
                            db.session.commit()
                    except Exception:
                        pass
                raise
            finally:
                sqlite_db.close()

        # Mark ScraperTask as COMPLETED
        if task_id:
            try:
                active_task = db.session.get(ScraperTask, task_id)
                if active_task:
                    active_task.status = "COMPLETED"
                    active_task.progress = 100
                    db.session.commit()
                    logger.info(f"ScraperTask {task_id} marked as COMPLETED")
            except Exception as t_err:
                logger.error(f"Failed to set task as COMPLETED: {t_err}")

        logger.info("=== DMart Celery Task COMPLETE ===")

if __name__ == '__main__':
    import argparse
    import os
    import sys
    
    # Ensure backend folder is in sys.path when running as CLI subprocess
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
        
    parser = argparse.ArgumentParser(description="DMart Scraper Standalone Process Runner")
    parser.add_argument("--search_term", type=str, required=True)
    parser.add_argument("--mode", type=str, default="category")
    parser.add_argument("--pincodes", type=str, default="all")
    parser.add_argument("--max_categories", type=int, default=None)
    parser.add_argument("--task_id", type=int, default=None)
    parser.add_argument("--categories", type=str, default=None)
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s : %(message)s")
    
    scrape_dmart_search(
        search_term=args.search_term,
        mode=args.mode,
        pincodes=args.pincodes,
        max_categories=args.max_categories,
        task_id=args.task_id,
        categories=args.categories
    )
