import sys
import os

# Add backend to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from services.scrapers.dmart_engine.database import DatabaseManager

db_file = os.path.join(os.path.dirname(__file__), "test_temp.db")
schema_file = os.path.join(backend_path, "services", "scrapers", "dmart_engine", "schema.sql")

print("Initializing DatabaseManager...")
db = DatabaseManager(db_file, schema_file)
db.connect()

paths = [
    "Packaged Food > Ready To Cook",
    "Packaged Food > Ready to Cook",  # Case/spacing differences
    "Dairy & Beverages > Beverages",
    "Grocery > DMart Grocery > Rice & Rice Products",
    "New Category > Sub Category > Leaf Item"  # Dynamic fallback
]

print("\n--- Testing Hybrid Mapping & Resolution ---")
for p in paths:
    cat_id = db.resolve_category_path(p)
    print(f"Path: '{p}' -> Resolved ID: {cat_id}")

print("\nListing inserted categories from SQLite:")
db.cursor.execute("SELECT category_id, category_name, parent_id, category_level, category_path FROM dmart_category_master")
for row in db.cursor.fetchall():
    print(f"ID={row[0]} | Name='{row[1]}' | Parent={row[2]} | Level={row[3]} | Path='{row[4]}'")

db.close()

# Cleanup database file
if os.path.exists(db_file):
    os.remove(db_file)
if os.path.exists(db_file + "-wal"):
    os.remove(db_file + "-wal")
if os.path.exists(db_file + "-shm"):
    os.remove(db_file + "-shm")
print("\nDone. Cleaned up temp DB.")
