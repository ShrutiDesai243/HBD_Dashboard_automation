import os
import sys
import types
from sqlalchemy import text

# Monkeypatch migrations check to boot instantly
sys.modules['utils.db_migrations'] = types.ModuleType('utils.db_migrations')
sys.modules['utils.db_migrations'].run_pending_migrations = lambda app: print("Skipping migrations check for debug script.")

# Add backend directory to path
sys.path.append(os.path.abspath('.'))

from app import app
from extensions import db
from routes.unmatched_data_routes import auto_resolve_matched_records
from model.unmatched_data_review import UnmatchedDataReview

with app.app_context():
    print("Direct execution context initialized.")
    try:
        # We manually run the code inside auto_resolve_matched_records to see traceback of any error
        # Load valid states, cities, and areas from Location_Master_India
        states_res = db.session.execute(
            text("SELECT DISTINCT LOWER(state_full_name), LOWER(state_short_code) FROM Location_Master_India")
        ).fetchall()
        valid_states = set()
        for r in states_res:
            if r[0]: valid_states.add(r[0].strip())
            if r[1]: valid_states.add(r[1].strip())
            
        cities_res = db.session.execute(
            text("SELECT DISTINCT LOWER(city_name) FROM Location_Master_India")
        ).fetchall()
        valid_cities = {r[0].strip() for r in cities_res if r[0]}

        areas_res = db.session.execute(
            text("SELECT DISTINCT LOWER(area_name) FROM Location_Master_India")
        ).fetchall()
        valid_areas = {r[0].strip() for r in areas_res if r[0]}

        for dtype, valid_set in [('state', valid_states), ('city', valid_cities), ('area', valid_areas)]:
            # Get distinct pending invalid_values for this data_type
            distinct_pending = db.session.execute(
                text("""
                    SELECT DISTINCT invalid_value 
                    FROM unmatched_data_review 
                    WHERE data_type = :dtype AND correction_status = 'pending'
                """),
                {"dtype": dtype}
            ).fetchall()
            
            for (val_raw,) in distinct_pending:
                if not val_raw:
                    continue
                val = val_raw.strip().lower()
                if val in valid_set:
                    print(f"Found match for {dtype}: '{val_raw}'")
                    # 1. Fetch the payloads for records that have non-empty row_data and need reintegration
                    records_with_data = db.session.execute(
                        text("""
                            SELECT table_name, row_data 
                            FROM unmatched_data_review 
                            WHERE data_type = :dtype 
                            AND invalid_value = :val_raw 
                            AND correction_status = 'pending'
                            AND row_data IS NOT NULL 
                            AND row_data != '' 
                            AND row_data != '{}'
                        """),
                        {"dtype": dtype, "val_raw": val_raw}
                    ).fetchall()
                    print(f"Fetch results: found {len(records_with_data)} records with non-empty payload to reintegrate.")
                    
                    master_rows_data = []
                    product_rows_data = []
                    for table_name, row_data in records_with_data:
                        if table_name == 'master_table':
                            master_rows_data.append(row_data)
                        elif table_name == 'product_master':
                            product_rows_data.append(row_data)
                            
                    # Perform bulk reintegration
                    if master_rows_data:
                        print(f"Reintegrating {len(master_rows_data)} rows into master_table...")
                        from routes.unmatched_data_routes import bulk_reintegrate_master_table_raw
                        bulk_reintegrate_master_table_raw(master_rows_data)
                    if product_rows_data:
                        print(f"Reintegrating {len(product_rows_data)} rows into product_master...")
                        from routes.unmatched_data_routes import bulk_reintegrate_product_master_raw
                        bulk_reintegrate_product_master_raw(product_rows_data)
                    
                    # 2. Bulk resolve all records in unmatched_data_review for this invalid_value
                    print("Updating unmatched_data_review table to corrected...")
                    res = db.session.execute(
                        text("""
                            UPDATE unmatched_data_review 
                            SET correction_status = 'corrected' 
                            WHERE data_type = :dtype 
                            AND invalid_value = :val_raw 
                            AND correction_status = 'pending'
                        """),
                        {"dtype": dtype, "val_raw": val_raw}
                    )
                    print(f"Update query result: rowcount={res.rowcount}")
                    
        db.session.commit()
        print("Success! db.session.commit() completed successfully!")
    except Exception as err:
        db.session.rollback()
        import traceback
        traceback.print_exc()
