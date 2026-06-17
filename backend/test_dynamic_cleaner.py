import os
import argparse
import time
from flask import Flask
from extensions import db
from sqlalchemy import text
from services.dynamic_cleaning_service import clean_and_route_batch
import sys

# Ensure unbuffered output for live logs
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

app = Flask(__name__)
from config import Config
app.config.from_object(Config)

db.init_app(app)

def run_cleaner(limit, target_table):
    with app.app_context():
        # Create running state file
        running_file = "logs/cleaner.running"
        with open(running_file, "w") as f:
            f.write(target_table)

        print("--------------------------------------------------")
        print(f"Starting Dynamic Cleaner Task (Limit: {limit}, Table: {target_table})")
        print("--------------------------------------------------")
        
        # Dynamically fetch columns first to check for status columns and support any table schema
        columns_query = db.session.execute(text(f"SHOW COLUMNS FROM {target_table}")).fetchall()
        col_names = [col[0].lower() for col in columns_query]
        
        try:
            if 'cleaning_status' not in col_names:
                print("Adding cleaning_status column to table...")
                db.session.execute(text(f"ALTER TABLE {target_table} ADD COLUMN cleaning_status VARCHAR(50) DEFAULT 'PENDING'"))
            if 'assigned_tier' not in col_names:
                print("Adding assigned_tier column to table...")
                db.session.execute(text(f"ALTER TABLE {target_table} ADD COLUMN assigned_tier VARCHAR(100) DEFAULT NULL"))
            if 'quality_score' not in col_names:
                print("Adding quality_score column to table...")
                db.session.execute(text(f"ALTER TABLE {target_table} ADD COLUMN quality_score INT DEFAULT NULL"))
            db.session.commit()
            
            # Re-fetch column names after alter to ensure our dictionary mapping works
            columns_query = db.session.execute(text(f"SHOW COLUMNS FROM {target_table}")).fetchall()
            col_names = [col[0].lower() for col in columns_query]
        except Exception as e:
            print(f"CRITICAL ERROR: Could not alter table to add status tracking columns. {e}")
            if os.path.exists(running_file):
                os.remove(running_file)
            return

        limit_val = int(limit) if limit != "all" else 250
        total_processed = 0
        batch_num = 1
        
        try:
            while True:
                # Check if stop file exists to allow graceful cancellation
                if os.path.exists("logs/stop_dynamic_cleaner"):
                    print(">>> Stop signal received. Halting cleaner.")
                    break

                print(f"Fetching batch {batch_num} (up to {limit_val} records)...")
                
                rows = db.session.execute(text(f"""
                    SELECT *
                    FROM {target_table}
                    WHERE cleaning_status != 'PROCESSED' OR cleaning_status IS NULL
                    LIMIT {limit_val}
                """)).fetchall()

                if not rows:
                    print("No more pending records found!")
                    break

                formatted_records = []
                for r in rows:
                    # Map the fetched row to a dictionary using lowercase column names
                    row_dict = dict(zip(col_names, r))
                    
                    # Fuzzy mapping for Name
                    name_val = row_dict.get("name") or row_dict.get("business_name") or row_dict.get("company_name") or row_dict.get("title") or row_dict.get("company")
                    
                    # Fuzzy mapping for Phone
                    phone_val = row_dict.get("phone_number") or row_dict.get("phone") or row_dict.get("mobile") or row_dict.get("contact") or row_dict.get("primary_phone")
                    
                    # Fuzzy mapping for Email/Website (sometimes emails are in website column)
                    email_val = row_dict.get("email") or row_dict.get("mail")
                    if not email_val:
                        website_val = str(row_dict.get("website", ""))
                        if "@" in website_val:
                            email_val = website_val
                            
                    # Fuzzy mapping for Address
                    address_val = row_dict.get("address") or row_dict.get("full_address") or row_dict.get("location")
                    
                    # ID mapping
                    record_id = row_dict.get("id") or row_dict.get("raw_id") or row_dict.get("record_id")

                    formatted_records.append({
                        "id": record_id,
                        "name": name_val,
                        "phone": phone_val,
                        "email": email_val,
                        "address": address_val,
                        "city": row_dict.get("city"),
                        "state": row_dict.get("state"),
                        "pincode": row_dict.get("pincode") or row_dict.get("zipcode") or row_dict.get("zip")
                    })

                print(f"Processing {len(formatted_records)} records...")
                try:
                    batch_count = clean_and_route_batch(target_table, formatted_records)
                    total_processed += batch_count
                    print(f"Batch {batch_num} complete. Total Processed: {total_processed}")
                except Exception as e:
                    print(f"Error processing batch {batch_num}: {e}")
                    print("Halting cleaner to prevent data corruption.")
                    break
                
                if limit != "all":
                    break
                    
                batch_num += 1

            print("--------------------------------------------------")
            print(f"Execution Complete. Total Records Processed: {total_processed}")
            print("--------------------------------------------------")
            
        finally:
            if os.path.exists(running_file):
                os.remove(running_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Dynamic Cleaner Background Task')
    parser.add_argument('--limit', type=str, default="100", help='Number of records to process, or "all"')
    parser.add_argument('--table', type=str, default="raw_clean_google_map_data", help='Table to clean')
    args = parser.parse_args()
    
    run_cleaner(args.limit, args.table)
