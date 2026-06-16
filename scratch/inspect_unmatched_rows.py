import os
import sys
import json

backend_path = os.path.abspath('backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
os.chdir(backend_path)

from dotenv import load_dotenv
load_dotenv('.env')

from app import app
from extensions import db
from sqlalchemy import text

def inspect_unmatched():
    with app.app_context():
        # Query 10 pending area records
        query = text("""
            SELECT review_id, data_type, invalid_value, correction_status, table_name, row_id, row_data 
            FROM unmatched_data_review 
            WHERE data_type = 'area' AND correction_status = 'pending' 
            LIMIT 10
        """)
        rows = db.session.execute(query).fetchall()
        
        print(f"Total area unmatched records fetched: {len(rows)}")
        for r in rows:
            print(f"\nReview ID: {r[0]}")
            print(f"  - DataType: {r[1]}")
            print(f"  - InvalidValue: {repr(r[2])}")
            print(f"  - Status: {r[3]}")
            print(f"  - TableName: {repr(r[4])}")
            print(f"  - RowID: {r[5]}")
            print(f"  - RowData (first 100 chars): {repr(r[6][:100]) if r[6] else 'None'}")
            
            # If row_id is present, let's see if it's in any table
            if r[5]:
                # check master_table
                exists_m = db.session.execute(text("SELECT id, business_name, address FROM master_table WHERE id = :id"), {"id": r[5]}).fetchone()
                print(f"  - Found in master_table: {exists_m}")
                
                # check other table names if specified
                if r[4] and r[4] != 'master_table':
                    exists_other = db.session.execute(text(f"SELECT * FROM {r[4]} WHERE id = :id LIMIT 1"), {"id": r[5]}).fetchone()
                    print(f"  - Found in {r[4]}: {exists_other}")

if __name__ == "__main__":
    inspect_unmatched()
