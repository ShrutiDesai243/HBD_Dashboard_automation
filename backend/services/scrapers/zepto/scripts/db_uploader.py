import os
from typing import List, Dict, Any

from dotenv import load_dotenv
import mysql.connector



TABLE_NAME = "zepto"


def _load_env():
    load_dotenv()


def get_connection():
    _load_env()

    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")

    missing = [
        k
        for k, v in {
            "DB_HOST": host,
            "DB_USER": user,
            "DB_PASSWORD": password,
            "DB_NAME": database,
        }.items()
        if not v
    ]

    if missing:
        raise RuntimeError(
            "Missing required env vars: " + ", ".join(missing) + ". Create a .env file."
        )

    return mysql.connector.connect(

        host=host,
        user=user,
        password=password,
        database=database,
    )


def ensure_unique_sku_id(conn):
    """Ensure UNIQUE(sku_id) exists so ON DUPLICATE KEY works for sku_id."""
    cursor = conn.cursor()

    # Check if a UNIQUE index exists on sku_id
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.statistics
        WHERE table_schema = %s
          AND table_name = %s
          AND index_name = 'sku_id'
        """,
        (conn.database, TABLE_NAME),
    )

    exists = cursor.fetchone()[0] > 0

    if not exists:
        # Create a unique index (index name: sku_id)
        cursor.execute(
            f"ALTER TABLE `{TABLE_NAME}` ADD UNIQUE INDEX `sku_id` (`sku_id`)"
        )
        conn.commit()

    cursor.close()


def update_category_mapping(conn, products: List[Dict[str, Any]]):
    """Automatically inserts missing main_category and subcategory entries into zepto_db_mapping.
    
    No internal commits are made to preserve transaction safety.
    """
    if not products:
        return

    cursor = conn.cursor()

    # 1. Extract unique (main_category, subcategory) pairs from the scraped products
    categories = set()
    for p in products:
        main = p.get("main_category")
        sub = p.get("subcategory")
        if main and sub:
            categories.add((main.strip(), sub.strip()))

    if not categories:
        cursor.close()
        return

    # 2. Insert missing Level 1 categories (main_category)
    for main, _ in categories:
        cursor.execute(
            "SELECT category_id FROM `zepto_db_mapping` WHERE category = %s AND category_level = 1",
            (main,)
        )
        res = cursor.fetchone()
        if not res:
            cursor.execute(
                "INSERT INTO `zepto_db_mapping` (category, parent_id, category_level, category_path) "
                "VALUES (%s, 0, 1, %s)",
                (main, main)
            )
            print(f"[+] Added new level 1 category mapping: {main}")

    # 3. Insert missing Level 2 categories (subcategory)
    for main, sub in categories:
        cursor.execute(
            "SELECT category_id FROM `zepto_db_mapping` WHERE category = %s AND category_level = 1",
            (main,)
        )
        parent_res = cursor.fetchone()
        if not parent_res:
            continue
        parent_id = parent_res[0]

        cursor.execute(
            "SELECT category_id FROM `zepto_db_mapping` WHERE category = %s AND parent_id = %s AND category_level = 2",
            (sub, parent_id)
        )
        res = cursor.fetchone()
        if not res:
            path = f"{main} > {sub}"
            cursor.execute(
                "INSERT INTO `zepto_db_mapping` (category, parent_id, category_level, category_path) "
                "VALUES (%s, %s, 2, %s)",
                (sub, parent_id, path)
            )
            print(f"[+] Added new level 2 category mapping: {path}")

    cursor.close()


def upload_products_to_mysql(products: List[Dict[str, Any]]):
    """Bulk upsert scraped products into DB under a single transaction.

    Dedupe/update strategy:
      - Filters and deduplicates in Python using sku_id, product_url, and name+subcategory matches.
      - Resolves duplicate listings to reuse existing database sku_ids to prevent duplicate records.
      - Uses ON DUPLICATE KEY UPDATE for batch inserts.
    """
    if not products:
        return

    from datetime import datetime

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ensure_unique_sku_id(conn)

        # Ensure autocommit is disabled to start transaction implicitly
        conn.autocommit = False

        # 1. Update/insert category mappings first (no commit yet)
        update_category_mapping(conn, products)

        # 2. Python-level Deduplication & Validation
        unique_batch_products = []
        seen_skus = set()
        seen_urls = set()
        seen_names = set()

        num_skips = 0

        for p in products:
            sku = str(p.get("sku_id") or "").strip()
            url = str(p.get("product_url") or "").strip()
            name = str(p.get("product_name") or "").strip().lower()
            sub = str(p.get("subcategory") or "").strip().lower()

            if not sku or not name:
                num_skips += 1
                continue

            # Prevent duplicate in same batch
            if sku in seen_skus:
                continue
            if url and url in seen_urls:
                continue
            name_key = (name, sub)
            if name_key in seen_names:
                continue

            seen_skus.add(sku)
            if url:
                seen_urls.add(url)
            seen_names.add(name_key)
            unique_batch_products.append(p)

        if not unique_batch_products:
            print(f"[+] DB Upload Stats: 0 inserts, 0 updates, {num_skips} skips.")
            conn.commit()
            return

        # 3. Check database for existing matches to prevent duplicates
        db_sku_to_sku = {}
        db_url_to_sku = {}
        db_name_sub_to_sku = {}

        skus_list = list(seen_skus)
        urls_list = [u for u in seen_urls if u]
        names_list = [k[0] for k in seen_names]
        subs_list = list(set([k[1] for k in seen_names]))

        query_parts = []
        params = []

        if skus_list:
            placeholders_sku = ", ".join(["%s"] * len(skus_list))
            query_parts.append(f"sku_id IN ({placeholders_sku})")
            params.extend(skus_list)
        if urls_list:
            placeholders_url = ", ".join(["%s"] * len(urls_list))
            query_parts.append(f"product_url IN ({placeholders_url})")
            params.extend(urls_list)
        if names_list and subs_list:
            placeholders_name = ", ".join(["%s"] * len(names_list))
            placeholders_sub = ", ".join(["%s"] * len(subs_list))
            query_parts.append(f"(product_name IN ({placeholders_name}) AND subcategory IN ({placeholders_sub}))")
            params.extend(names_list)
            params.extend(subs_list)

        if query_parts:
            sql = f"SELECT sku_id, product_url, product_name, subcategory FROM `{TABLE_NAME}` WHERE " + " OR ".join(query_parts)
            cursor.execute(sql, tuple(params))
            for row in cursor.fetchall():
                db_sku, db_url, db_name, db_sub = row
                db_sku = str(db_sku or "").strip()
                db_url = str(db_url or "").strip()
                db_name = str(db_name or "").strip().lower()
                db_sub = str(db_sub or "").strip().lower()

                if db_sku:
                    db_sku_to_sku[db_sku] = db_sku
                    if db_url:
                        db_url_to_sku[db_url] = db_sku
                    if db_name:
                        db_name_sub_to_sku[(db_name, db_sub)] = db_sku

        # 4. Align SKUs and Validate Types
        rows = []
        num_inserts = 0
        num_updates = 0

        for p in unique_batch_products:
            sku = str(p.get("sku_id") or "").strip()
            url = str(p.get("product_url") or "").strip()
            name = str(p.get("product_name") or "").strip().lower()
            sub = str(p.get("subcategory") or "").strip().lower()

            # Find if it matches any existing row in the DB
            matched_sku = None
            if sku in db_sku_to_sku:
                matched_sku = db_sku_to_sku[sku]
            elif url and url in db_url_to_sku:
                matched_sku = db_url_to_sku[url]
            elif (name, sub) in db_name_sub_to_sku:
                matched_sku = db_name_sub_to_sku[(name, sub)]

            if matched_sku:
                final_sku = matched_sku
                num_updates += 1
            else:
                final_sku = sku
                num_inserts += 1

            # Cast datatypes and apply safety fallbacks
            try:
                mrp_val = int(float(p.get("mrp") or 0))
            except (ValueError, TypeError):
                mrp_val = 0

            try:
                sp_val = int(float(p.get("selling_price") or 0))
            except (ValueError, TypeError):
                sp_val = 0

            try:
                rating_val = float(p.get("rating")) if p.get("rating") is not None else None
            except (ValueError, TypeError):
                rating_val = None

            try:
                review_val = float(p.get("review")) if p.get("review") is not None else None
            except (ValueError, TypeError):
                review_val = None

            availability_val = int(p.get("availability") or 1)

            scraped_at_val = p.get("scraped_at")
            if not scraped_at_val:
                scraped_at_val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            rows.append(
                (
                    final_sku,
                    p.get("product_name"),
                    p.get("product_description"),
                    p.get("quantity"),
                    rating_val,
                    review_val,
                    mrp_val,
                    sp_val,
                    p.get("main_category"),
                    p.get("subcategory"),
                    p.get("product_url"),
                    p.get("image_url"),
                    scraped_at_val,
                    availability_val,
                )
            )

        query = f"""
            INSERT INTO `{TABLE_NAME}` (
                sku_id,
                product_name,
                product_description,
                quantity,
                rating,
                review,
                mrp,
                selling_price,
                main_category,
                subcategory,
                product_url,
                image_url,
                scraped_at,
                availability
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                product_name=VALUES(product_name),
                product_description=VALUES(product_description),
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
                availability=VALUES(availability)
        """

        # 5. Insert products in batch
        if rows:
            cursor.executemany(query, rows)

        # 6. Update category_id mapping inside the zepto table
        print("[+] Updating category_id inside the zepto table...")
        update_category_id_query = """
            UPDATE `zepto` z
            JOIN `zepto_db_mapping` m_sub 
              ON z.subcategory = m_sub.category AND m_sub.category_level = 2
            JOIN `zepto_db_mapping` m_main 
              ON m_sub.parent_id = m_main.category_id AND z.main_category = m_main.category AND m_main.category_level = 1
            SET z.category_id = m_sub.category_id
            WHERE z.category_id IS NULL OR z.category_id <> m_sub.category_id;
        """
        cursor.execute(update_category_id_query)

        # 7. Commit whole transaction
        conn.commit()
        print(f"[+] DB Upload complete: {num_inserts} inserts, {num_updates} updates, {num_skips} skips.")

    except Exception as e:
        conn.rollback()
        print(f"[!] DB transaction rolled back due to error: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()

