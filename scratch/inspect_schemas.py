import os
import sys
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('backend/.env')

db_user = os.getenv('DB_USER')
db_pass = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT', '3306')
db_name = os.getenv('DB_NAME')

quoted_pass = urllib.parse.quote_plus(db_pass or '')
engine = create_engine(f"mysql+pymysql://{db_user}:{quoted_pass}@{db_host}:{db_port}/{db_name}")

tables = ['master_table', 'product_master', 'Location_Master_India', 'product_category_master', 'unmatched_data_review']

try:
    with engine.connect() as conn:
        for table in tables:
            print(f"\n=====================================")
            print(f"Table: {table}")
            print(f"=====================================")
            try:
                # Get count
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
                print(f"Row count: {count:,}")
                
                # Get columns
                cols = conn.execute(text(f"DESCRIBE {table}")).fetchall()
                print("Columns:")
                for col in cols:
                    print(f" - {col[0]}: {col[1]} (Null: {col[2]}, Key: {col[3]}, Default: {col[4]})")
                
            except Exception as e:
                print(f"Error reading table {table}: {e}")
except Exception as e:
    print("Error:", e)
