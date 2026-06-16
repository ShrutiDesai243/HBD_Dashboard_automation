import os
import sys
import logging
import sqlite3
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

# Ensure backend folder is in path
backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import config

load_dotenv(os.path.join(backend_dir, '.env'))

MERGES = [
    {"src_id": 61, "dst_id": 1760579388, "name": "Pooja Needs", "dst_path": "Home Utility & Organisers > Pooja Needs", "dst_level": 2},
    {"src_id": 73, "dst_id": 1891455760, "name": "Festive Specials", "dst_path": "Seasonal & More > Festive Specials", "dst_level": 2},
    {"src_id": 81, "dst_id": 1575377540, "name": "Home Appliances", "dst_path": "Electronics & Appliances > Home Appliances", "dst_level": 2},
    {"src_id": 156162266, "dst_id": 3, "name": "Biscuits & Cookies", "dst_path": "Packaged Food > Biscuits & Cookies", "dst_level": 2},
    {"src_id": 1118636434, "dst_id": 38, "name": "Baby Care", "dst_path": "Baby & Kids > Baby Care", "dst_level": 2},
    {"src_id": 1802059203, "dst_id": 2, "name": "Beverages", "dst_path": "Dairy & Beverages > Beverages", "dst_level": 2},
    {"src_id": 1931775010, "dst_id": 53, "name": "Rice & Rice Products", "dst_path": "Grocery > DMart Grocery > Rice & Rice Products", "dst_level": 3}
]

def update_descendants_mysql(conn, parent_id, parent_path, parent_level):
    """Recursively update levels, paths, and product strings for MySQL category descendants."""
    query = text("SELECT category_id, category_name FROM dmart_categories WHERE parent_id = :parent_id")
    children = conn.execute(query, {"parent_id": parent_id}).fetchall()
    
    for child_id, child_name in children:
        child_level = parent_level + 1
        child_path = f"{parent_path} > {child_name}"
        
        # Update category path and level
        conn.execute(text("""
            UPDATE dmart_categories 
            SET category_level = :level, category_path = :path 
            WHERE category_id = :cat_id
        """), {"level": child_level, "path": child_path, "cat_id": child_id})
        logger.info(f"[MySQL] Updated descendant category '{child_name}' (ID: {child_id}) to path: '{child_path}' (level {child_level})")
        
        # Update products category string to new path
        p_res = conn.execute(text("""
            UPDATE dmart_products 
            SET category = :path 
            WHERE category_id = :cat_id
        """), {"path": child_path, "cat_id": child_id})
        logger.info(f"[MySQL] Updated {p_res.rowcount} products to category path: '{child_path}'")
        
        # Recurse
        update_descendants_mysql(conn, child_id, child_path, child_level)

def update_descendants_sqlite(cursor, parent_id, parent_path, parent_level):
    """Recursively update levels, paths, and product strings for SQLite category descendants."""
    cursor.execute("SELECT category_id, category_name FROM dmart_category_master WHERE parent_id = ?", (parent_id,))
    children = cursor.fetchall()
    
    for child_id, child_name in children:
        child_level = parent_level + 1
        child_path = f"{parent_path} > {child_name}"
        
        # Update category path and level
        cursor.execute("""
            UPDATE dmart_category_master 
            SET category_level = ?, category_path = ? 
            WHERE category_id = ?
        """, (child_level, child_path, child_id))
        logger.info(f"[SQLite] Updated descendant category '{child_name}' (ID: {child_id}) to path: '{child_path}' (level {child_level})")
        
        # Update products category string to new path
        cursor.execute("""
            UPDATE dmart_product_master 
            SET category_name = ? 
            WHERE category_id = ?
        """, (child_path, child_id))
        
        # Recurse
        update_descendants_sqlite(cursor, child_id, child_path, child_level)

def clean_mysql():
    logger.info("Starting MySQL database taxonomy merge...")
    engine = create_engine(config.DATABASE_URI)
    
    with engine.begin() as conn:
        logger.info("[MySQL] Disabling foreign key checks...")
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        try:
            for merge in MERGES:
                src_id = merge["src_id"]
                dst_id = merge["dst_id"]
                name = merge["name"]
                dst_path = merge["dst_path"]
                dst_level = merge["dst_level"]
                
                logger.info(f"[MySQL] Merging category '{name}' (ID {src_id} -> {dst_id})...")
                
                # 1. Update product category_id references
                p_res = conn.execute(text("""
                    UPDATE dmart_products 
                    SET category_id = :dst_id, category = :dst_path 
                    WHERE category_id = :src_id
                """), {"dst_id": dst_id, "dst_path": dst_path, "src_id": src_id})
                logger.info(f"  Mapped {p_res.rowcount} products to category ID {dst_id} ('{dst_path}').")
                
                # 2. Re-parent any child categories pointing to src_id
                children_res = conn.execute(text("""
                    UPDATE dmart_categories 
                    SET parent_id = :dst_id 
                    WHERE parent_id = :src_id
                """), {"dst_id": dst_id, "src_id": src_id})
                logger.info(f"  Re-parented {children_res.rowcount} child categories to parent ID {dst_id}.")
                
                # 3. Update paths and levels for descendants of the destination category
                update_descendants_mysql(conn, dst_id, dst_path, dst_level)
                
                # 4. Delete the duplicate source category row
                del_res = conn.execute(text("""
                    DELETE FROM dmart_categories WHERE category_id = :src_id
                """), {"src_id": src_id})
                logger.info(f"  Deleted duplicate level 1 category ID {src_id} (rows deleted: {del_res.rowcount}).")
                
        finally:
            logger.info("[MySQL] Re-enabling foreign key checks...")
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            
    logger.info("✅ MySQL taxonomy merge completed.")

def clean_sqlite():
    db_path = os.path.join(backend_dir, "output", "dmart_master.db")
    if not os.path.exists(db_path):
        logger.warning(f"[SQLite] Database file not found at {db_path}. Skipping SQLite merge.")
        return
        
    logger.info(f"Starting SQLite database taxonomy merge at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA foreign_keys=OFF")
        
        for merge in MERGES:
            src_id = merge["src_id"]
            dst_id = merge["dst_id"]
            name = merge["name"]
            dst_path = merge["dst_path"]
            dst_level = merge["dst_level"]
            
            logger.info(f"[SQLite] Merging category '{name}' (ID {src_id} -> {dst_id})...")
            
            # Check if source category exists
            cursor.execute("SELECT COUNT(*) FROM dmart_category_master WHERE category_id = ?", (src_id,))
            if cursor.fetchone()[0] == 0:
                logger.info(f"  Source category {src_id} does not exist in SQLite. Skipping merge for this one.")
                continue
                
            # 1. Update product category_id references
            cursor.execute("""
                UPDATE dmart_product_master 
                SET category_id = ?, category_name = ? 
                WHERE category_id = ?
            """, (dst_id, dst_path, src_id))
            
            # 2. Re-parent child categories
            cursor.execute("""
                UPDATE dmart_category_master 
                SET parent_id = ? 
                WHERE parent_id = ?
            """, (dst_id, src_id))
            
            # 3. Update paths/levels for descendants of target category
            update_descendants_sqlite(cursor, dst_id, dst_path, dst_level)
            
            # 4. Delete the duplicate source category row
            cursor.execute("DELETE FROM dmart_category_master WHERE category_id = ?", (src_id,))
            logger.info(f"  Successfully merged category in SQLite.")
            
        conn.commit()
        logger.info("✅ SQLite taxonomy merge completed.")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ SQLite merge failed: {e}")
        raise
    finally:
        cursor.execute("PRAGMA foreign_keys=ON")
        conn.close()

if __name__ == '__main__':
    clean_mysql()
    clean_sqlite()
