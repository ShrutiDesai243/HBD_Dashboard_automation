import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite intermediate buffer for Zepto.

    Design mirrors the DMart engine DatabaseManager:
      - WAL-enabled SQLite
      - dynamic category resolution + upsert
      - product UPSERT with:
          1) primary dedupe by sku_id
          2) secondary dedupe by (product_name, pack_size) overriding sku_id

    The scraper preloads only from fresh JSONL caches; this manager does not
    seed from old CSV/DB on startup.
    """

    def __init__(self, db_path: str, schema_path: Optional[str] = None):
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path) if schema_path else None
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

        self.on_category_saved = None
        self.on_product_saved = None

        self._category_cache: Dict[tuple, int] = {}

    def connect(self):
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
            self.cursor = self.conn.cursor()

            # Performance
            self.cursor.execute("PRAGMA journal_mode=WAL")
            self.cursor.execute("PRAGMA synchronous=NORMAL")
            self.cursor.execute("PRAGMA cache_size=-64000")
            self.cursor.execute("PRAGMA foreign_keys=ON")
            self.cursor.execute("PRAGMA temp_store=MEMORY")

            if self.schema_path and self.schema_path.exists():
                schema_sql = self.schema_path.read_text(encoding="utf-8")
                self.cursor.executescript(schema_sql)
                self.conn.commit()

            # Ensure Zepto tables always exist (production-grade safety).
            # This prevents runtime failures like: "no such table: zepto_categories".
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS zepto_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_name TEXT NOT NULL,
                    parent_id INTEGER DEFAULT NULL,
                    category_level INTEGER DEFAULT NULL,
                    category_path TEXT DEFAULT NULL
                )
                """
            )
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS zepto_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku_id TEXT NOT NULL UNIQUE,
                    product_name TEXT NOT NULL,
                    quantity TEXT DEFAULT NULL,
                    rating TEXT DEFAULT NULL,
                    review TEXT DEFAULT NULL,
                    mrp DECIMAL(12,2) DEFAULT NULL,
                    selling_price DECIMAL(12,2) DEFAULT NULL,
                    main_category TEXT DEFAULT NULL,
                    subcategory TEXT DEFAULT NULL,
                    product_url TEXT DEFAULT NULL,
                    image_url TEXT DEFAULT NULL,
                    scraped_at TEXT DEFAULT NULL,
                    product_description TEXT DEFAULT NULL,
                    availability INTEGER DEFAULT 1,
                    category_id INTEGER DEFAULT NULL,
                    pack_size TEXT DEFAULT NULL
                )
                """
            )
            self.conn.commit()


            logger.info(f"SQLite connected: {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"SQLite connect failed: {e}")
            raise

    def close(self):
        try:
            if self.conn:
                self.conn.commit()
                self.conn.close()
        except sqlite3.Error as e:
            logger.warning(f"SQLite close error: {e}")
        finally:
            self.conn = None
            self.cursor = None

    # ── Category ───────────────────────────────────────────────

    def upsert_category(
        self,
        category_name: str,
        parent_id: Optional[int],
        category_level: Optional[int],
        category_path: Optional[str],
    ) -> int:
        if not category_name:
            category_name = "Uncategorized"

        cache_key = (category_name.strip().lower(), parent_id)
        if cache_key in self._category_cache:
            return self._category_cache[cache_key]

        try:
            if parent_id is None:
                self.cursor.execute(
                    """SELECT category_id FROM zepto_categories
                       WHERE category_name = ? AND parent_id IS NULL""",
                    (category_name,),
                )
            else:
                self.cursor.execute(
                    """SELECT category_id FROM zepto_categories
                       WHERE category_name = ? AND parent_id = ?""",
                    (category_name, parent_id),
                )
            row = self.cursor.fetchone()

            if row:
                category_id = row[0]
                self.cursor.execute(
                    """UPDATE zepto_categories SET
                           category_level = COALESCE(?, category_level),
                           category_path = COALESCE(?, category_path)
                       WHERE category_id = ?""",
                    (category_level, category_path, category_id),
                )
                self.conn.commit()
            else:
                self.cursor.execute(
                    """INSERT INTO zepto_categories
                       (category_name, parent_id, category_level, category_path)
                       VALUES (?, ?, ?, ?)""",
                    (category_name, parent_id, category_level, category_path),
                )
                category_id = self.cursor.lastrowid
                self.conn.commit()
                logger.info(
                    f"[SQLite] New category: {category_name} (id={category_id}, level={category_level})"
                )

            self._category_cache[cache_key] = category_id

            if self.on_category_saved:
                try:
                    self.on_category_saved(
                        {
                            "category_id": category_id,
                            "category_name": category_name,
                            "parent_id": parent_id,
                            "category_level": category_level,
                            "category_path": category_path,
                        }
                    )
                except Exception as cb_err:
                    logger.error(f"on_category_saved callback failed: {cb_err}")

            return category_id

        except sqlite3.Error as e:
            logger.error(f"SQLite category upsert failed: {e}")
            raise

    def resolve_category_path(self, category_path: str) -> int:
        """Resolve a path like 'Main > Sub' (or longer) into zepto_categories rows."""
        parts = [p.strip() for p in (category_path or "").split(">") if p.strip()]
        if not parts:
            return self.upsert_category("Uncategorized", None, 1, "Uncategorized")

        parent_id = None
        category_id = None
        for idx, part in enumerate(parts):
            level = idx + 1
            current_path = " > ".join(parts[: level])
            category_id = self.upsert_category(part, parent_id, level, current_path)
            parent_id = category_id
        return int(category_id)

    # ── Products ───────────────────────────────────────────────

    def upsert_product(self, product: dict, category_id: Optional[int] = None) -> bool:
        sku_id = str(product.get("sku_id", "")).strip() if product.get("sku_id") is not None else ""
        if not sku_id:
            return False

        # Secondary dedupe: name + pack_size
        # If an identical product exists under different sku, override sku_id to match existing.
        p_name = product.get("product_name")
        p_size = product.get("pack_size")

        try:
            if p_name:
                if p_size is not None:
                    self.cursor.execute(
                        """SELECT sku_id FROM zepto_products
                           WHERE product_name = ? AND pack_size = ?""",
                        (p_name, p_size),
                    )
                else:
                    self.cursor.execute(
                        """SELECT sku_id FROM zepto_products
                           WHERE product_name = ? AND pack_size IS NULL""",
                        (p_name,),
                    )

                row = self.cursor.fetchone()
                if row:
                    existing_sku = str(row[0]).strip()
                    if existing_sku and existing_sku != sku_id:
                        sku_id = existing_sku

            # Upsert by sku_id
            self.cursor.execute(
                """SELECT id FROM zepto_products WHERE sku_id = ?""",
                (sku_id,),
            )
            existing = self.cursor.fetchone()

            fields = {
                "product_name": product.get("product_name"),
                "quantity": product.get("quantity"),
                "rating": product.get("rating"),
                "review": product.get("review"),
                "mrp": product.get("mrp"),
                "selling_price": product.get("selling_price"),
                "main_category": product.get("main_category"),
                "subcategory": product.get("subcategory"),
                "product_url": product.get("product_url"),
                "image_url": product.get("image_url"),
                "scraped_at": product.get("scraped_at"),
                "product_description": product.get("product_description"),
                "availability": product.get("availability"),
                "category_id": category_id,
            }

            if existing:
                self.cursor.execute(
                    """UPDATE zepto_products SET
                        product_name = COALESCE(?, product_name),
                        quantity = COALESCE(?, quantity),
                        rating = COALESCE(?, rating),
                        review = COALESCE(?, review),
                        mrp = COALESCE(?, mrp),
                        selling_price = COALESCE(?, selling_price),
                        main_category = COALESCE(?, main_category),
                        subcategory = COALESCE(?, subcategory),
                        product_url = COALESCE(?, product_url),
                        image_url = COALESCE(?, image_url),
                        scraped_at = COALESCE(?, scraped_at),
                        product_description = COALESCE(?, product_description),
                        availability = COALESCE(?, availability),
                        category_id = COALESCE(?, category_id)
                    WHERE sku_id = ?""",
                    (
                        fields["product_name"],
                        fields["quantity"],
                        fields["rating"],
                        fields["review"],
                        fields["mrp"],
                        fields["selling_price"],
                        fields["main_category"],
                        fields["subcategory"],
                        fields["product_url"],
                        fields["image_url"],
                        fields["scraped_at"],
                        fields["product_description"],
                        fields["availability"],
                        fields["category_id"],
                        sku_id,
                    ),
                )
            else:
                self.cursor.execute(
                    """INSERT INTO zepto_products
                       (sku_id, product_name, quantity, rating, review, mrp, selling_price,
                        main_category, subcategory, product_url, image_url, scraped_at,
                        product_description, availability, category_id, pack_size)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sku_id,
                        fields["product_name"],
                        fields["quantity"],
                        fields["rating"],
                        fields["review"],
                        fields["mrp"],
                        fields["selling_price"],
                        fields["main_category"],
                        fields["subcategory"],
                        fields["product_url"],
                        fields["image_url"],
                        fields["scraped_at"],
                        fields["product_description"],
                        fields["availability"],
                        fields["category_id"],
                        product.get("pack_size"),
                    ),
                )

            self.conn.commit()

            if self.on_product_saved:
                try:
                    self.on_product_saved({
                        **product,
                        "sku_id": sku_id,
                        "category_id": category_id,
                    }, category_id=category_id)
                except Exception as cb_err:
                    logger.error(f"on_product_saved callback failed: {cb_err}")

            return True

        except sqlite3.Error as e:
            logger.error(f"SQLite product upsert failed for sku_id={sku_id}: {e}")
            return False

    def get_product_count(self) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM zepto_products")
        return int(self.cursor.fetchone()[0])

    def export_master_csv(self, output_path: Path) -> int:
        import csv

        self.cursor.execute(
            """SELECT
                sku_id, product_name, quantity, rating, review,
                mrp, selling_price, main_category, subcategory,
                product_url, image_url, scraped_at, product_description
             FROM zepto_products"""
        )
        rows = self.cursor.fetchall()
        if not rows:
            return 0

        headers = [
            "sku_id",
            "product_name",
            "quantity",
            "rating",
            "review",
            "mrp",
            "selling_price",
            "main_category",
            "subcategory",
            "product_url",
            "image_url",
            "scraped_at",
            "product_description",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        return len(rows)

