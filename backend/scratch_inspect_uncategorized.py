import os
from sqlalchemy import create_engine, text
from config import Config

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

try:
    with engine.connect() as conn:
        print("--- Uncategorized Products in MySQL ---")
        rows = conn.execute(text("SELECT id, ASIN, Product_name, category, link FROM dmart_products WHERE category = 'Uncategorized'")).fetchall()
        print(f"Total uncategorized products: {len(rows)}")
        for r in rows:
            print(f"ID={r[0]} | SKU/ASIN={r[1]} | Name={repr(r[2])} | Link={r[4]}")
            
except Exception as e:
    print(f"Error: {e}")
