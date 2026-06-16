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
    print("Checking status of runs directly from database...")
    with engine.connect() as conn:
        res = conn.execute(text("DESCRIBE data_cleaning_log")).fetchall()
        print("\n--- Columns in data_cleaning_log ---")
        for row in res:
            print(f"Column: {row[0]}, Type: {row[1]}")
            
        res_data = conn.execute(text("SELECT * FROM data_cleaning_log ORDER BY created_at DESC LIMIT 5")).fetchall()
        print("\n--- Last 5 Rows ---")
        for row in res_data:
            print(row)
except Exception as e:
    print("DB Connection failed:", e)
