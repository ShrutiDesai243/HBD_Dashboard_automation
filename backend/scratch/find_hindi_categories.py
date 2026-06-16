import os
import sys
from sqlalchemy import create_engine, text

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import config

engine = create_engine(config.DATABASE_URI)

def is_hindi(text_val):
    if not text_val:
        return False
    return any('\u0900' <= char <= '\u097f' for char in text_val)

output_file = os.path.join(os.path.dirname(__file__), 'find_hindi_categories_results.txt')

with engine.connect() as conn:
    # Fetch all active master categories
    res = conn.execute(text("SELECT id, name, path, level FROM master_categories WHERE is_active = 1")).fetchall()
    
    hindi_cats = []
    for row in res:
        cat_id, name, path, level = row
        if is_hindi(name) or is_hindi(path):
            # Count how many mapping entries point to this category
            map_count = conn.execute(text(
                "SELECT COUNT(*) FROM platform_category_mapping WHERE master_category_id = :id AND is_active = 1"
            ), {"id": cat_id}).fetchone()[0]
            
            hindi_cats.append((cat_id, name, path, level, map_count))
            
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=== Searching for Hindi Categories in Database ===\n")
        f.write(f"Found {len(hindi_cats)} active Hindi categories:\n")
        for cat_id, name, path, level, map_count in sorted(hindi_cats, key=lambda x: x[4], reverse=True):
            f.write(f"ID: {cat_id} | Name: {name} | Level: {level} | Path: {path} | Mapped Entries: {map_count}\n")
            
    print(f"Results written to: {output_file}")
