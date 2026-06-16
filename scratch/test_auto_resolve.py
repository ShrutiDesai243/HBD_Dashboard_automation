import os
import sys
import json
import urllib.request
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
        # Check how many 'vijaywada' pending records are in unmatched_data_review BEFORE the API call
        count_before = conn.execute(
            text("SELECT COUNT(*) FROM unmatched_data_review WHERE LOWER(invalid_value) = 'vijaywada' AND correction_status = 'pending'")
        ).scalar()
        print(f"Pending 'vijaywada' review records BEFORE API call: {count_before}")

        # Check if 'vijaywada' exists in Location_Master_India
        loc_row = conn.execute(
            text("SELECT id FROM Location_Master_India WHERE LOWER(city_name) = 'vijaywada' LIMIT 1")
        ).fetchone()
        if loc_row:
            print(f"Vijaywada exists in Location_Master_India (ID: {loc_row[0]})")
        else:
            print("Vijaywada does not exist in Location_Master_India")

        # Call the GET counts endpoint
        url = "http://127.0.0.1:8001/api/unmatched/counts"
        print("\nCalling GET /api/unmatched/counts to trigger auto-resolve...")
        try:
            response = urllib.request.urlopen(url, timeout=10)
            res_content = json.loads(response.read().decode('utf-8'))
            print("Response:", res_content)
            
            # Check counts in DB AFTER the API call
            count_after = conn.execute(
                text("SELECT COUNT(*) FROM unmatched_data_review WHERE LOWER(invalid_value) = 'vijaywada' AND correction_status = 'pending'")
            ).scalar()
            print(f"Pending 'vijaywada' review records AFTER API call: {count_after}")
            
            count_corrected = conn.execute(
                text("SELECT COUNT(*) FROM unmatched_data_review WHERE LOWER(invalid_value) = 'vijaywada' AND correction_status = 'corrected'")
            ).scalar()
            print(f"Corrected/Resolved 'vijaywada' review records: {count_corrected}")
            
            if count_after == 0 and count_corrected > 0:
                print("✅ Success! All 'vijaywada' pending records have been automatically resolved and marked as corrected!")
            else:
                print("❌ Pending records are still present or not updated")

        except Exception as api_err:
            print("API request failed:", api_err)

except Exception as e:
    print("DB Connection failed:", e)
