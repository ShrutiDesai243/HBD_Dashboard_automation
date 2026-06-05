import sys
import os
sys.path.append(r"c:\Users\dyaao\HBD_Dashboard_automation\backend")
from sqlalchemy import create_engine, text
from config import config

engine = create_engine(config.SQLALCHEMY_DATABASE_URI)

indexes_to_add = [
    # Table, Column, Index Name
    ("bigbasket", "main_category", "idx_bb_main_category"),
    ("bigbasket_dbmapping", "category_name", "idx_bbdm_category_name"),
    ("bigbasket_dbmapping", "category_id", "idx_bbdm_category_id"),
    ("bigbasket_dbmapping", "parent_id", "idx_bbdm_parent_id"),
    ("bigbasket_dbmapping", "category_level", "idx_bbdm_category_level"),
    
    ("blinkit", "category", "idx_bl_category"),
    ("blinkit_mapping", "category_name", "idx_blm_category_name"),
    ("blinkit_mapping", "category_id", "idx_blm_category_id"),
    ("blinkit_mapping", "parent_id", "idx_blm_parent_id"),
    ("blinkit_mapping", "category_level", "idx_blm_category_level"),
    
    ("dmart_products", "category", "idx_dm_category"),
    ("dmart_categories", "category_name", "idx_dmc_category_name"),
    ("dmart_categories", "parent_id", "idx_dmc_parent_id"),
    ("dmart_categories", "category_level", "idx_dmc_category_level"),
    
    ("indiamart_mappings", "category_name", "idx_imm_category_name"),
    ("indiamart_mappings", "parent_id", "idx_imm_parent_id"),
    ("indiamart_mappings", "category_level", "idx_imm_category_level"),
    
    ("zepto", "main_category", "idx_zp_main_category"),
    ("zepto_db_mapping", "category", "idx_zdm_category"),
    ("zepto_db_mapping", "category_id", "idx_zdm_category_id"),
    ("zepto_db_mapping", "parent_id", "idx_zdm_parent_id"),
    ("zepto_db_mapping", "category_level", "idx_zdm_category_level"),
]

with engine.begin() as conn:
    for tbl, col, idx in indexes_to_add:
        print(f"Adding index {idx} on {tbl}({col})...", flush=True)
        # Check if already exists
        try:
            # First try normal index
            conn.execute(text(f"CREATE INDEX {idx} ON {tbl} ({col})"))
            print(f"  Successfully created normal index {idx} on {tbl}({col})", flush=True)
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate key name" in str(e).lower():
                print(f"  Index {idx} already exists.", flush=True)
            else:
                # If it's a TEXT column, try prefix indexing
                try:
                    conn.execute(text(f"CREATE INDEX {idx} ON {tbl} ({col}(255))"))
                    print(f"  Successfully created prefix index {idx} on {tbl}({col}(255))", flush=True)
                except Exception as e2:
                    print(f"  Failed to create index {idx} on {tbl}({col}): {e2}", flush=True)
                    
print("Index creation run completed.", flush=True)
