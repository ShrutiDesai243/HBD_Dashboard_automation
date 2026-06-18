"""
Blinkit Database Sync Layer — Zero-duplicate batch upsert to MySQL.

Strategy:
  blinkit table:       product_id is PRIMARY KEY → INSERT ... ON DUPLICATE KEY UPDATE
  blinkit_mapping:     category_id is PRIMARY KEY → no duplicates by ID
                       Duplicate names prevented by app-level name check before insert

All operations are transactional with batch processing (500 records/commit).
live_to_db map is RETURNED from sync_categories() so caller can translate
live Blinkit subcategory IDs → DB IDs for product insertion.
"""
import logging
import re
import pymysql
import pymysql.cursors
from typing import List, Dict, Tuple, Optional, Set

from services.scrapers.blinkit_engine.config import PRODUCT_BATCH_SIZE, CATEGORY_BATCH_SIZE

logger = logging.getLogger(__name__)


class BlinkitDatabaseSync:
    """
    Handles all MySQL operations for the Blinkit scraper.
    Uses raw pymysql for high-performance batch inserts.
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self._conn: Optional[pymysql.Connection] = None

    def connect(self):
        self._conn = pymysql.connect(
            host=self.db_config["host"],
            user=self.db_config["user"],
            password=self.db_config["password"],
            database=self.db_config["db"],
            port=int(self.db_config.get("port", 3306)),
            charset="utf8mb4",
            autocommit=False,
            connect_timeout=15,
            read_timeout=30,
            write_timeout=30,
            cursorclass=pymysql.cursors.DictCursor,
        )
        logger.info("[DBSync] Connected to MySQL")

    def disconnect(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _ensure_connected(self):
        try:
            if self._conn is None:
                self.connect()
            else:
                self._conn.ping(reconnect=True)
        except Exception:
            self.connect()

    # ── Category Sync ─────────────────────────────────────────────────────────

    def get_existing_category_maps(self):
        """Load all existing category mappings from database.
        Returns:
            Tuple of:
              - name_to_id: dict mapping normalized lower category_name -> category_id
              - existing_ids: set of all existing category_ids
        """
        self._ensure_connected()
        with self._conn.cursor() as cur:
            cur.execute("SELECT category_id, category_name FROM blinkit_mapping")
            rows = cur.fetchall()
            name_to_id = {}
            existing_ids = set()
            for r in rows:
                if r["category_name"] and r["category_id"]:
                    norm_name = re.sub(r"\s+", " ", r["category_name"]).strip().lower()
                    name_to_id[norm_name] = int(r["category_id"])
                    existing_ids.add(int(r["category_id"]))
            return name_to_id, existing_ids

    def sync_categories(self, categories: List[Dict]) -> Tuple[Dict[str, int], Dict[int, int]]:
        """
        Upsert categories into blinkit_mapping.
        Resolves category duplicates by name (case-insensitive).

        Returns:
            Tuple of:
              - stats dict: {"inserted": int, "skipped": int, "failed": int}
              - live_to_db dict: {live_category_id (int) -> db_category_id (int)}
        """
        if not categories:
            return {"inserted": 0, "skipped": 0, "failed": 0}, {}

        self._ensure_connected()
        stats = {"inserted": 0, "skipped": 0, "failed": 0}

        # 1. Load existing categories
        name_to_id, existing_ids = self.get_existing_category_maps()
        logger.info(f"[DBSync] Loaded {len(name_to_id)} unique category names from DB.")

        CATEGORY_NAME_REMAP = {
            "beauty & personal care": "Personal Care",
            "cleaning & household": "Cleaning Essentials",
            "pantry staples": "Atta, Rice & Dal",
            "dairy & breakfast": "Dairy, Bread & Eggs",
            "ice creams & sweets": "Sweet Tooth",
            "paan & hookah": "Paan Corner",
            "digital needs": "Digital Goods",
            "meat & seafood": "Chicken, Meat & Fish",
            "arts & crafts": "Toys & Games",
            "accessories other supplies": "Pet Care",
            "tomato chilli ketchup": "Sauces & Spreads",
            "chips crisps": "Munchies",
            "oil ghee": "Masala, Oil & More",
            "fashion accessories": "Personal Care",
            "arts built environment": "Toys & Games",
            "bath & body": "Personal Care",
            "biscuit gift pack": "Bakery & Biscuits",
            "body skin care": "Personal Care",
            "diapers more": "Baby Care",
            "fabric conditioner additives": "Cleaning Essentials",
            "face body moisturizers": "Personal Care",
            "fashion accesssories": "Personal Care",
            "health & wellness": "Tea, Coffee & Health Drinks",
            "spiritual religious needs": "Home & Office",
        }

        # 2. Build live_to_db mapping
        live_to_db: Dict[int, int] = {}
        sorted_categories = sorted(categories, key=lambda x: int(x.get("category_level") or 1))
        next_new_id = max(existing_ids) + 1 if existing_ids else 1000
        to_insert = []

        for c in sorted_categories:
            live_id = int(c["category_id"])
            raw_name = c.get("category_name", "").strip()
            name_lower = re.sub(r"\s+", " ", raw_name).strip().lower()

            if name_lower in CATEGORY_NAME_REMAP:
                mapped_name = CATEGORY_NAME_REMAP[name_lower]
                c["category_name"] = mapped_name
                name_lower = re.sub(r"\s+", " ", mapped_name).strip().lower()

            final_name = c["category_name"]

            if name_lower in name_to_id:
                db_id = name_to_id[name_lower]
                live_to_db[live_id] = db_id
                c["_db_category_id"] = db_id
                stats["skipped"] += 1
            else:
                if live_id not in existing_ids:
                    db_id = live_id
                else:
                    db_id = next_new_id
                    next_new_id += 1

                live_to_db[live_id] = db_id
                name_to_id[name_lower] = db_id
                existing_ids.add(db_id)
                c["_db_category_id"] = db_id
                to_insert.append(c)

        # 3. Second pass: resolve parent_id using live_to_db map
        db_id_to_name = {}
        for r_cat in sorted_categories:
            db_id = r_cat.get("_db_category_id")
            if db_id:
                db_id_to_name[db_id] = r_cat.get("category_name", "")

        for c in sorted_categories:
            live_parent_id = int(c.get("parent_id") or 0)
            if live_parent_id != 0:
                db_parent_id = live_to_db.get(live_parent_id, live_parent_id)
                c["parent_id"] = db_parent_id
            else:
                c["parent_id"] = 0

            if int(c.get("category_level") or 1) == 2:
                db_parent_id = c["parent_id"]
                parent_name = db_id_to_name.get(db_parent_id, "")
                if not parent_name:
                    try:
                        with self._conn.cursor() as cur:
                            cur.execute(
                                "SELECT category_name FROM blinkit_mapping WHERE category_id = %s",
                                (db_parent_id,)
                            )
                            row = cur.fetchone()
                            if row:
                                parent_name = row["category_name"]
                                db_id_to_name[db_parent_id] = parent_name
                    except Exception:
                        pass
                c["full_category_path"] = f"{parent_name} > {c['category_name']}" if parent_name else c["category_name"]
            else:
                c["full_category_path"] = c["category_name"]

        # 4. Execute SQL inserts for new categories
        if not to_insert:
            logger.info("[DBSync] No new category names to insert.")
            return stats, live_to_db

        INSERT_SQL = """
            INSERT IGNORE INTO blinkit_mapping
                (category_id, category_name, slug, parent_id, category_level, full_category_path)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        for i in range(0, len(to_insert), CATEGORY_BATCH_SIZE):
            batch = to_insert[i:i + CATEGORY_BATCH_SIZE]
            try:
                with self._conn.cursor() as cur:
                    rows = [
                        (
                            int(c["_db_category_id"]),
                            str(c.get("category_name", ""))[:50],
                            str(c.get("slug", ""))[:50],
                            int(c.get("parent_id") or 0),
                            int(c.get("category_level") or 1),
                            str(c.get("full_category_path", ""))[:58],
                        )
                        for c in batch
                    ]
                    cur.executemany(INSERT_SQL, rows)
                self._conn.commit()
                stats["inserted"] += len(batch)
                logger.info(f"[DBSync] Categories: committed batch of {len(batch)} (total inserted: {stats['inserted']})")
            except Exception as e:
                self._conn.rollback()
                stats["failed"] += len(batch)
                logger.error(f"[DBSync] Category batch insert failed: {e}", exc_info=True)

        logger.info(f"[DBSync] sync_categories complete: {stats} | live_to_db entries: {len(live_to_db)}")
        return stats, live_to_db

    def get_subcategory_id_by_name(self, category_name: str, sub_category_name: str) -> Optional[int]:
        """Look up a subcategory DB id by name matching."""
        self._ensure_connected()
        sub_norm = re.sub(r"\s+", " ", sub_category_name).strip().lower() if sub_category_name else ""
        cat_norm = re.sub(r"\s+", " ", category_name).strip().lower() if category_name else ""

        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT category_id, parent_id FROM blinkit_mapping WHERE LOWER(TRIM(category_name)) = %s AND category_level = 2",
                    (sub_norm,)
                )
                matches = cur.fetchall()

                if len(matches) == 1:
                    return int(matches[0]["category_id"])

                if len(matches) > 1:
                    for m in matches:
                        cur.execute(
                            "SELECT category_name FROM blinkit_mapping WHERE category_id = %s",
                            (m["parent_id"],)
                        )
                        pr = cur.fetchone()
                        if pr and re.sub(r"\s+", " ", pr["category_name"]).strip().lower() == cat_norm:
                            return int(m["category_id"])
                    return int(matches[0]["category_id"])

                cur.execute(
                    "SELECT category_id FROM blinkit_mapping WHERE LOWER(TRIM(category_name)) = %s AND category_level = 1",
                    (cat_norm,)
                )
                parent_row = cur.fetchone()
                if parent_row:
                    return int(parent_row["category_id"])

                return None
        except Exception as e:
            logger.warning(f"[DBSync] get_subcategory_id_by_name failed: {e}")
            return None

    # ── Product Sync ──────────────────────────────────────────────────────────

    def get_existing_product_ids(self) -> Set[int]:
        """Load all product_ids already in blinkit table."""
        self._ensure_connected()
        with self._conn.cursor() as cur:
            cur.execute("SELECT product_id FROM blinkit")
            rows = cur.fetchall()
            return {int(r["product_id"]) for r in rows}

    def sync_products(self, products: List[Dict]) -> Dict[str, int]:
        """
        Batch upsert products into blinkit table.
        Uses ON DUPLICATE KEY UPDATE for existing products (updates price/availability).

        Returns: {inserted, updated, skipped, failed}
        IMPORTANT: accurately tracks inserts vs updates using a pre-check.
        """
        if not products:
            return {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}

        self._ensure_connected()
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}

        UPSERT_SQL = """
            INSERT INTO blinkit
                (product_id, product_name, brand, category, sub_category, category_id,
                 price, mrp, discount, quantity, availability, image_url, product_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                product_name = IF(VALUES(product_name) != '', VALUES(product_name), product_name),
                brand        = IF(VALUES(brand) IS NOT NULL, VALUES(brand), brand),
                category     = IF(VALUES(category) IS NOT NULL, VALUES(category), category),
                sub_category = IF(VALUES(sub_category) IS NOT NULL, VALUES(sub_category), sub_category),
                category_id  = IF(VALUES(category_id) IS NOT NULL, VALUES(category_id), category_id),
                price        = VALUES(price),
                mrp          = VALUES(mrp),
                discount     = VALUES(discount),
                quantity     = IF(VALUES(quantity) IS NOT NULL, VALUES(quantity), quantity),
                availability = VALUES(availability),
                image_url    = IF(VALUES(image_url) IS NOT NULL AND VALUES(image_url) != '', VALUES(image_url), image_url),
                product_url  = IF(VALUES(product_url) IS NOT NULL, VALUES(product_url), product_url)
        """

        valid = [p for p in products if p.get("product_id") and p.get("product_name")]
        stats["skipped"] += len(products) - len(valid)

        for i in range(0, len(valid), PRODUCT_BATCH_SIZE):
            batch = valid[i:i + PRODUCT_BATCH_SIZE]
            try:
                # Pre-check: which product_ids already exist
                batch_ids = [int(p["product_id"]) for p in batch]
                with self._conn.cursor() as cur:
                    ph = ",".join(["%s"] * len(batch_ids))
                    cur.execute(f"SELECT product_id FROM blinkit WHERE product_id IN ({ph})", batch_ids)
                    existing = {r["product_id"] for r in cur.fetchall()}

                new_count = sum(1 for p in batch if int(p["product_id"]) not in existing)
                upd_count = len(batch) - new_count

                with self._conn.cursor() as cur:
                    rows = [
                        (
                            int(p["product_id"]),
                            str(p.get("product_name", ""))[:500],
                            str(p["brand"])[:255] if p.get("brand") else None,
                            str(p["category"])[:255] if p.get("category") else None,
                            str(p["sub_category"])[:255] if p.get("sub_category") else None,
                            int(p["category_id"]) if p.get("category_id") is not None else None,
                            float(p["price"]) if p.get("price") is not None else None,
                            float(p["mrp"]) if p.get("mrp") is not None else None,
                            float(p["discount"]) if p.get("discount") is not None else None,
                            str(p["quantity"])[:100] if p.get("quantity") else None,
                            1 if p.get("availability", True) else 0,
                            str(p["image_url"])[:2048] if p.get("image_url") else None,
                            str(p["product_url"])[:2048] if p.get("product_url") else None,
                        )
                        for p in batch
                    ]
                    cur.executemany(UPSERT_SQL, rows)
                self._conn.commit()

                stats["inserted"] += new_count
                stats["updated"] += upd_count
                logger.info(f"[DBSync] Products: inserted={new_count} updated={upd_count} (batch={len(batch)})")

            except Exception as e:
                self._conn.rollback()
                stats["failed"] += len(batch)
                logger.error(f"[DBSync] Product batch upsert failed: {e}", exc_info=True)
                try:
                    self.connect()
                except Exception:
                    pass

        return stats

    # ── Stats Query ───────────────────────────────────────────────────────────

    def get_current_counts(self) -> Dict[str, int]:
        """Get current row counts from both blinkit tables."""
        self._ensure_connected()
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM blinkit")
                product_count = cur.fetchone()["cnt"]

                cur.execute("SELECT COUNT(*) as cnt FROM blinkit_mapping")
                category_count = cur.fetchone()["cnt"]

                cur.execute("SELECT COUNT(DISTINCT category) as cnt FROM blinkit WHERE category IS NOT NULL")
                distinct_cats = cur.fetchone()["cnt"]

                cur.execute("SELECT COUNT(DISTINCT brand) as cnt FROM blinkit WHERE brand IS NOT NULL AND brand != ''")
                distinct_brands = cur.fetchone()["cnt"]

                cur.execute("SELECT COUNT(*) as cnt FROM blinkit WHERE category_id IS NULL")
                null_cat_ids = cur.fetchone()["cnt"]

                cur.execute("""
                    SELECT COUNT(*) as cnt FROM (
                        SELECT category_id, COUNT(*) as c
                        FROM blinkit_mapping
                        WHERE category_id IS NOT NULL
                        GROUP BY category_id HAVING c > 1
                    ) x
                """)
                mapping_dupes = cur.fetchone()["cnt"]

            return {
                "total_products":   product_count,
                "total_categories": category_count,
                "distinct_categories": distinct_cats,
                "distinct_brands":  distinct_brands,
                "products_null_category_id": null_cat_ids,
                "mapping_duplicates": mapping_dupes,
            }
        except Exception as e:
            logger.error(f"[DBSync] Count query failed: {e}")
            return {}

    def get_categories_for_filter(self) -> List[Dict]:
        """Returns all L1 categories for UI category filter dropdown."""
        self._ensure_connected()
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT m.category_id, m.category_name,
                           COUNT(b.product_id) as product_count
                    FROM blinkit_mapping m
                    LEFT JOIN blinkit b ON b.category_id = m.category_id
                       OR (b.category = m.category_name AND m.parent_id = 0)
                    WHERE m.parent_id = 0
                    GROUP BY m.category_id, m.category_name
                    ORDER BY m.category_name
                """)
                return [
                    {"id": r["category_id"], "name": r["category_name"], "product_count": r["product_count"]}
                    for r in cur.fetchall()
                ]
        except Exception as e:
            logger.error(f"[DBSync] get_categories_for_filter failed: {e}")
            return []

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
