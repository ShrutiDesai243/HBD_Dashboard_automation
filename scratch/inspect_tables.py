import os
import sys
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Add parent directory to path if run from scratch
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

# Change working directory to backend to ensure .env is loaded correctly
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
os.chdir(backend_dir)
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
        print("\n--- unmatched_data_review ---")
        try:
            res = conn.execute(text("SHOW CREATE TABLE unmatched_data_review")).fetchone()
            print(res[1])
        except Exception as e:
            print(f"Error getting table: {e}")

        print("\n--- duplicate_records_review ---")
        try:
            res = conn.execute(text("SHOW CREATE TABLE duplicate_records_review")).fetchone()
            print(res[1])
        except Exception as e:
            print(f"Error getting table: {e}")

except Exception as e:
    print(f"Connection Error: {e}")
