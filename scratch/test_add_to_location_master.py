import os
import sys
import json
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

print("Connecting to DB...")
try:
    with engine.connect() as conn:
        # 1. Find a pending unmatched location review record
        review_row = conn.execute(
            text("SELECT review_id, data_type, invalid_value, row_data FROM unmatched_data_review WHERE correction_status = 'pending' AND data_type IN ('city', 'state', 'area') LIMIT 1")
        ).fetchone()

        if not review_row:
            print("No pending unmatched location records found in unmatched_data_review. Creating a mock record for testing...")
            # Let's insert a mock record
            mock_row_data = {
                "id": 999999,
                "business_name": "Test Mock Location Business",
                "primary_phone": "9999999999",
                "secondary_phone": None,
                "other_phones": None,
                "email": "test@mocklocation.com",
                "address": "123 Mock Street, Solapur, Maharashtra, India",
                "city": "Solapur",
                "state": "Maharashtra",
                "area": "Mock Testing Area",
                "pincode": "413001"
            }
            conn.execute(
                text("""
                    INSERT INTO unmatched_data_review (data_type, invalid_value, correction_status, table_name, row_id, row_data)
                    VALUES ('area', 'Mock Testing Area', 'pending', 'master_table', 999999, :row_data)
                """),
                {"row_data": json.dumps(mock_row_data)}
            )
            conn.commit()
            
            review_row = conn.execute(
                text("SELECT review_id, data_type, invalid_value, row_data FROM unmatched_data_review WHERE review_id = LAST_INSERT_ID()")
            ).fetchone()

        review_id, data_type, invalid_value, row_data = review_row
        print(f"Testing with Unmatched Record: ID={review_id}, Type={data_type}, Invalid Value={invalid_value}")
        r_data = json.loads(row_data)
        print(f"Record Data: Area={r_data.get('area')}, City={r_data.get('city')}, State={r_data.get('state')}")

        # 2. Call the endpoint locally
        import urllib.request
        url = "http://127.0.0.1:8001/api/unmatched/add-to-location-master"
        req_data = json.dumps({"id": review_id}).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=req_data, 
            headers={'Content-Type': 'application/json'}
        )
        
        print("\nSending POST request to endpoint...")
        try:
            response = urllib.request.urlopen(req, timeout=10)
            res_content = json.loads(response.read().decode('utf-8'))
            print("Response:", res_content)
            
            # 3. Verify results in DB
            print("\nVerifying database results...")
            
            # Check Location_Master_India
            loc_row = conn.execute(
                text("SELECT id, area_name, city_name, state_full_name, state_short_code FROM Location_Master_India WHERE LOWER(area_name) = LOWER(:area) AND LOWER(city_name) = LOWER(:city) LIMIT 1"),
                {"area": r_data.get("area"), "city": r_data.get("city")}
            ).fetchone()
            
            if loc_row:
                print(f"✅ FOUND in Location_Master_India: ID={loc_row[0]}, Area={loc_row[1]}, City={loc_row[2]}, State={loc_row[3]} ({loc_row[4]})")
            else:
                print("❌ NOT FOUND in Location_Master_India")

            # Check unmatched_data_review status
            status_res = conn.execute(
                text("SELECT correction_status, invalid_value FROM unmatched_data_review WHERE review_id = :id"),
                {"id": review_id}
            ).fetchone()
            print(f"Unmatched Data Status: correction_status={status_res[0]}, invalid_value={status_res[1]}")
            if status_res[0] == 'corrected':
                print("✅ Unmatched Data Status marked as corrected!")
            else:
                print("❌ Unmatched Data Status not updated")
                
            # Clean up the mock items if we created them
            if r_data.get("id") == 999999:
                print("\nCleaning up mock testing data...")
                conn.execute(text("DELETE FROM unmatched_data_review WHERE review_id = :id"), {"id": review_id})
                conn.execute(text("DELETE FROM Location_Master_India WHERE id = :id"), {"id": loc_row[0]} if loc_row else {"id": 0})
                conn.commit()
                print("Cleanup complete.")
                
        except Exception as api_err:
            print("API request failed:", api_err)
            if hasattr(api_err, 'read'):
                print("API error detail:", api_err.read().decode('utf-8'))

except Exception as e:
    print("DB Connection failed:", e)
