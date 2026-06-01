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
from services.scrapers.dmart_engine.sitemap_runner import SitemapRunner

logger = logging.getLogger(__name__)


def scrape_dmart_search(
    search_term: str,
    mode: str = "category",
    pincodes: str = "400001",
    max_categories: Optional[int] = None,
    task_id: Optional[int] = None
):
    """
    Celery-compatible entry point for the DMart scraper.

    Modes:
        category — Infinite scroll PLP scraping (default)
        sitemap  — PDP scraping via XML sitemap
        hybrid   — Category scrape + sitemap fill for missing descriptions

    After each pincode's scrape completes, all products in SQLite
    (dmart_product_master) are synced to MySQL (dmart_products table).
    """
    from app import app
    from extensions import db
    from model.product_model.additional_products import DMart, DMartCategory
    from model.scraper_task import ScraperTask

    with app.app_context():
        # ── Retrieve Task for progress updates ──
        task = None
        if task_id:
            try:
                task = ScraperTask.query.get(task_id)
                if task:
                    task.status = "RUNNING"
                    task.progress = 0
                    db.session.commit()
                    logger.info(f"ScraperTask {task_id} initialized to RUNNING")
            except Exception as e:
                logger.warning(f"Failed to fetch/initialize ScraperTask in start: {e}")

        # ── Parse pincode list ──
        if str(pincodes).strip().lower() == "all":
            from services.scrapers.dmart_engine.config import PINCODE_LIST
            pincode_list = PINCODE_LIST
        else:
            pincode_list = [p.strip() for p in str(pincodes).split(",") if p.strip()]

        limit = int(max_categories) if max_categories else None

        logger.info(
            f"=== DMart Scraper START | mode={mode} | "
            f"pincodes={pincode_list[:3]}... | max_cat={limit} ==="
        )

        for idx, pin in enumerate(pincode_list, 1):
            logger.info(f"[{idx}/{len(pincode_list)}] Running scrape for pincode: {pin}")

            import datetime
            # Buffer by 5 minutes to prevent missing rows due to execution lag or time difference
            run_start_time = (datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

            if task:
                try:
                    db.session.refresh(task)
                    task.status = f"Pincode {pin} ({idx}/{len(pincode_list)}): Initializing browser..."
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
                        cat_id = category.get('category_id')
                        name = category.get('category_name')
                        slug = category.get('slug')
                        parent_id = category.get('parent_id')
                        level = category.get('category_level')
                        category_path = category.get('category_path')

                        existing_cat = DMartCategory.query.filter_by(category_id=cat_id).first()
                        if existing_cat:
                            existing_cat.category_name = name
                            existing_cat.slug = slug
                            existing_cat.parent_id = parent_id
                            existing_cat.category_level = level
                            existing_cat.category_path = category_path
                        else:
                            new_cat = DMartCategory(
                                category_id = cat_id,
                                category_name = name,
                                slug = slug,
                                parent_id = parent_id,
                                category_level = level,
                                category_path = category_path
                            )
                            db.session.add(new_cat)
                        db.session.commit()
                        logger.info(f"Synchronized category '{name}' (ID={cat_id}) to MySQL")
                        break  # Success
                    except Exception as cat_err:
                        db.session.rollback()
                        db.session.remove()  # Crucial: discard dead connection context
                        if attempt == max_retries:
                            logger.error(f"Real-time MySQL category sync failed for ID {category.get('category_id')} after {max_retries} attempts: {cat_err}")
                            break
                        logger.warning(f"Category sync failed on attempt {attempt}/{max_retries}. Discarded connection, retrying in 2s...")
                        import time
                        time.sleep(2)

            def on_product_saved_callback(product: dict, category_id: Optional[int] = None):
                try:
                    sku_id = str(product.get('sku_id', '')).strip()
                    if not sku_id:
                        return

                    product_name = product.get('product_name') or "Unknown Product"
                    brand = product.get('brand')
                    pack_size = product.get('pack_size')
                    mrp = product.get('mrp')
                    dmart_price = product.get('dmart_price')
                    availability = product.get('availability')
                    category_name = product.get('category_name') or "Uncategorized"
                    product_url = product.get('product_url')
                    image_url = product.get('image_url')
                    description = product.get('description')

                    price_str = str(dmart_price) if dmart_price is not None else "0.0"
                    mrp_str = str(mrp) if mrp is not None else "0.0"

                    # Sync product to MySQL dmart_products with self-healing retry logic
                    max_db_retries = 3
                    for db_attempt in range(1, max_db_retries + 1):
                        try:
                            existing = DMart.query.filter_by(asin=sku_id).first()
                            if existing:
                                existing.title       = product_name
                                existing.imgUrl      = image_url
                                existing.productUrl  = product_url
                                existing.price       = price_str
                                existing.listPrice   = mrp_str
                                existing.categoryName = category_name
                                existing.brand       = brand
                                existing.description = description
                                existing.category_id = category_id
                                existing.quantity    = pack_size
                            else:
                                new_product = DMart(
                                    asin         = sku_id,
                                    title        = product_name,
                                    imgUrl       = image_url,
                                    productUrl   = product_url,
                                    stars        = "0.0",
                                    reviews      = "0",
                                    price        = price_str,
                                    listPrice    = mrp_str,
                                    categoryName = category_name,
                                    brand        = brand,
                                    description  = description,
                                    category_id  = category_id,
                                    quantity     = pack_size
                                )
                                db.session.add(new_product)
                            
                            db.session.commit()
                            break  # Success
                        except Exception as db_err:
                            db.session.rollback()
                            db.session.remove()  # Crucial: discard dead connection context
                            if db_attempt == max_db_retries:
                                raise db_err
                            logger.warning(
                                f"Product sync failed on attempt {db_attempt}/{max_db_retries} for SKU {sku_id}. "
                                f"Discarded session, retrying in 2s..."
                            )
                            import time
                            time.sleep(2)

                    # Update ScraperTask status and progress
                    if task:
                        max_task_retries = 3
                        for task_attempt in range(1, max_task_retries + 1):
                            try:
                                db.session.refresh(task)
                                task.total_found = task.total_found + 1
                                
                                # Estimate progress based on found products
                                estimated_prog = min(99, int((task.total_found / (limit * len(pincode_list) if limit else 300)) * 100))
                                task.progress = max(task.progress, estimated_prog)
                                
                                cat_lbl = category_name or "products"
                                task.status = f"Pincode {pin} ({idx}/{len(pincode_list)}): Scraped {task.total_found} products (last: {cat_lbl})"
                                db.session.commit()
                                break  # Success
                            except Exception as t_err:
                                db.session.rollback()
                                db.session.remove()  # Crucial: discard dead connection context
                                if task_attempt == max_task_retries:
                                    logger.error(f"Failed to update task progress after {max_task_retries} attempts: {t_err}")
                                    break
                                logger.warning(f"Task progress update failed on attempt {task_attempt}/{max_task_retries}. Retrying in 2s...")
                                import time
                                time.sleep(2)

                except Exception as sync_err:
                    logger.error(f"Real-time MySQL sync failed for SKU {product.get('sku_id')}: {sync_err}")

            sqlite_db.on_category_saved = on_category_saved_callback
            sqlite_db.on_product_saved = on_product_saved_callback
            sqlite_db.connect()

            try:
                # Count products already in SQLite before this run
                products_before = sqlite_db.get_product_count()

                # ── Mode: Category Infinite Scroll ──
                if mode in ("category", "hybrid"):
                    logger.info(f"Stage 1: Category PLP scrape for pincode {pin}...")

                    async def _run_category():
                        async with DMartScraper(sqlite_db, pincode=pin) as scraper:
                            await scraper.run(max_categories=limit)

                    asyncio.run(_run_category())
                    products_after_cat = sqlite_db.get_product_count()
                    logger.info(
                        f"Category scrape done. SQLite: {products_before} → {products_after_cat} "
                        f"(+{products_after_cat - products_before} new products)"
                    )

                # ── Mode: Sitemap PDP Scraping ──
                if mode == "sitemap":
                    sitemap_limit = int(search_term) if str(search_term).isdigit() else 50
                    logger.info(f"Sitemap mode: scraping {sitemap_limit} PDPs for pincode {pin}...")
                    runner = SitemapRunner(sqlite_db, pincode=pin)
                    asyncio.run(runner.run(limit=sitemap_limit))

                # ── Mode: Hybrid Stage 2 — fill missing descriptions ──
                if mode == "hybrid":
                    try:
                        missing_urls = sqlite_db.get_products_missing_descriptions()
                        if missing_urls:
                            logger.info(
                                f"Hybrid Stage 2: filling descriptions for "
                                f"{len(missing_urls)} products..."
                            )
                            runner = SitemapRunner(sqlite_db, pincode=pin)
                            asyncio.run(runner.run(
                                limit=len(missing_urls),
                                custom_urls=missing_urls
                            ))
                        else:
                            logger.info("Hybrid Stage 2: no missing descriptions. Skipping.")
                    except Exception as e:
                        logger.error(f"Hybrid Stage 2 failed: {e}")

                # ── Read categories from SQLite → Sync to MySQL (Double-safety fallback) ──
                logger.info("Syncing categories from SQLite → MySQL...")
                max_fallback_cat_retries = 3
                for fb_cat_attempt in range(1, max_fallback_cat_retries + 1):
                    try:
                        sqlite_db.cursor.execute("""
                            SELECT category_id, category_name, slug, parent_id, category_level, category_path
                            FROM dmart_category_master
                        """)
                        cat_rows = sqlite_db.cursor.fetchall()
                        for cat_row in cat_rows:
                            c_id, c_name, c_slug, c_parent, c_level, c_path = cat_row
                            existing_cat = DMartCategory.query.filter_by(category_id=c_id).first()
                            if existing_cat:
                                existing_cat.category_name = c_name
                                existing_cat.slug = c_slug
                                existing_cat.parent_id = c_parent
                                existing_cat.category_level = c_level
                                existing_cat.category_path = c_path
                            else:
                                new_cat = DMartCategory(
                                    category_id = c_id,
                                    category_name = c_name,
                                    slug = c_slug,
                                    parent_id = c_parent,
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
                logger.info("Reading products from SQLite for MySQL sync...")
                try:
                    sqlite_db.cursor.execute("""
                        SELECT
                            sku_id, product_name, brand, pack_size,
                            mrp, dmart_price, availability,
                            category_name, product_url, image_url, description, category_id
                        FROM dmart_product_master
                        WHERE scraped_at >= ?
                        ORDER BY scraped_at DESC
                    """, (run_start_time,))
                    rows = sqlite_db.cursor.fetchall()
                except Exception as e:
                    logger.error(f"SQLite read failed: {e}")
                    rows = []

                logger.info(f"Syncing {len(rows)} products from SQLite → MySQL...")
                synced = 0
                failed = 0

                for row in rows:
                    sku_id = None
                    max_fb_p_retries = 3
                    for fb_p_attempt in range(1, max_fb_p_retries + 1):
                        try:
                            (
                                sku_id, product_name, brand, pack_size,
                                mrp, dmart_price, availability,
                                category_name, product_url, image_url, description, category_id
                            ) = row

                            if not sku_id:
                                break

                            price_str    = str(dmart_price) if dmart_price is not None else "0.0"
                            mrp_str      = str(mrp) if mrp is not None else "0.0"
                            cat_str      = category_name or "Uncategorized"
                            name_str     = product_name or "Unknown Product"

                            existing = DMart.query.filter_by(asin=sku_id).first()
                            if existing:
                                existing.title       = name_str
                                existing.imgUrl      = image_url
                                existing.productUrl  = product_url
                                existing.price       = price_str
                                existing.listPrice   = mrp_str
                                existing.categoryName = cat_str
                                existing.brand       = brand
                                existing.description = description
                                existing.category_id = category_id
                                existing.quantity    = pack_size
                            else:
                                new_product = DMart(
                                    asin         = sku_id,
                                    title        = name_str,
                                    imgUrl       = image_url,
                                    productUrl   = product_url,
                                    stars        = "0.0",
                                    reviews      = "0",
                                    price        = price_str,
                                    listPrice    = mrp_str,
                                    categoryName = cat_str,
                                    brand        = brand,
                                    description  = description,
                                    category_id  = category_id,
                                    quantity     = pack_size
                                )
                                db.session.add(new_product)

                            synced += 1
                            if synced % 200 == 0:
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
                    f"MySQL sync complete: {synced} synced, {failed} failed "
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
                if task:
                    try:
                        db.session.refresh(task)
                        task.status = "ERROR"
                        task.error_message = str(e)
                        db.session.commit()
                    except Exception:
                        pass
                raise
            finally:
                sqlite_db.close()

        # Mark ScraperTask as COMPLETED
        if task:
            try:
                db.session.refresh(task)
                task.status = "COMPLETED"
                task.progress = 100
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
    parser.add_argument("--pincodes", type=str, default="400001")
    parser.add_argument("--max_categories", type=int, default=None)
    parser.add_argument("--task_id", type=int, default=None)
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s : %(message)s")
    
    scrape_dmart_search(
        search_term=args.search_term,
        mode=args.mode,
        pincodes=args.pincodes,
        max_categories=args.max_categories,
        task_id=args.task_id
    )
