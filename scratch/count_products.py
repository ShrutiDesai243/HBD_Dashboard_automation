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

try:
    with engine.connect() as conn:
        for table in ['product_master', 'product_master_table']:
            try:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
                print(f"{table} count: {cnt:,}")
            except Exception as e:
                print(f"Error checking {table}: {e}")
except Exception as e:
    print("Error:", e)
