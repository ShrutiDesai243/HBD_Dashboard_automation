"""
Blinkit Scraper Service — Main Orchestrator
============================================
Entry point for the Blinkit automation system.
Uses BlinkitPlaywrightScraper to bypass block issues.

Key fix: sync_categories() now returns (stats, live_to_db) so that
product insertion uses DB category IDs (not live Blinkit IDs).
"""

import os
import re
import sys
import json
import time
import logging
import argparse
import asyncio
from typing import Optional, Dict

# ── Path Setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.scrapers.blinkit_engine.config import (
    DEFAULT_PINCODE, LOGS_DIR, MODE_FULL, MODE_CATEGORIES, MODE_INCREMENTAL,
)
from services.scrapers.blinkit_engine.playwright_scraper import BlinkitPlaywrightScraper
from services.scrapers.blinkit_engine.database_sync import BlinkitDatabaseSync
from services.scrapers.blinkit_engine.progress_tracker import BlinkitProgressTracker


def _setup_logger(task_id: Optional[int] = None) -> logging.Logger:
    """Configure logging to both console and file."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s : %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]

    if task_id:
        log_file = LOGS_DIR / f"blinkit_task_{task_id}.log"
        handlers.append(logging.FileHandler(str(log_file), encoding="utf-8", mode="w"))

    logging.basicConfig(level=logging.INFO, format=log_format, handlers=handlers)
    return logging.getLogger(__name__)


def _get_db_config() -> dict:
    """Load DB config from environment."""
    from dotenv import load_dotenv
    env_path = os.path.join(BACKEND_DIR, ".env")
    load_dotenv(env_path, override=True)

    return {
        "host":     os.getenv("DB_HOST", "localhost"),
        "user":     os.getenv("DB_USER", "").strip(),
        "password": os.getenv("DB_PASSWORD", "").strip(),
        "db":       os.getenv("DB_NAME", ""),
        "port":     int(os.getenv("DB_PORT", 3306)),
    }


def _update_task(task_id: Optional[int], status: str, progress: int, total_found: int = 0,
                  error_message: Optional[str] = None):
    """Update ScraperTask record in MySQL."""
    if not task_id:
        return
    try:
        from app import app
        from extensions import db
        from model.scraper_task import ScraperTask
        with app.app_context():
            task = db.session.get(ScraperTask, task_id)
            if task:
                task.status = status
                task.progress = progress
                task.total_found = total_found
                if error_message:
                    task.error_message = str(error_message)[:2000]
                db.session.commit()
    except Exception as e:
        logging.getLogger(__name__).warning(f"[Task] Failed to update ScraperTask {task_id}: {e}")


def scrape_blinkit(
    task_id: Optional[int] = None,
    pincode: str = DEFAULT_PINCODE,
    mode: str = MODE_FULL,
    max_categories: Optional[int] = None,
    resume: bool = False,
    selected_categories: Optional[list] = None,
):
    """
    Main Blinkit scraping orchestrator (called from Celery subprocess).
    """
    logger = _setup_logger(task_id)
    db_config = _get_db_config()

    logger.info("=" * 60)
    logger.info("=== Blinkit Playwright Automation Scraper START ===")
    logger.info(f"[CONFIG] task_id={task_id} | pincode={pincode} | mode={mode} | max_cat={max_categories}")
    if selected_categories:
        logger.info(f"[CONFIG] Selected categories filter: {selected_categories}")
    logger.info("=" * 60)

    _update_task(task_id, f"Initializing | pincode={pincode}", 0)

    db_sync = BlinkitDatabaseSync(db_config)

    async def _async_run():
        try:
            db_sync.connect()
            tracker = BlinkitProgressTracker()

            if not resume:
                tracker.reset(pincode=pincode, mode=mode)
                logger.info("[State] Fresh run — state reset")
            else:
                logger.info(f"[State] Resuming from: products_scraped={tracker.get('products_scraped', 0)}")

            # Start Playwright Scraper context
            async with BlinkitPlaywrightScraper(db_sync, pincode, tracker, task_id) as scraper:

                # Step 1: Set pincode via UI interaction
                _update_task(task_id, f"Setting location to {pincode}...", 3)
                await scraper.set_pincode_location()

                # Step 2: Category Discovery
                _update_task(task_id, "Discovering categories...", 5)
                discovered_categories = await scraper.discover_categories()
                logger.info(f"[Phase1] Discovered {len(discovered_categories)} categories from Blinkit.")

                if not discovered_categories:
                    # Fallback to existing mapping from DB if discovery failed
                    logger.warning("[Phase1] Category discovery returned empty. Reading categories from DB mapping...")
                    with db_sync._conn.cursor() as cur:
                        cur.execute("""
                            SELECT category_id, category_name, parent_id, full_category_path
                            FROM blinkit_mapping
                            ORDER BY category_level, category_id
                        """)
                        rows = cur.fetchall()
                        discovered_categories = [
                            {
                                "category_id": r["category_id"],
                                "category_name": r["category_name"],
                                "slug": slugify(r["category_name"]),
                                "parent_id": r["parent_id"],
                                "category_level": 2 if r["parent_id"] != 0 else 1,
                                "full_category_path": r["full_category_path"],
                            }
                            for r in rows
                        ]
                    logger.info(f"[Phase1] Using {len(discovered_categories)} fallback categories from DB mapping.")

                # Sync and normalize category mapping.
                # IMPORTANT: sync_categories() returns (stats, live_to_db)
                # live_to_db maps live Blinkit category IDs → DB category IDs.
                _update_task(task_id, f"Syncing and translating {len(discovered_categories)} categories...", 10)
                cat_stats, live_to_db = db_sync.sync_categories(discovered_categories)
                tracker.set("categories_synced", cat_stats.get("inserted", 0))
                logger.info(f"[Phase1] Category sync & translation completed: {cat_stats}")
                logger.info(f"[Phase1] live_to_db map has {len(live_to_db)} entries.")

                if mode == MODE_CATEGORIES:
                    logger.info("[Phase1] Mode=categories — complete.")
                    tracker.mark_complete()
                    _update_task(task_id, "COMPLETED", 100)
                    return

                # Leaf categories for product scraping (level 2 categories)
                leaf_categories = [c for c in discovered_categories if c.get("category_level", 1) == 2]
                if not leaf_categories:
                    leaf_categories = discovered_categories

                # Apply selected_categories filter (user picked specific L1 categories in UI)
                if selected_categories:
                    sel_lower = {s.strip().lower() for s in selected_categories}
                    filtered = []
                    for c in leaf_categories:
                        # Get the parent category name
                        parent_db_id = int(c.get("parent_id") or 0)
                        parent_cat = c.get("category_name", "")
                        # Check if this subcategory's parent is in the selected list
                        parent_found = False
                        for discovered in discovered_categories:
                            db_id = discovered.get("_db_category_id") or discovered.get("category_id")
                            if db_id and int(db_id) == parent_db_id:
                                if discovered.get("category_name", "").strip().lower() in sel_lower:
                                    parent_found = True
                                break
                        if parent_found:
                            filtered.append(c)
                    if filtered:
                        leaf_categories = filtered
                        logger.info(f"[Phase1] Applied category filter: {len(leaf_categories)} subcategories in selected L1 categories.")
                    else:
                        logger.warning(f"[Phase1] Category filter matched 0 subcategories, ignoring filter.")

                if max_categories:
                    leaf_categories = leaf_categories[:max_categories]
                    logger.info(f"[Phase1] Limited to {max_categories} categories for testing.")

                tracker.set("total_categories", len(leaf_categories))
                logger.info(f"[Phase1] Will scrape {len(leaf_categories)} subcategories for products.")

                # Build parent name map using DB IDs (after sync_categories translated them)
                # discovered_categories have been mutated in-place by sync_categories to use DB IDs
                parent_name_map: Dict[int, str] = {}
                for c in discovered_categories:
                    if c.get("category_level", 1) == 1:
                        db_cat_id = c.get("_db_category_id") or c.get("category_id")
                        if db_cat_id:
                            parent_name_map[int(db_cat_id)] = c.get("category_name", "Category")

                # Step 3: Product Scraping
                _update_task(task_id, "Scraping products...", 15)
                total_categories = len(leaf_categories)

                total_scraped = tracker.get("products_scraped", 0)
                total_inserted = tracker.get("products_inserted", 0)
                total_updated = tracker.get("products_updated", 0)
                total_skipped = tracker.get("products_skipped", 0)
                total_failed = tracker.get("products_failed", 0)

                # Product sync callback
                def on_product_batch(products: list, live_sub_id: int):
                    """
                    Called when a batch of products is scraped for a subcategory.
                    live_sub_id is the LIVE Blinkit subcategory ID — must be translated
                    to the DB category_id using live_to_db before storing.
                    """
                    nonlocal total_scraped, total_inserted, total_updated, total_skipped, total_failed

                    # Translate live subcategory ID → DB category ID
                    db_cat_id = live_to_db.get(live_sub_id)
                    if db_cat_id is None:
                        # Try the ID directly (may already be a DB ID)
                        db_cat_id = live_sub_id
                        logger.warning(
                            f"[Phase2] live_sub_id={live_sub_id} not in live_to_db map. "
                            f"Using raw ID={db_cat_id}. Check category discovery."
                        )

                    for p in products:
                        p["category_id"] = db_cat_id

                    stats = db_sync.sync_products(products)

                    total_scraped += len(products)
                    total_inserted += stats.get("inserted", 0)
                    total_updated += stats.get("updated", 0)
                    total_skipped += stats.get("skipped", 0)
                    total_failed += stats.get("failed", 0)

                    tracker.increment("products_scraped", len(products))
                    tracker.increment("products_inserted", stats.get("inserted", 0))
                    tracker.increment("products_updated", stats.get("updated", 0))
                    tracker.increment("products_skipped", stats.get("skipped", 0))
                    tracker.increment("products_failed", stats.get("failed", 0))
                    tracker.save()

                for cat_idx, cat in enumerate(leaf_categories, 1):
                    # Use DB category ID (resolved by sync_categories)
                    cat_db_id = cat.get("_db_category_id") or cat.get("category_id")
                    live_cat_id = cat.get("category_id")  # original live id from Blinkit
                    cat_name = cat.get("category_name", "Unknown")

                    # Parent ID after sync_categories resolution
                    parent_db_id = int(cat.get("parent_id") or 0)
                    parent_name = parent_name_map.get(parent_db_id, "Category")

                    if resume and tracker.is_category_completed(cat_db_id):
                        logger.info(f"[Phase2] [{cat_idx}/{total_categories}] SKIP (already done): {cat_name}")
                        continue

                    progress_pct = 15 + int((cat_idx / total_categories) * 80)
                    status_msg = (
                        f"Scraping [{cat_idx}/{total_categories}] {cat_name} | "
                        f"Products: {total_scraped:,} | "
                        f"Inserted: {total_inserted:,}"
                    )
                    logger.info(f"[Phase2] {status_msg}")
                    _update_task(task_id, status_msg, progress_pct, total_found=total_scraped)

                    tracker.set("current_category_id", cat_db_id)

                    # Scrape — pass live_cat_id as subcategory_id since the playwright
                    # scraper builds URLs from live IDs, and the on_product_batch callback
                    # receives the live_sub_id to translate via live_to_db.
                    await scraper.scrape_subcategory_products(
                        parent_id=parent_db_id,
                        subcategory_id=int(live_cat_id),   # live ID for URL building
                        parent_name=parent_name,
                        subcategory_name=cat_name,
                        on_product_batch=on_product_batch,
                    )

                    tracker.add_completed_category(cat_db_id)
                    tracker.save()

                # Final completed marker
                tracker.mark_complete()
                final_counts = db_sync.get_current_counts()
                logger.info(f"[Done] Final DB counts: {final_counts}")
                logger.info("=== Blinkit Automation Scraper COMPLETE ===")
                _update_task(task_id, "COMPLETED", 100, total_found=total_scraped)

        except Exception as e:
            logger.error(f"[FATAL] Async scraper loop crashed: {e}", exc_info=True)
            tracker.add_error(str(e))
            tracker.save()
            _update_task(task_id, "ERROR", 0, error_message=str(e)[:2000])
            raise
        finally:
            db_sync.disconnect()

    # Run the async loop synchronously
    asyncio.run(_async_run())


def slugify(text: str) -> str:
    """Helper to slugify category names."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


# ── CLI Entry Point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Blinkit Playwright Automation Scraper")
    parser.add_argument("--task_id",              type=int,   default=None)
    parser.add_argument("--pincode",              type=str,   default=DEFAULT_PINCODE)
    parser.add_argument("--mode",                 type=str,   default=MODE_FULL,
                        choices=[MODE_FULL, MODE_CATEGORIES, MODE_INCREMENTAL])
    parser.add_argument("--max_categories",       type=int,   default=None)
    parser.add_argument("--resume",               action="store_true", default=False)
    parser.add_argument("--selected_categories",  type=str,   default=None,
                        help="JSON list of L1 category names to scrape")
    args = parser.parse_args()

    sel_cats = None
    if args.selected_categories:
        try:
            sel_cats = json.loads(args.selected_categories)
        except Exception:
            sel_cats = None

    scrape_blinkit(
        task_id=args.task_id,
        pincode=args.pincode,
        mode=args.mode,
        max_categories=args.max_categories,
        resume=args.resume,
        selected_categories=sel_cats,
    )
