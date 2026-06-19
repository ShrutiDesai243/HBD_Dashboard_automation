import os
import traceback
from sqlalchemy import text
from extensions import db

def sync_flipkart_db_mapping():
    """
    Reads distinct category combinations from flipkart_products_new and
    safely inserts any missing entries into the flipkart_db_mapping table.
    Builds the hierarchy using category_level (0, 1, 2) and parent_id.
    """
    try:
        print("[Sync Flipkart Mapping] Starting category extraction from flipkart_products_new...")

        sql_fetch = """
            SELECT DISTINCT main_category, subcategory, leaf_category
            FROM flipkart_products_new
            WHERE main_category IS NOT NULL AND main_category != ''
        """
        rows = db.session.execute(text(sql_fetch)).fetchall()
        print(f"[Sync Flipkart Mapping] Found {len(rows)} distinct category combinations in product data.")

        # Local cache for flipkart_db_mapping to minimize inserts/selects
        # Key: category_path (or just category_name for level 0 if path is empty)
        mapping_cache = {} # path -> (category_id, parent_id, category_level)

        sql_existing = "SELECT category_id, category_name, category_level, parent_id, category_path FROM flipkart_db_mapping"
        existing_rows = db.session.execute(text(sql_existing)).fetchall()
        for r in existing_rows:
            # For level 0, category_path is empty in existing records, so use category_name as key
            key = r.category_path if r.category_path else r.category_name
            mapping_cache[key] = (r.category_id, r.parent_id, r.category_level)

        new_inserts = 0

        def get_or_create(name, level, parent_id, path_key, actual_path):
            nonlocal new_inserts
            name = name.strip()
            path_key = path_key.strip()
            actual_path = actual_path.strip() if actual_path else ""

            if path_key in mapping_cache:
                return mapping_cache[path_key][0]

            # Insert new category
            insert_sql = """
                INSERT INTO flipkart_db_mapping (category_name, category_level, parent_id, category_path)
                VALUES (:name, :level, :parent_id, :path)
            """
            result = db.session.execute(text(insert_sql), {
                "name": name,
                "level": level,
                "parent_id": parent_id or 0,  # Root elements usually have parent_id=0 based on schema
                "path": actual_path
            })
            new_id = result.lastrowid
            mapping_cache[path_key] = (new_id, parent_id, level)
            new_inserts += 1
            return new_id

        for row in rows:
            main_cat = row.main_category
            sub_cat = row.subcategory
            leaf_cat = row.leaf_category

            if not main_cat:
                continue
            
            # Level 0 (Main Category)
            # Based on DB sample: (1, 'Electronics', 0, 0, '')
            l0_path_key = main_cat.strip()
            l0_id = get_or_create(
                name=main_cat,
                level=0,
                parent_id=0,
                path_key=l0_path_key,
                actual_path=""
            )

            # Level 1 (Subcategory)
            if sub_cat and sub_cat.strip() and sub_cat.strip() != 'null':
                l1_actual_path = f"{main_cat.strip()} > {sub_cat.strip()}"
                l1_id = get_or_create(
                    name=sub_cat,
                    level=1,
                    parent_id=l0_id,
                    path_key=l1_actual_path,
                    actual_path=l1_actual_path
                )

                # Level 2 (Leaf Category)
                if leaf_cat and leaf_cat.strip() and leaf_cat.strip() != 'null' and leaf_cat.strip() != sub_cat.strip():
                    l2_actual_path = f"{l1_actual_path} > {leaf_cat.strip()}"
                    get_or_create(
                        name=leaf_cat,
                        level=2,
                        parent_id=l1_id,
                        path_key=l2_actual_path,
                        actual_path=l2_actual_path
                    )

        db.session.commit()
        print(f"[Sync Flipkart Mapping] Completed successfully. Inserted {new_inserts} new categories.")
        return new_inserts

    except Exception as e:
        db.session.rollback()
        print(f"[Sync Flipkart Mapping] Error syncing flipkart_db_mapping: {traceback.format_exc()}")
        raise e
