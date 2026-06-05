import os
from sqlalchemy import create_engine, text
import sys
from dotenv import load_dotenv
import re

_backend_dir = os.path.abspath(os.path.dirname(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
from config import config

load_dotenv()
engine = create_engine(config.DATABASE_URI)

# Match Devanagari range: \u0900-\u097f
hindi_re = re.compile(r'[\u0900-\u097f]')

with engine.connect() as conn:
    print("Checking for English-only products in amazon_products...")
    try:
        # Fetch 2000 products with reviews > 0 and check how many have no Hindi
        rows = conn.execute(text("""
            SELECT id, asin, title, categoryName 
            FROM amazon_products 
            WHERE reviews > 0 
            ORDER BY reviews DESC 
            LIMIT 5000
        """)).mappings().fetchall()
        
        english_rows = []
        for r in rows:
            title = r["title"] or ""
            cat = r["categoryName"] or ""
            if not hindi_re.search(title) and not hindi_re.search(cat):
                english_rows.append(r)
                
        print(f"Out of 5000 top reviewed products, {len(english_rows)} are English-only.")
        
        if english_rows:
            print("\nEnglish Sample 1:")
            for k, v in english_rows[0].items():
                print(f"  {k}: {v}")
            print("\nEnglish Sample 2:")
            for k, v in english_rows[1].items():
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")
