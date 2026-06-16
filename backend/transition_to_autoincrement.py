import os
import sys
import shutil
import sqlite3
import datetime
from sqlalchemy import text

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app import app
from extensions import db
from model.product_model.additional_products import DMart, DMartCategory
from services.scrapers.dmart_engine.config import DB_PATH

def run_migration():
    print("Starting DMart category AUTO_INCREMENT transition...")

    # 1. Back up SQLite database file
    if DB_PATH.exists():
        backup_path = DB_PATH.with_suffix(".db.bak")
        print(f"Backing up SQLite database to: {backup_path}")
        shutil.copy2(DB_PATH, backup_path)
    else:
        print("SQLite database not found at DB_PATH. Scraping may not have run yet.")
        return

    with app.app_context():
        try:
            # 2. Connect to SQLite and fetch current categories and products
            print("Reading current SQLite database...")
            sqlite_conn = sqlite3.connect(str(DB_PATH))
            sqlite_cursor = sqlite_conn.cursor()
            
            sqlite_cursor.execute("SELECT category_id, category_name, slug, parent_id, category_level, category_path FROM dmart_category_master")
            sqlite_cats = sqlite_cursor.fetchall()
            print(f"   Fetched {len(sqlite_cats)} categories from SQLite.")
            
            sqlite_cursor.execute("SELECT sku_id, product_name, brand, pack_size, mrp, dmart_price, availability, category_id, category_name, product_url, image_url, description, pincodes, scraped_at FROM dmart_product_master")
            sqlite_products = sqlite_cursor.fetchall()
            print(f"   Fetched {len(sqlite_products)} products from SQLite.")

            # 3. Connect to MySQL and truncate dmart_categories and dmart_products
            print("Truncating MySQL categories and products tables...")
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            db.session.execute(text("TRUNCATE TABLE dmart_products"))
            db.session.execute(text("TRUNCATE TABLE dmart_categories"))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            db.session.commit()
            print("Truncated MySQL tables successfully.")

            # 4. Alter MySQL dmart_categories category_id column to have AUTO_INCREMENT
            print("Ensuring MySQL dmart_categories category_id has AUTO_INCREMENT enabled...")
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            db.session.execute(text("ALTER TABLE dmart_categories MODIFY COLUMN category_id INT AUTO_INCREMENT"))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            db.session.commit()
            print("Enabled AUTO_INCREMENT on category_id.")

            # 5. Insert categories into MySQL level-by-level to generate AUTO_INCREMENT sequential IDs
            print("Migrating categories to MySQL level-by-level...")
            cats_by_level = {1: [], 2: [], 3: [], 4: []}
            for cat in sqlite_cats:
                c_id, name, slug, parent_id, level, path = cat
                level = level or 1
                cats_by_level[level].append({
                    'old_id': c_id,
                    'name': name,
                    'slug': slug,
                    'old_parent_id': parent_id,
                    'level': level,
                    'path': path
                })

            old_id_to_path = {cat[0]: cat[5] for cat in sqlite_cats}
            path_to_mysql_id = {}

            for level in sorted(cats_by_level.keys()):
                level_cats_inserted = 0
                for cat_info in cats_by_level[level]:
                    parent_mysql_id = None
                    if cat_info['old_parent_id'] is not None:
                        parent_path = old_id_to_path.get(cat_info['old_parent_id'])
                        if parent_path:
                            parent_mysql_id = path_to_mysql_id.get(parent_path)
                    
                    new_cat = DMartCategory(
                        category_name=cat_info['name'],
                        slug=cat_info['slug'],
                        parent_id=parent_mysql_id,
                        category_level=cat_info['level'],
                        category_path=cat_info['path']
                    )
                    db.session.add(new_cat)
                    db.session.flush() # Generate ID
                    path_to_mysql_id[cat_info['path']] = new_cat.category_id
                    level_cats_inserted += 1
                db.session.commit()
                print(f"   Level {level}: Migrated {level_cats_inserted} categories.")

            # 6. Recreate SQLite dmart_category_master and insert categories with the new IDs
            print("Rebuilding SQLite categories table...")
            sqlite_cursor.execute("DROP TABLE IF EXISTS dmart_category_master")
            sqlite_cursor.execute("""
            CREATE TABLE dmart_category_master (
                category_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name   TEXT    NOT NULL,
                slug            TEXT,
                parent_id       INTEGER,
                category_level  INTEGER,
                category_path   TEXT,
                FOREIGN KEY (parent_id) REFERENCES dmart_category_master(category_id)
            )""")
            
            mysql_cats = DMartCategory.query.order_by(DMartCategory.category_id).all()
            for mc in mysql_cats:
                sqlite_cursor.execute(
                    "INSERT INTO dmart_category_master (category_id, category_name, slug, parent_id, category_level, category_path) VALUES (?, ?, ?, ?, ?, ?)",
                    (mc.category_id, mc.category_name, mc.slug, mc.parent_id, mc.category_level, mc.category_path)
                )
            sqlite_conn.commit()
            print(f"Re-populated SQLite categories ({len(mysql_cats)} rows).")

            # 7. Migrate products to MySQL and SQLite
            print("Migrating products to MySQL and SQLite...")
            sqlite_products_batch = []
            mysql_products_by_asin = {}
            
            # Sort products by scraped_at ascending so that the latest product details for each ASIN override older ones
            sorted_products = sorted(
                sqlite_products,
                key=lambda x: x[13] if x[13] else ""
            )

            for prod in sorted_products:
                sku_id, name, brand, pack_size, mrp, dmart_price, availability, old_cat_id, cat_path, prod_url, img_url, desc, pincodes, scraped_at = prod
                
                sku_id_str = str(sku_id).strip()
                if not sku_id_str:
                    continue

                actual_path = cat_path
                if not actual_path and old_cat_id:
                    actual_path = old_id_to_path.get(old_cat_id)
                if not actual_path:
                    actual_path = "Uncategorized"
                    
                new_cat_id = path_to_mysql_id.get(actual_path)
                
                price_str = str(dmart_price) if dmart_price is not None else "0.0"
                mrp_str = str(mrp) if mrp is not None else "0.0"
                
                dt_scraped = None
                if scraped_at:
                    try:
                        dt_scraped = datetime.datetime.strptime(scraped_at, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            dt_scraped = datetime.datetime.fromisoformat(scraped_at)
                        except Exception:
                            dt_scraped = datetime.datetime.now()
                else:
                    dt_scraped = datetime.datetime.now()

                # Deduplicate for MySQL
                mysql_prod_dict = {
                    'ASIN': sku_id_str,
                    'Product_name': name,
                    'Image_URLs': img_url,
                    'link': prod_url,
                    'price': price_str,
                    'listPrice': mrp_str,
                    'category': actual_path,
                    'Brand': brand,
                    'category_id': new_cat_id,
                    'quantity': pack_size,
                    'availability': availability,
                    'scraped_at': dt_scraped
                }
                mysql_products_by_asin[sku_id_str] = mysql_prod_dict
                
                sqlite_products_batch.append((
                    sku_id_str, name, brand, pack_size, mrp, dmart_price, availability, new_cat_id, actual_path, prod_url, img_url, desc, pincodes, scraped_at
                ))
            
            # Bulk insert unique products to MySQL
            print(f"Bulk inserting {len(mysql_products_by_asin)} unique products to MySQL...")
            db.session.bulk_insert_mappings(DMart, list(mysql_products_by_asin.values()))
            db.session.commit()
            print(f"Migrated products to MySQL successfully.")

            # 8. Rebuild SQLite dmart_product_master and insert products
            print("Rebuilding SQLite products table...")
            sqlite_cursor.execute("DROP TABLE IF EXISTS dmart_product_master")
            sqlite_cursor.execute("""
            CREATE TABLE dmart_product_master (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                sku_id          TEXT    NOT NULL,
                product_name    TEXT,
                brand           TEXT,
                pack_size       TEXT,
                mrp             REAL,
                dmart_price     REAL,
                availability    INTEGER,
                category_id     INTEGER,
                category_name   TEXT,
                product_url     TEXT,
                image_url       TEXT,
                description     TEXT,
                pincodes        TEXT,
                scraped_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES dmart_category_master(category_id)
            )""")
            
            sqlite_cursor.executemany("""
            INSERT INTO dmart_product_master (
                sku_id, product_name, brand, pack_size, mrp, dmart_price, availability, category_id, category_name, product_url, image_url, description, pincodes, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sqlite_products_batch)
            
            # Recreate indices
            sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_sku ON dmart_product_master(sku_id)")
            sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_brand ON dmart_product_master(brand)")
            sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_category ON dmart_product_master(category_id)")
            sqlite_cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_scraped ON dmart_product_master(scraped_at)")
            
            sqlite_conn.commit()
            sqlite_conn.close()
            print(f"Re-populated SQLite products ({len(sqlite_products_batch)} rows).")
            print("Database transition completed successfully!")

        except Exception as e:
            db.session.rollback()
            print(f"Migration failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    run_migration()
