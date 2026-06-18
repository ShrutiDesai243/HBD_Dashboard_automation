import os
from sqlalchemy import text
from app import app
from extensions import db
from model.unmatched_data_review import UnmatchedDataReview
from model.master_table_model import MasterTable

# This script finds unmatched or invalid records in master_table and populates unmatched_data_review.
# For demonstration, we assume 'city', 'state', and 'business_category' could be empty or invalid.

def run_population():
    with app.app_context():
        print("Starting unmatched data population...")

        # Find missing or unstandardized cities
        # Note: We use raw SQL for performance instead of loading models
        city_query = text("""
            INSERT INTO unmatched_data_review (data_type, invalid_value, correction_status, created_at)
            SELECT DISTINCT 'city', COALESCE(city, ''), 'pending', NOW()
            FROM master_table
            WHERE (city IS NULL OR city = '' OR city = 'Unknown')
            AND COALESCE(city, '') NOT IN (SELECT COALESCE(invalid_value, '') FROM unmatched_data_review WHERE data_type = 'city')
        """)
        
        # Find missing or unstandardized states
        state_query = text("""
            INSERT INTO unmatched_data_review (data_type, invalid_value, correction_status, created_at)
            SELECT DISTINCT 'state', COALESCE(state, ''), 'pending', NOW()
            FROM master_table
            WHERE (state IS NULL OR state = '' OR state = 'Unknown')
            AND COALESCE(state, '') NOT IN (SELECT COALESCE(invalid_value, '') FROM unmatched_data_review WHERE data_type = 'state')
        """)

        # Find missing or unstandardized categories
        category_query = text("""
            INSERT INTO unmatched_data_review (data_type, invalid_value, correction_status, created_at)
            SELECT DISTINCT 'business_category', COALESCE(business_category, ''), 'pending', NOW()
            FROM master_table
            WHERE (business_category IS NULL OR business_category = '' OR business_category = 'Unknown')
            AND COALESCE(business_category, '') NOT IN (SELECT COALESCE(invalid_value, '') FROM unmatched_data_review WHERE data_type = 'business_category')
        """)

        # Find missing or unstandardized areas
        area_query = text("""
            INSERT INTO unmatched_data_review (data_type, invalid_value, correction_status, created_at)
            SELECT DISTINCT 'area', COALESCE(area, ''), 'pending', NOW()
            FROM master_table
            WHERE (area IS NULL OR area = '' OR area = 'Unknown')
            AND COALESCE(area, '') NOT IN (SELECT COALESCE(invalid_value, '') FROM unmatched_data_review WHERE data_type = 'area')
        """)

        try:
            print("Running city query...")
            result = db.session.execute(city_query)
            print(f"Inserted cities. Rowcount: {result.rowcount}")
            db.session.commit()

            print("Running state query...")
            result = db.session.execute(state_query)
            print(f"Inserted states. Rowcount: {result.rowcount}")
            db.session.commit()

            print("Running category query...")
            result = db.session.execute(category_query)
            print(f"Inserted categories. Rowcount: {result.rowcount}")
            db.session.commit()

            print("Running area query...")
            result = db.session.execute(area_query)
            print(f"Inserted areas. Rowcount: {result.rowcount}")
            db.session.commit()

            print("Population completed successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error during population: {e}")

if __name__ == "__main__":
    run_population()
