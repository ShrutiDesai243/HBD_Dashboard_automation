import os
import sys
import logging
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

def run_cleanup():
    logger.info("Starting DMart categories duplicate cleanup and schema modification...")
    engine = create_engine(config.DATABASE_URI)
    
    with engine.begin() as conn:
        # 1. Disable Foreign Key Checks
        logger.info("Disabling foreign key checks temporarily...")
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        try:
            # 2. Update dmart_products referencing ID 99 to 198713113 (Home Cleaners & Bathroom Needs)
            logger.info("Migrating products from category ID 99 to 198713113...")
            prod_99_res = conn.execute(text(
                "UPDATE dmart_products SET category_id = 198713113 WHERE category_id = 99"
            ))
            logger.info(f"Updated {prod_99_res.rowcount} products referencing category ID 99.")
            
            # Delete the duplicate category ID 99
            cat_99_res = conn.execute(text(
                "DELETE FROM dmart_categories WHERE category_id = 99"
            ))
            logger.info(f"Deleted duplicate category ID 99 (rows deleted: {cat_99_res.rowcount}).")
            
            # 3. Update dmart_products referencing ID 101 to 2120253707 (Hair Care)
            logger.info("Migrating products from category ID 101 to 2120253707...")
            prod_101_res = conn.execute(text(
                "UPDATE dmart_products SET category_id = 2120253707 WHERE category_id = 101"
            ))
            logger.info(f"Updated {prod_101_res.rowcount} products referencing category ID 101.")
            
            # Delete the duplicate category ID 101
            cat_101_res = conn.execute(text(
                "DELETE FROM dmart_categories WHERE category_id = 101"
            ))
            logger.info(f"Deleted duplicate category ID 101 (rows deleted: {cat_101_res.rowcount}).")
            
            # 4. Migrate 'Others' from ID 98 to 1579920142
            logger.info("Migrating products from category ID 98 to 1579920142...")
            prod_98_res = conn.execute(text(
                "UPDATE dmart_products SET category_id = 1579920142 WHERE category_id = 98"
            ))
            logger.info(f"Updated {prod_98_res.rowcount} products referencing category ID 98.")
            
            # Update the category ID itself in dmart_categories
            cat_98_res = conn.execute(text(
                "UPDATE dmart_categories SET category_id = 1579920142 WHERE category_id = 98"
            ))
            logger.info(f"Updated category ID 98 to 1579920142 (rows updated: {cat_98_res.rowcount}).")

            # 5. Remove AUTO_INCREMENT from category_id in dmart_categories
            logger.info("Removing AUTO_INCREMENT from `dmart_categories.category_id`...")
            # We try to alter direct first
            try:
                conn.execute(text("ALTER TABLE dmart_categories MODIFY COLUMN category_id INT NOT NULL"))
                logger.info("✅ Successfully removed AUTO_INCREMENT from `category_id` column.")
            except Exception as alter_err:
                logger.warning(f"Direct AUTO_INCREMENT removal failed: {alter_err}. Attempting with FK drop...")
                # Drop constraints
                try:
                    conn.execute(text("ALTER TABLE dmart_products DROP FOREIGN KEY fk_dmart_products_category"))
                except Exception:
                    try:
                        conn.execute(text("ALTER TABLE dmart_products DROP FOREIGN KEY dmart_products_ibfk_1"))
                    except Exception:
                        pass
                try:
                    conn.execute(text("ALTER TABLE dmart_categories DROP FOREIGN KEY fk_categories_parent"))
                except Exception:
                    try:
                        conn.execute(text("ALTER TABLE dmart_categories DROP FOREIGN KEY dmart_categories_ibfk_1"))
                    except Exception:
                        pass
                # Alter column
                conn.execute(text("ALTER TABLE dmart_categories MODIFY COLUMN category_id INT NOT NULL"))
                # Re-add constraints
                conn.execute(text("""
                    ALTER TABLE dmart_categories ADD CONSTRAINT fk_categories_parent 
                    FOREIGN KEY (parent_id) REFERENCES dmart_categories(category_id) ON DELETE SET NULL
                """))
                conn.execute(text("""
                    ALTER TABLE dmart_products ADD CONSTRAINT fk_dmart_products_category 
                    FOREIGN KEY (category_id) REFERENCES dmart_categories(category_id) ON DELETE SET NULL
                """))
                logger.info("✅ Successfully removed AUTO_INCREMENT from `category_id` via FK drop fallback.")
                
        finally:
            # 6. Re-enable Foreign Key Checks
            logger.info("Re-enabling foreign key checks...")
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            
    logger.info("Cleanup transaction committed successfully.")

if __name__ == '__main__':
    run_cleanup()
