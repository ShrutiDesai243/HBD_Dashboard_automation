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

try:
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            print("Fetching one 'Vijaywada' pending record...")
            row = conn.execute(
                text("SELECT review_id, data_type, invalid_value, table_name, row_id, row_data FROM unmatched_data_review WHERE LOWER(invalid_value) = 'vijaywada' AND correction_status = 'pending' LIMIT 1")
            ).fetchone()
            
            if not row:
                print("No record found!")
                sys.exit(0)
                
            review_id, data_type, invalid_value, table_name, row_id, row_data = row
            print(f"Record: ID={review_id}, Type={data_type}, Table={table_name}, Row ID={row_id}")
            
            r_data = json.loads(row_data) if row_data else {}
            print("Payload parsed successfully:", type(r_data))
            
            print("Attempting to re-integrate and update...")
            
            # Recreate the check in reintegrate_and_mark_corrected
            if table_name == 'master_table':
                exists = conn.execute(
                    text("SELECT 1 FROM master_table WHERE id = :id"),
                    {"id": r_data.get("id")}
                ).fetchone() is not None
                print("Exists in master_table:", exists)
                
                if exists:
                    conn.execute(
                        text("""
                            UPDATE master_table 
                            SET business_name=:business_name, primary_phone=:primary_phone, secondary_phone=:secondary_phone,
                                other_phones=:other_phones, email=:email, address=:address, city=:city, state=:state,
                                area=:area, pincode=:pincode
                            WHERE id=:id
                        """),
                        {
                            "id": r_data.get("id"),
                            "business_name": r_data.get("business_name"),
                            "primary_phone": r_data.get("primary_phone"),
                            "secondary_phone": r_data.get("secondary_phone"),
                            "other_phones": r_data.get("other_phones"),
                            "email": r_data.get("email"),
                            "address": r_data.get("address"),
                            "city": r_data.get("city"),
                            "state": r_data.get("state"),
                            "area": r_data.get("area"),
                            "pincode": r_data.get("pincode")
                        }
                    )
                    print("Updated record in master_table")
                else:
                    conn.execute(
                        text("""
                            INSERT INTO master_table (id, business_name, primary_phone, secondary_phone, other_phones, email, address, city, state, area, pincode)
                            VALUES (:id, :business_name, :primary_phone, :secondary_phone, :other_phones, :email, :address, :city, :state, :area, :pincode)
                        """),
                        {
                            "id": r_data.get("id"),
                            "business_name": r_data.get("business_name"),
                            "primary_phone": r_data.get("primary_phone"),
                            "secondary_phone": r_data.get("secondary_phone"),
                            "other_phones": r_data.get("other_phones"),
                            "email": r_data.get("email"),
                            "address": r_data.get("address"),
                            "city": r_data.get("city"),
                            "state": r_data.get("state"),
                            "area": r_data.get("area"),
                            "pincode": r_data.get("pincode")
                        }
                    )
                    print("Inserted record into master_table")
            
            # Update review record status
            conn.execute(
                text("UPDATE unmatched_data_review SET correction_status = 'corrected', invalid_value = :val WHERE review_id = :id"),
                {"val": r_data.get(data_type), "id": review_id}
            )
            print("Marked review record corrected.")
            
            trans.commit()
            print("Transaction committed successfully!")
        except Exception as e:
            trans.rollback()
            print("Operation failed:", e)

except Exception as e:
    print("DB inspect failed:", e)
