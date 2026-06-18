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
    """Automatically inserts missing main_category and subcategory entries into zepto_db_mapping."""
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
            cursor.execute("SELECT COALESCE(MAX(category_id), 0) FROM `zepto_db_mapping`")
            max_id = cursor.fetchone()[0]
            new_id = max_id + 1

            cursor.execute(
                "INSERT INTO `zepto_db_mapping` (category_id, category, parent_id, category_level, category_path) "
                "VALUES (%s, %s, NULL, 1, %s)",
                (new_id, main, main)
            )
            conn.commit()
            print(f"[+] Added new level 1 category mapping: {main} (ID: {new_id})")

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
            cursor.execute("SELECT COALESCE(MAX(category_id), 0) FROM `zepto_db_mapping`")
            max_id = cursor.fetchone()[0]
            new_id = max_id + 1

            path = f"{main} > {sub}"
            cursor.execute(
                "INSERT INTO `zepto_db_mapping` (category_id, category, parent_id, category_level, category_path) "
                "VALUES (%s, %s, %s, 2, %s)",
                (new_id, sub, parent_id, path)
            )
            conn.commit()
            print(f"[+] Added new level 2 category mapping: {path} (ID: {new_id})")

    cursor.close()


def upload_products_to_mysql(products: List[Dict[str, Any]]):

    """Bulk upsert scraped products into DB.

    Dedupe/update strategy: ON DUPLICATE KEY UPDATE driven by UNIQUE(sku_id).
    """
    if not products:
        return

    conn = get_connection()
    cursor = conn.cursor()

    ensure_unique_sku_id(conn)

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

    # Normalize rows to match expected columns/order
    rows = []
    for p in products:
        sku_id = p.get("sku_id")
        if not sku_id:
            # sku_id is required for dedupe/upsert
            continue

        rows.append(
            (
                str(sku_id).strip(),
                p.get("product_name"),
                p.get("product_description"),
                p.get("quantity"),
                p.get("rating"),
                p.get("review"),
                p.get("mrp"),
                p.get("selling_price"),
                p.get("main_category"),
                p.get("subcategory"),
                p.get("product_url"),
                p.get("image_url"),
                p.get("scraped_at"),
                p.get("availability"),
            )
        )

    if not rows:
        cursor.close()
        conn.close()
        return

    cursor.executemany(query, rows)
    conn.commit()

    print(f"[+] DB upsert complete: attempted {len(rows)} rows")

    # Call the auto mapping update helper
    try:
        update_category_mapping(conn, products)

        # Now update the category_id inside the zepto table (for both new and existing data)
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
        conn.commit()
        print(f"[+] category_id update complete: updated {cursor.rowcount} rows")
    except Exception as e:
        print(f"[!] Failed to update category mapping or category_id: {e}")

    cursor.close()
    conn.close()

