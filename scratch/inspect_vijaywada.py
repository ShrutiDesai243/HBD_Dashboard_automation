import os
import sys
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

backend_dir = os.path.abspath('backend')
load_dotenv(dotenv_path=os.path.join(backend_dir, '.env'))

DB_USER = os.getenv('DB_USER')
DB_PASS = quote_plus(os.getenv('DB_PASSWORD') or "")
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = os.getenv('DB_PORT', '3306')

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        print("1. Inspecting vijaywada cities in Location_Master_India:")
        res = conn.execute(
            text("SELECT DISTINCT city_name FROM Location_Master_India WHERE LOWER(city_name) LIKE '%vijay%'")
        ).fetchall()
        for r in res:
            print(f"City: '{r[0]}' (Length: {len(r[0]) if r[0] else 0})")
            
        print("\n2. Inspecting pending invalid_value in unmatched_data_review:")
        res2 = conn.execute(
            text("SELECT DISTINCT invalid_value FROM unmatched_data_review WHERE LOWER(invalid_value) LIKE '%vijay%' AND correction_status = 'pending'")
        ).fetchall()
        for r in res2:
            print(f"Invalid Value: '{r[0]}' (Length: {len(r[0]) if r[0] else 0})")

except Exception as e:
    print("DB inspect failed:", e)
