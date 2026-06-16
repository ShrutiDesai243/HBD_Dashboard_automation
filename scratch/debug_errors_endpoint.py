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

def test_queries():
    with app.app_context():
        # Let's count records with invalid phone/email with various sql queries:
        
        # Query 1: The query from get_table_counts_and_metrics
        q1 = text("""
            SELECT COUNT(*) FROM master_table 
            WHERE (primary_phone IS NOT NULL AND primary_phone != '' AND NOT (primary_phone REGEXP '^[0-9+ -]{8,20}$'))
               OR (email IS NOT NULL AND email != '' AND NOT (email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\\.[a-zA-Z]{2,}$'))
        """)
        # Query 2: The query from get_cleaning_errors route
        q2 = text("""
            SELECT COUNT(*)
            FROM master_table
            WHERE (primary_phone IS NOT NULL AND primary_phone != '' AND NOT (primary_phone REGEXP '^[0-9+ -]{8,20}$'))
               OR (email IS NOT NULL AND email != '' AND NOT (email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'))
        """)
        # Query 3: Using a single backslash
        q3 = text("""
            SELECT COUNT(*)
            FROM master_table
            WHERE (primary_phone IS NOT NULL AND primary_phone != '' AND NOT (primary_phone REGEXP '^[0-9+ -]{8,20}$'))
               OR (email IS NOT NULL AND email != '' AND NOT (email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'))
        """)
        # Query 4: Checking just phone invalid count
        q_phone = text("""
            SELECT COUNT(*) FROM master_table 
            WHERE primary_phone IS NOT NULL AND primary_phone != '' AND NOT (primary_phone REGEXP '^[0-9+ -]{8,20}$')
        """)
        # Query 5: Checking just email invalid count
        q_email_1 = text("""
            SELECT COUNT(*) FROM master_table 
            WHERE email IS NOT NULL AND email != '' AND NOT (email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\\.[a-zA-Z]{2,}$')
        """)
        q_email_2 = text("""
            SELECT COUNT(*) FROM master_table 
            WHERE email IS NOT NULL AND email != '' AND NOT (email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$')
        """)
        
        try:
            print(f"Phone only count: {db.session.execute(q_phone).fetchone()[0]}")
            print(f"Email with 4-backslash count: {db.session.execute(q_email_1).fetchone()[0]}")
            print(f"Email with 2-backslash count: {db.session.execute(q_email_2).fetchone()[0]}")
            print(f"Query 1 (4-backslash query) count: {db.session.execute(q1).fetchone()[0]}")
            print(f"Query 2 (2-backslash query) count: {db.session.execute(q2).fetchone()[0]}")
            
            # Let's print the actual SQL string that MySQL receives for q2:
            print("\nTesting SELECT query with 2-backslash:")
            select_q = text("""
                SELECT id, business_name, primary_phone, email
                FROM master_table
                WHERE (primary_phone IS NOT NULL AND primary_phone != '' AND NOT (primary_phone REGEXP '^[0-9+ -]{8,20}$'))
                   OR (email IS NOT NULL AND email != '' AND NOT (email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'))
                LIMIT 5
            """)
            rows = db.session.execute(select_q).fetchall()
            print(f"Result count with 2-backslash: {len(rows)}")
            
            print("\nTesting SELECT query with 4-backslash:")
            select_q_4 = text("""
                SELECT id, business_name, primary_phone, email
                FROM master_table
                WHERE (primary_phone IS NOT NULL AND primary_phone != '' AND NOT (primary_phone REGEXP '^[0-9+ -]{8,20}$'))
                   OR (email IS NOT NULL AND email != '' AND NOT (email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\\.[a-zA-Z]{2,}$'))
                LIMIT 5
            """)
            rows_4 = db.session.execute(select_q_4).fetchall()
            print(f"Result count with 4-backslash: {len(rows_4)}")
            for r in rows_4:
                print(f"  ID: {r[0]}, Business: {r[1]}, Phone: {r[2]}, Email: {r[3]}")
                
        except Exception as e:
            print(f"Error executing: {e}")

if __name__ == "__main__":
    test_queries()
