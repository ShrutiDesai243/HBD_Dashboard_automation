import os
import sys
import argparse
import logging
import time
from pathlib import Path
from typing import Optional

# ── Ensure backend folder is in sys.path when running as CLI subprocess ──
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# ── Engine is a sibling package ──
scrapy_dir = os.path.join(os.path.dirname(__file__), "flipkart_engine")
if scrapy_dir not in sys.path:
    sys.path.insert(0, scrapy_dir)

# ── Set Scrapy settings module ──
os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "flipkart_scraper.settings")

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy import signals

logger = logging.getLogger(__name__)

def _bootstrap_flask_app():
    """Import app and extensions lazily so this adapter can run safely as a CLI subprocess."""
    os.environ.setdefault("SKIP_DB_CREATE_ALL", "1")

    # Ensure output dir exists to prevent import crashes
    repo_root = os.path.abspath(os.path.join(backend_root, ".."))
    output_dir = os.path.join(repo_root, "output")
    os.makedirs(output_dir, exist_ok=True)

    gdrive_log = os.path.join(output_dir, "gdrive_etl.log")
    if not os.path.exists(gdrive_log):
        with open(gdrive_log, "w", encoding="utf-8") as f:
            f.write("")

    from app import app as flask_app
    return flask_app


# ── Custom Item Pipeline: writes to Flask DB model (flipkart_products_new) ──
class FlipkartFlaskDatabasePipeline:
    """
    Real-time pipeline: receives cleaned items from the Scrapy spider and
    inserts/updates them in the flipkart_products_new table via the Flask model.
    Tracks progress in ScraperTask.
    """
    def __init__(self):
        self.flask_app = None
        self.db = None
        self.FlipkartModel = None
        self.ScraperTaskModel = None
        self.task_id = None
        self.total_found = 0
        self.items_scraped = 0

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.task_id = crawler.settings.get('FLASK_TASK_ID')
        return pipeline

    def open_spider(self, spider):
        self.flask_app = _bootstrap_flask_app()
        from extensions import db
        from model.product_model.additional_products import Flipkart
        from model.scraper_task import ScraperTask

        self.db = db
        self.FlipkartModel = Flipkart
        self.ScraperTaskModel = ScraperTask
        self.items_scraped = 0

        with self.flask_app.app_context():
            if self.task_id:
                try:
                    task = self.db.session.get(self.ScraperTaskModel, self.task_id)
                    if task:
                        self.total_found = task.total_found or 0
                except Exception as e:
                    spider.logger.warning(f"Pipeline failed to load task on open: {e}")

    def process_item(self, item, spider):
        from itemadapter import ItemAdapter
        adapter = ItemAdapter(item)

        # ── Map new scraper fields → flipkart_products_new columns ──
        product_id   = adapter.get("product_id")
        product_name = adapter.get("product_name")
        image_url    = adapter.get("image_url")
        product_url  = adapter.get("product_url")
        rating_raw   = adapter.get("rating")
        reviews      = adapter.get("reviews")
        brand        = adapter.get("brand")
        spec_bullets = adapter.get("spec_bullets")
        main_category = adapter.get("main_category") or ""
        subcategory   = adapter.get("subcategory") or ""
        leaf_category = adapter.get("leaf_category") or adapter.get("main_category") or "Uncategorized"
        discount      = adapter.get("discount")

        # Clean numeric fields
        def _to_decimal(val):
            if not val:
                return None
            try:
                return float(str(val).replace(",", "").strip())
            except Exception:
                return None

        price     = _to_decimal(adapter.get("price"))
        mrp       = _to_decimal(adapter.get("mrp"))
        rating    = _to_decimal(rating_raw)

        if not product_id or not product_name:
            return item

        with self.flask_app.app_context():
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    existing = self.db.session.query(self.FlipkartModel).filter_by(
                        product_id=product_id
                    ).first()

                    if existing:
                        # Update pricing and ratings — never overwrite identity
                        existing.product_name  = product_name
                        existing.image_url     = image_url
                        existing.product_url   = product_url
                        existing.rating        = rating
                        existing.reviews       = reviews
                        existing.price         = price
                        existing.mrp           = mrp
                        existing.discount      = discount
                        existing.leaf_category = leaf_category
                        existing.brand         = brand
                        existing.spec_bullets  = spec_bullets
                    else:
                        new_prod = self.FlipkartModel(
                            product_id    = product_id,
                            product_name  = product_name,
                            image_url     = image_url,
                            product_url   = product_url,
                            rating        = rating,
                            reviews       = reviews,
                            price         = price,
                            mrp           = mrp,
                            discount      = discount,
                            brand         = brand,
                            spec_bullets  = spec_bullets,
                            main_category = main_category,
                            subcategory   = subcategory,
                            leaf_category = leaf_category,
                        )
                        self.db.session.add(new_prod)

                    self.items_scraped += 1
                    self.total_found += 1

                    # Update task progress dynamically
                    if self.task_id:
                        task = self.db.session.get(self.ScraperTaskModel, self.task_id)
                        if task:
                            task.total_found = self.total_found
                            task.progress = min(99, self.total_found % 100)
                            task.status = f"Scraped {self.total_found} products"

                    self.db.session.commit()
                    break  # success
                except Exception as e:
                    self.db.session.rollback()
                    self.db.session.remove()
                    if attempt == max_retries:
                        spider.logger.error(
                            f"Pipeline MySQL insert failed for {product_id} after {max_retries} attempts: {e}"
                        )
                        break
                    time.sleep(1)

        return item


# ── Custom Scrapy signal monitor: cancellation + progress ──
class FlipkartScrapyMonitor:
    def __init__(self, task_id, flask_app, db, ScraperTaskModel):
        self.task_id = task_id
        self.flask_app = flask_app
        self.db = db
        self.ScraperTaskModel = ScraperTaskModel
        self.responses_count = 0

    def response_received(self, response, request, spider):
        self.responses_count += 1
        if self.task_id:
            with self.flask_app.app_context():
                try:
                    task = self.db.session.get(self.ScraperTaskModel, self.task_id)
                    if task:
                        # Allow dashboard to cancel the spider
                        if task.should_stop:
                            spider.logger.info("STOP signal detected in DB. Closing spider...")
                            spider.crawler.engine.close_spider(spider, reason="cancelled_by_user")
                            return

                        # Progress update for non-product spiders
                        if spider.name not in ("flipkart_products", "flipkart_search"):
                            task.progress = min(99, self.responses_count)
                            task.status = f"Crawling: visited {self.responses_count} pages..."
                            self.db.session.commit()
                except Exception as err:
                    spider.logger.warning(f"Error checking cancel/progress: {err}")
                    self.db.session.rollback()


# ── Main entry point: called from flipkart_routes.py via subprocess ──
def run_flipkart_scrape(
    search_term: str,
    mode: str = "products",
    categories: Optional[str] = None,
    max_pages: Optional[int] = None,
    task_id: Optional[int] = None
):
    app = _bootstrap_flask_app()
    from extensions import db
    from model.scraper_task import ScraperTask

    logger.info(
        f"=== Flipkart Scraper START | mode={mode} | "
        f"search_term={search_term} | categories={categories} | max_pages={max_pages} ==="
    )

    with app.app_context():
        if task_id:
            try:
                task = db.session.get(ScraperTask, task_id)
                if task:
                    task.status = "RUNNING"
                    task.progress = 0
                    db.session.commit()
            except Exception as e:
                logger.warning(f"Failed to set ScraperTask {task_id} status to RUNNING: {e}")

    # ── Spider selection logic ──────────────────────────────────────────────────
    spider_args = {}

    if mode == "discover_categories":
        from flipkart_scraper.spiders.discover_categories import DiscoverCategoriesSpider
        spider_cls = DiscoverCategoriesSpider

    elif mode == "auto_discover":
        from flipkart_scraper.spiders.auto_discover import AutoDiscoverSpider
        spider_cls = AutoDiscoverSpider
        spider_args["dry_run"] = "False"

    else:
        # ── KEY ROUTING: search_term != "all" → use FlipkartSearchSpider ──
        # This is the on-demand dashboard search flow.
        # search_term == "all" → use FlipkartProductsSpider (bulk category crawl)
        is_specific_search = (
            search_term
            and search_term.strip().lower() not in ("", "all")
        )

        if is_specific_search:
            # On-demand search: user typed a category or product name in dashboard
            from flipkart_scraper.spiders.flipkart_search import FlipkartSearchSpider
            spider_cls = FlipkartSearchSpider
            spider_args["query"] = search_term.strip()
            spider_args["pages"] = str(max_pages or 2)
            logger.info(f"[Routing] On-demand search → FlipkartSearchSpider | query='{search_term}'")

        else:
            # Bulk category crawl from categories.csv
            from flipkart_scraper.spiders.flipkart_products import FlipkartProductsSpider
            spider_cls = FlipkartProductsSpider
            spider_args["pages"] = str(max_pages or 1)
            spider_args["debug"] = "0"
            if categories:
                spider_args["category"] = categories
            logger.info(f"[Routing] Bulk crawl → FlipkartProductsSpider | category_filter='{categories}'")

    # ── Build Scrapy settings ───────────────────────────────────────────────────
    settings = get_project_settings()
    settings.set("FLASK_TASK_ID", task_id)

    # Inject the dashboard pipeline (replaces the standalone MySQLPipeline)
    pipelines = {
        "flipkart_scraper.pipelines.CleaningPipeline": 100,
        "flipkart_scraper.pipelines.DedupPipeline": 200,
        "services.scrapers.flipkart_service.FlipkartFlaskDatabasePipeline": 400
    }
    settings.set("ITEM_PIPELINES", pipelines)

    process = CrawlerProcess(settings)
    crawler = process.create_crawler(spider_cls)

    # Attach signal monitor for cancellation support
    monitor = FlipkartScrapyMonitor(task_id, app, db, ScraperTask)
    crawler.signals.connect(monitor.response_received, signal=signals.response_received)

    try:
        process.crawl(crawler, **spider_args)
        process.start()

        # Mark task complete
        if task_id:
            with app.app_context():
                task = db.session.get(ScraperTask, task_id)
                if task:
                    if task.should_stop:
                        task.status = "CANCELLED"
                    else:
                        task.status = "COMPLETED"
                        task.progress = 100
                    db.session.commit()
                    logger.info(f"ScraperTask {task_id} marked as {task.status}")

    except Exception as e:
        logger.error(f"Execution failed for task {task_id}: {e}", exc_info=True)
        if task_id:
            with app.app_context():
                try:
                    task = db.session.get(ScraperTask, task_id)
                    if task:
                        task.status = "FAILED"
                        task.error_message = str(e)
                        db.session.commit()
                except Exception as db_err:
                    logger.error(f"Failed to record execution error in DB: {db_err}")
        raise e


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Flipkart Scraper Standalone Process Runner")
    parser.add_argument("--search_term", type=str, default="all")
    parser.add_argument("--mode", type=str, default="products")
    parser.add_argument("--categories", type=str, default=None)
    parser.add_argument("--max_pages", type=int, default=None)
    parser.add_argument("--task_id", type=int, default=None)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s : %(message)s"
    )

    run_flipkart_scrape(
        search_term=args.search_term,
        mode=args.mode,
        categories=args.categories,
        max_pages=args.max_pages,
        task_id=args.task_id
    )
