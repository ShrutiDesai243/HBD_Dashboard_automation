import os
from sqlalchemy import create_engine, text
import sys
from dotenv import load_dotenv

_backend_dir = os.path.abspath(os.path.dirname(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
from config import config

load_dotenv()
engine = create_engine(config.DATABASE_URI)

with engine.connect() as conn:
    print("Unique categories in amazon_products:")
    try:
        res = conn.execute(text("""
            SELECT categoryName, COUNT(*) as count 
            FROM amazon_products 
            GROUP BY categoryName 
            ORDER BY count DESC 
            LIMIT 50
        """)).mappings().fetchall()
        for r in res:
            print(f"  {r['categoryName']}: {r['count']}")
    except Exception as e:
        print(f"Error: {e}")
