import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)



def _bootstrap_flask_app():
    """Import app and extensions lazily so this adapter can run
    as a standalone subprocess.

    Zepto subprocess imports backend/app.py which in turn imports Celery tasks.
    Those tasks configure FileHandler paths during import time.

    To prevent startup crashes, we pre-create the expected log directory/file.
    """

    # Make Flask-SQLAlchemy bootstrap resilient in the subprocess.
    os.environ.setdefault("SKIP_DB_CREATE_ALL", "1")

    # Ensure backend/output exists (celery tasks write logs under output/).
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    output_dir = repo_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create known log file path(s) referenced during import.
    # (If more are needed, they can be added here.)
    gdrive_log = output_dir / "gdrive_etl.log"
    if not gdrive_log.exists():
        gdrive_log.write_text("", encoding="utf-8")

    from app import app as flask_app
    return flask_app



def _ensure_schema(sql_path: str, db_engine):
    # Best-effort: Zepto engine writes its own schema via sqlite scripts,
    # but MySQL needs tables to exist.
    if not os.path.exists(sql_path):
        return
    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            db_engine.execute(db_engine.text(stmt))


def upsert_mysql_schema():
    # Create MySQL tables for Zepto if not exists.
    from extensions import db

    create_categories_sql = """
    CREATE TABLE IF NOT EXISTS `zepto_categories` (
      `category_id` int NOT NULL AUTO_INCREMENT,
      `category_name` varchar(255) NOT NULL,
      `parent_id` int DEFAULT NULL,
      `category_level` int DEFAULT NULL,
      `category_path` varchar(512) DEFAULT NULL,
      PRIMARY KEY (`category_id`),
      FOREIGN KEY (`parent_id`) REFERENCES `zepto_categories` (`category_id`) ON DELETE SET NULL
    );
    """

    create_products_sql = """
    CREATE TABLE IF NOT EXISTS `zepto_products` (
      `id` int NOT NULL AUTO_INCREMENT,
      `sku_id` varchar(100) NOT NULL UNIQUE,
      `product_name` varchar(512) NOT NULL,
      `quantity` varchar(255) DEFAULT NULL,
      `rating` varchar(50) DEFAULT NULL,
      `review` varchar(50) DEFAULT NULL,
      `mrp` decimal(12,2) DEFAULT NULL,
      `selling_price` decimal(12,2) DEFAULT NULL,
      `main_category` varchar(255) DEFAULT NULL,
      `subcategory` varchar(255) DEFAULT NULL,
      `product_url` text DEFAULT NULL,
      `image_url` text DEFAULT NULL,
      `scraped_at` datetime DEFAULT NULL,
      `product_description` text DEFAULT NULL,
      `availability` int DEFAULT 1,
      `category_id` int DEFAULT NULL,
      `pack_size` varchar(100) DEFAULT NULL,
      PRIMARY KEY (`id`),
      INDEX (`category_id`),
      FOREIGN KEY (`category_id`) REFERENCES `zepto_categories` (`category_id`) ON DELETE SET NULL
    );
    """

    db.session.execute(db.text(create_categories_sql))
    db.session.execute(db.text(create_products_sql))
    db.session.commit()


def parse_pincodes(pincodes: str):
    if not pincodes or str(pincodes).strip().lower() == "all":
        return None
    return [p.strip() for p in str(pincodes).split(",") if p.strip()]


def run_zepto_scrape(
    pincodes: str = "all",
    max_categories: Optional[int] = None,
    task_id: Optional[int] = None,
    categories: Optional[str] = None,
):
    """Standalone entrypoint for the Zepto scraper subprocess."""
    from extensions import db
    from model.scraper_task import ScraperTask

    from services.scrapers.zepto_engine.config import PINCODE_GEO_MAP, DB_PATH, SCHEMA_PATH
    from services.scrapers.zepto_engine.database import DatabaseManager
    from services.scrapers.zepto_engine.scraper import ZeptoScraper

    app = _bootstrap_flask_app()

    with app.app_context():
        # Ensure MySQL schema exists (best-effort: MySQL may be intermittently unavailable)
        try:
            upsert_mysql_schema()
        except Exception as e:
            logger.warning(f"MySQL schema init skipped (will proceed with SQLite-only scrape): {e}")

        # Initialize task
        if task_id:
            try:
                task = ScraperTask.query.get(task_id)
                if task:
                    task.status = "RUNNING"
                    task.progress = 0
                    task.total_found = 0
                    db.session.commit()
                    logger.info(f"ScraperTask {task_id} initialized to RUNNING")
            except Exception as e:
                logger.warning(f"Failed to initialize ScraperTask in MySQL (continuing): {e}")


        pincodes_list = parse_pincodes(pincodes)
        if pincodes_list is None:
            pincodes_list = list(PINCODE_GEO_MAP.keys())

        categories_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None

        limit = int(max_categories) if max_categories else None

        # If categories filter is provided but resolves to empty, fall back to scraping all discovered categories.
        # This prevents engine runs with categories=0 (which produces empty JSONL + no MySQL sync).
        if categories_list is not None and len(categories_list) == 0:
            logger.warning("Zepto service received an empty --categories list; will fall back to scraping all categories.")
            categories_list = None

        if categories_list is not None:
            logger.info(f"Zepto service category filter enabled: {categories_list}")
        else:
            logger.info("Zepto service category filter disabled: scraping all discovered categories")

        for idx, pin in enumerate(pincodes_list, 1):
            logger.info(f"[{idx}/{len(pincodes_list)}] Zepto scrape pincode={pin}")

            sqlite_db = DatabaseManager(str(DB_PATH), str(SCHEMA_PATH))
            sqlite_db.on_category_saved = None
            sqlite_db.on_product_saved = None

            # Real-time MySQL sync callbacks
            def on_category_saved_callback(category: dict):
                # Insert category into MySQL; use natural key (name+parent_id) not unique.
                # Keep it simple and idempotent by looking up category by category_name+parent_id.
                try:
                    name = category.get("category_name")
                    parent_id = category.get("parent_id")
                    level = category.get("category_level")
                    path = category.get("category_path")

                    # parent_id mapping from SQLite ids -> MySQL ids is not 1:1.
                    # We'll just upsert using category_name+path uniqueness via SELECT.
                    existing = db.session.execute(
                        db.text("SELECT category_id FROM zepto_categories WHERE category_name=:n AND category_path=:p LIMIT 1"),
                        {"n": name, "p": path},
                    ).fetchone()

                    if existing:
                        mysql_cat_id = existing[0]
                        db.session.execute(
                            db.text(
                                "UPDATE zepto_categories SET category_level=:l, parent_id=:parent_id, category_path=:p WHERE category_id=:id"
                            ),
                            {"l": level, "parent_id": None, "p": path, "id": mysql_cat_id},
                        )
                    else:
                        res = db.session.execute(
                            db.text(
                                "INSERT INTO zepto_categories(category_name,parent_id,category_level,category_path) VALUES(:n,NULL,:l,:p)"
                            ),
                            {"n": name, "l": level, "p": path},
                        )
                        mysql_cat_id = res.lastrowid

                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    logger.warning(f"MySQL category callback failed: {e}")

            def on_product_saved_callback(product: dict, category_id=None):
                try:
                    # category_id is SQLite category_id; we don't have a deterministic mapping.
                    # We'll resolve MySQL category_id using product main/subcategory path if needed.
                    product_name = product.get("product_name")
                    sku_id = str(product.get("sku_id") or "").strip()
                    if not sku_id or not product_name:
                        return

                    main_cat = product.get("main_category")
                    sub_cat = product.get("subcategory")
                    path = f"{main_cat} > {sub_cat}" if sub_cat else (main_cat or None)

                    # resolve category_id in MySQL by category_path
                    cat_row = db.session.execute(
                        db.text(
                            "SELECT category_id FROM zepto_categories WHERE category_path=:p LIMIT 1"
                        ),
                        {"p": path},
                    ).fetchone()
                    mysql_cat_id = cat_row[0] if cat_row else None

                    # Secondary dedupe handled in SQLite; MySQL primary dedupe by sku_id.
                    db.session.execute(
                        db.text(
                            """
                            INSERT INTO zepto_products(
                                sku_id, product_name, quantity, rating, review, mrp, selling_price,
                                main_category, subcategory, product_url, image_url, scraped_at,
                                product_description, availability, category_id, pack_size
                            ) VALUES(
                                :sku_id, :product_name, :quantity, :rating, :review, :mrp, :selling_price,
                                :main_category, :subcategory, :product_url, :image_url, :scraped_at,
                                :product_description, :availability, :category_id, :pack_size
                            )
                            ON DUPLICATE KEY UPDATE
                                product_name=VALUES(product_name),
                                quantity=VALUES(quantity),
                                rating=VALUES(rating),
                                review=VALUES(review),
                                mrp=VALUES(mrp),
                                selling_price=VALUES(selling_price),
                                main_category=VALUES(main_category),
                                subcategory=VALUES(subcategory),
                                product_url=VALUES(product_url),
                                image_url=VALUES(image_url),
                                scraped_at=VALUES(scraped_at),
                                product_description=VALUES(product_description),
                                availability=VALUES(availability),
                                category_id=COALESCE(VALUES(category_id), category_id),
                                pack_size=VALUES(pack_size)
                            """
                        ),
                        {
                            "sku_id": sku_id,
                            "product_name": product_name,
                            "quantity": product.get("quantity"),
                            "rating": str(product.get("rating")) if product.get("rating") is not None else None,
                            "review": str(product.get("review")) if product.get("review") is not None else None,
                            "mrp": product.get("mrp"),
                            "selling_price": product.get("selling_price"),
                            "main_category": product.get("main_category"),
                            "subcategory": product.get("subcategory"),
                            "product_url": product.get("product_url"),
                            "image_url": product.get("image_url"),
                            "scraped_at": product.get("scraped_at"),
                            "product_description": product.get("product_description"),
                            "availability": int(product.get("availability") or 1),
                            "category_id": mysql_cat_id,
                            "pack_size": product.get("pack_size"),
                        },
                    )

                    # Update task counters lightly
                    if task_id:
                        t = ScraperTask.query.get(task_id)
                        if t:
                            t.total_found = (t.total_found or 0) + 1
                            t.progress = min(99, (t.total_found or 0) % 100)
                            t.status = f"Pincode {pin}: synced {t.total_found} products"
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    logger.warning(f"MySQL product callback failed: {e}")

            sqlite_db.on_category_saved = on_category_saved_callback
            sqlite_db.on_product_saved = on_product_saved_callback

            sqlite_db.connect()

            try:
                async def _run():
                    async with ZeptoScraper(sqlite_db, pincode=pin) as scraper:
                        await scraper.run(max_categories=limit, categories_to_scrape=categories_list)

                import asyncio

                asyncio.run(_run())
            finally:
                sqlite_db.close()

        if task_id:
            task = ScraperTask.query.get(task_id)
            if task:
                task.status = "COMPLETED"
                task.progress = 100
                db.session.commit()
                logger.info(f"ScraperTask {task_id} marked COMPLETED")


if __name__ == "__main__":
    # Standalone subprocess args
    parser = argparse.ArgumentParser(description="Zepto Scraper Standalone Runner")
    parser.add_argument("--pincodes", type=str, default="all")
    parser.add_argument("--max_categories", type=int, default=None)
    parser.add_argument("--task_id", type=int, default=None)
    parser.add_argument("--categories", type=str, default=None)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s : %(message)s")

    run_zepto_scrape(
        pincodes=args.pincodes,
        max_categories=args.max_categories,
        task_id=args.task_id,
        categories=args.categories,
    )

