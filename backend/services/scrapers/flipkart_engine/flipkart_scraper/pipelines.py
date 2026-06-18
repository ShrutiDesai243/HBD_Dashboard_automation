"""
pipelines.py — Cleans items, deduplicates, and writes to per-category CSV files.
Output goes to output/<category_slug>.csv and output/all.csv.
"""

import csv
import os
import re
import time
from itemadapter import ItemAdapter
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")  # for upload_to_mysql.py

OUTPUT_FIELDS = [
    "main_category", "subcategory", "leaf_category",
    "product_id", "product_url", "product_name", "brand",
    "price", "mrp", "discount",
    "rating", "reviews",
    "image_url", "spec_bullets",
]


def _safe_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.lower().strip()).strip("_")


def _clean_price(val: str) -> str:
    if not val:
        return ""
    return re.sub(r"[^\d.]", "", val)


def _open_csv(path: str, mode: str):
    for attempt in range(5):
        try:
            return open(path, mode, newline="", encoding="utf-8")
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.2)


# ── Pipeline 1: Clean & normalise fields ──────────────────────────────────────

class CleaningPipeline:
    """Normalize and clean fields. Maps spider item fields correctly."""

    def process_item(self, item, spider=None):
        adapter = ItemAdapter(item)

        # Price fields — strip currency symbols, keep digits and dot only
        adapter["price"]    = _clean_price(adapter.get("price") or "")
        adapter["mrp"]      = _clean_price(adapter.get("mrp") or "")

        # Discount — strip "off" suffix, keep "67%" style
        discount = adapter.get("discount") or ""
        adapter["discount"] = discount.replace("off", "").strip()

        # Text fields — strip whitespace
        adapter["product_name"] = (adapter.get("product_name") or "").strip()
        adapter["brand"]        = (adapter.get("brand") or "").strip()
        adapter["rating"]       = (adapter.get("rating") or "").strip()
        adapter["reviews"]      = (adapter.get("reviews") or "").strip()
        adapter["spec_bullets"] = (adapter.get("spec_bullets") or "").strip()

        return item


# ── Pipeline 2: Deduplicate by product_id ────────────────────────────────────

class DedupPipeline:
    """Drop duplicate products by product_id across runs."""

    def __init__(self):
        self._seen: set = set()
        # Load existing product IDs from all.csv if it exists
        all_csv_path = os.path.join(OUTPUT_DIR, "all.csv")
        if os.path.isfile(all_csv_path):
            try:
                with open(all_csv_path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        pid = row.get("product_id")
                        if pid:
                            self._seen.add(pid)
            except Exception:
                pass

    def process_item(self, item, spider=None):
        pid = ItemAdapter(item).get("product_id", "")
        if pid and pid in self._seen:
            from scrapy.exceptions import DropItem
            raise DropItem(f"Duplicate product_id: {pid}")
        if pid:
            self._seen.add(pid)
        return item


# ── Pipeline 3: Write to CSV ──────────────────────────────────────────────────

class CSVExportPipeline:
    """
    Write each item to:
      output/all.csv                    ← everything in one file
      output/<leaf_category_slug>.csv   ← one file per leaf category
    """

    def __init__(self):
        os.makedirs(OUTPUT_DIR,  exist_ok=True)   # output/
        os.makedirs(OUTPUTS_DIR, exist_ok=True)   # outputs/  (for upload_to_mysql.py)
        self._files: dict   = {}
        self._writers: dict = {}

    def _get_writer(self, key: str) -> csv.DictWriter:
        if key not in self._writers:
            path = os.path.join(OUTPUT_DIR, f"{key}.csv")
            file_exists  = os.path.isfile(path)
            needs_header = not file_exists or self._needs_current_header(path)
            f      = _open_csv(path, "a")
            writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
            if needs_header:
                writer.writeheader()
            self._files[key]   = f
            self._writers[key] = writer
        return self._writers[key]

    def _needs_current_header(self, path: str) -> bool:
        try:
            with _open_csv(path, "r") as f:
                reader = csv.DictReader(f)
                return reader.fieldnames != OUTPUT_FIELDS
        except Exception:
            return True

    def process_item(self, item, spider=None):
        adapter = ItemAdapter(item)

        # Map directly from spider item fields — no more old level1/level2 names
        row = {
            "main_category": adapter.get("main_category", ""),
            "subcategory":   adapter.get("subcategory", ""),
            "leaf_category": adapter.get("leaf_category", ""),
            "product_id":    adapter.get("product_id", ""),
            "product_url":   adapter.get("product_url", ""),
            "product_name":  adapter.get("product_name", ""),
            "brand":         adapter.get("brand", ""),
            "price":         adapter.get("price", ""),
            "mrp":           adapter.get("mrp", ""),
            "discount":      adapter.get("discount", ""),
            "rating":        adapter.get("rating", ""),
            "reviews":       adapter.get("reviews", ""),
            "image_url":     adapter.get("image_url", ""),
            "spec_bullets":  adapter.get("spec_bullets", ""),
        }

        # Write to all.csv  (output/all.csv)
        self._get_writer("all").writerow(row)

        # Write to outputs/all_1.csv  (used by upload_to_mysql.py)
        all1_path = os.path.join(OUTPUTS_DIR, "all_1.csv")
        file_exists   = os.path.isfile(all1_path)
        needs_header  = not file_exists
        if "_all1" not in self._writers:
            f = _open_csv(all1_path, "a")
            w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
            if needs_header:
                w.writeheader()
            self._files["_all1"]   = f
            self._writers["_all1"] = w
        self._writers["_all1"].writerow(row)

        # Write to per-main-category file (output/<category>.csv)
        slug = _safe_filename(adapter.get("main_category") or "unknown")
        self._get_writer(slug).writerow(row)

        return item

    async def close_spider(self, spider):
        """Async close — required for Scrapy 2.12+ with async pipelines."""
        for f in self._files.values():
            try:
                f.close()
            except Exception:
                pass
        if spider is not None:
            spider.logger.info(f"Output written to: {OUTPUT_DIR}")


class MySQLPipeline:
    """
    Directly inserts items into the MySQL database in real-time during scraping.
    Loads credentials from the .env file in the project root.
    """
    def __init__(self):
        load_dotenv()
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = int(os.getenv("DB_PORT", "3306"))
        self.db_user = os.getenv("DB_USER", "root")
        self.db_password = os.getenv("DB_PASSWORD", "your_password")
        self.db_name = os.getenv("DB_NAME", "flipkart_db")
        self.conn = None
        self.cursor = None

    def open_spider(self, spider):
        try:
            self.conn = mysql.connector.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name
            )
            self.cursor = self.conn.cursor()
            spider.logger.info("MySQL Pipeline: Connected successfully to the database.")
        except Error as e:
            self.conn = None
            self.cursor = None
            spider.logger.warning(
                f"MySQL Pipeline: Failed to connect to database ({e}). "
                "The scraper will still run and output to CSV files normally."
            )

    def process_item(self, item, spider):
        # If connection failed, just pass the item along to other pipelines
        if not self.conn or not self.cursor:
            return item

        adapter = ItemAdapter(item)

        # Parse numeric fields to match MySQL schema
        def clean_price(val):
            if not val:
                return None
            try:
                return float(str(val).replace(",", "").strip())
            except Exception:
                return None

        def clean_rating(val):
            if not val:
                return None
            try:
                return float(str(val).strip())
            except Exception:
                return None

        price = clean_price(adapter.get("price"))
        mrp = clean_price(adapter.get("mrp"))
        rating = clean_rating(adapter.get("rating"))

        insert_sql = """
            INSERT INTO flipkart_products_new
                (main_category, subcategory, leaf_category, product_id,
                 product_url, product_name, brand, price, mrp, discount,
                 rating, reviews, image_url, spec_bullets)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                price       = VALUES(price),
                mrp         = VALUES(mrp),
                discount    = VALUES(discount),
                rating      = VALUES(rating),
                reviews     = VALUES(reviews)
        """

        try:
            self.cursor.execute(insert_sql, (
                adapter.get("main_category"),
                adapter.get("subcategory"),
                adapter.get("leaf_category"),
                adapter.get("product_id"),
                adapter.get("product_url"),
                adapter.get("product_name"),
                adapter.get("brand"),
                price,
                mrp,
                adapter.get("discount"),
                rating,
                adapter.get("reviews"),
                adapter.get("image_url"),
                adapter.get("spec_bullets")
            ))
            self.conn.commit()
        except Error as e:
            spider.logger.warning(f"MySQL Pipeline error inserting row: {e}")

        return item

    def close_spider(self, spider):
        if self.cursor:
            try:
                self.cursor.close()
            except Exception:
                pass
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        if spider is not None:
            spider.logger.info("MySQL Pipeline: Connection closed.")
