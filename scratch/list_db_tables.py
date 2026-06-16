import os
import sys
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load env
load_dotenv('backend/.env')

db_user = os.getenv('DB_USER')
db_pass = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT', '3306')
db_name = os.getenv('DB_NAME')

quoted_pass = urllib.parse.quote_plus(db_pass or '')

print(f"Connecting to {db_user}@{db_host}:{db_port}/{db_name}...")

engine = create_engine(f"mysql+pymysql://{db_user}:{quoted_pass}@{db_host}:{db_port}/{db_name}")

try:
    with engine.connect() as conn:
        tables = conn.execute(text("SHOW TABLES")).fetchall()
        print("Tables in remote database:")
        for t in tables:
            print(f" - {t[0]}")
except Exception as e:
    print("Error connecting or executing:", e)
