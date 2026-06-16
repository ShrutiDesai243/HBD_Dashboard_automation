import os
import sys
import time
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add current directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
from config import Config

print("Initializing database connection...")
load_dotenv(os.path.join(backend_dir, ".env"))
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

indexes = [
    # (table_name, columns_str, index_name)
    ("bigbasket", "main_category(100), subcategory(100)", "idx_bb_cat_subcat_composite"),
    ("blinkit", "category(100), sub_category(100)", "idx_bl_cat_subcat_composite"),
    ("zepto", "main_category(100), subcategory(100)", "idx_zp_cat_subcat_composite"),
    ("dmart_products", "category(255)", "idx_dm_category_composite"),
    ("indiamart_products", "category_name(100), sub_category_name(100)", "idx_im_cat_subcat_composite"),
    ("amazon_products", "categoryName(255)", "idx_am_category_composite"),
    ("flipkart_products", "category(100), subcategory(100)", "idx_fk_cat_subcat_composite"),
    ("jio_mart_products", "category(100), subcategory(100)", "idx_jm_cat_subcat_composite"),
]

with engine.begin() as conn:
    conn.execute(text("SET SESSION sql_mode=''"))
    print("Starting index creation process...")
    for tbl, cols, idx in indexes:
        start_time = time.time()
        print(f"Creating composite index {idx} on {tbl}({cols})...", end="", flush=True)
        try:
            conn.execute(text(f"CREATE INDEX {idx} ON {tbl} ({cols})"))
            duration = time.time() - start_time
            print(f" Done ({duration:.2f}s).", flush=True)
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate key name" in str(e).lower():
                print(" Already exists.", flush=True)
            else:
                print(f" Failed: {e}", flush=True)

print("Indexes check and creation complete.")
