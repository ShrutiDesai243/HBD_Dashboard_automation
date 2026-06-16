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
        print("1. Checking Location_Master_India for Ganesh Peth...")
        loc_row = conn.execute(
            text("SELECT id, area_name, city_name, state_full_name, state_short_code FROM Location_Master_India WHERE LOWER(area_name) = 'ganesh peth' AND LOWER(city_name) = 'solapur' LIMIT 1")
        ).fetchone()
        
        if loc_row:
            print(f"[FOUND] ID: {loc_row[0]}, Area: {loc_row[1]}, City: {loc_row[2]}, State: {loc_row[3]} ({loc_row[4]})")
        else:
            print("[NOT FOUND]")

        print("\n2. Checking correction_status in unmatched_data_review for ID 3499...")
        status_res = conn.execute(
            text("SELECT correction_status, invalid_value FROM unmatched_data_review WHERE review_id = 3499")
        ).fetchone()
        
        if status_res:
            print(f"[STATUS] Correction Status: {status_res[0]}, Invalid Value: {status_res[1]}")
        else:
            print("[NOT FOUND]")

except Exception as e:
    print("Failed to query DB:", e)
