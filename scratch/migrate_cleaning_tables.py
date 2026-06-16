import os
import sys
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load env using directory-agnostic path
_dot_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../backend/.env')
print(f"Loading environment from {_dot_env}")
load_dotenv(_dot_env)

# Ensure backend folder is in path to load app/models
backend_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

db_user = os.getenv('DB_USER')
db_pass = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT', '3306')
db_name = os.getenv('DB_NAME')

quoted_pass = urllib.parse.quote_plus(db_pass or '')
engine = create_engine(f"mysql+pymysql://{db_user}:{quoted_pass}@{db_host}:{db_port}/{db_name}")

try:
    with engine.connect() as conn:
        print("Adding columns to unmatched_data_review if they do not exist...")
        
        # Check if table_name column exists
        columns = conn.execute(text("DESCRIBE unmatched_data_review")).fetchall()
        col_names = [col[0] for col in columns]
        
        if 'table_name' not in col_names:
            conn.execute(text("ALTER TABLE unmatched_data_review ADD COLUMN table_name VARCHAR(100) NULL"))
            print(" - Added table_name column")
        else:
            print(" - table_name already exists")
            
        if 'row_id' not in col_names:
            conn.execute(text("ALTER TABLE unmatched_data_review ADD COLUMN row_id INT NULL"))
            print(" - Added row_id column")
        else:
            print(" - row_id already exists")
            
        if 'row_data' not in col_names:
            conn.execute(text("ALTER TABLE unmatched_data_review ADD COLUMN row_data LONGTEXT NULL"))
            print(" - Added row_data column")
        else:
            print(" - row_data already exists")
            
        conn.commit()
        print("Schema migration for unmatched_data_review: SUCCESS")
        
except Exception as e:
    print("Error migrating unmatched_data_review:", e)

# Now run db.create_all() by initializing flask app
try:
    # Change working directory to backend folder so output/gdrive_etl.log resolves correctly
    os.chdir(backend_path)
    print(f"Changed directory to {backend_path}")
    from app import app
    from extensions import db
    
    with app.app_context():
        db.create_all()
        print("SQLAlchemy db.create_all(): SUCCESS (data_cleaning_log and duplicate_records_review tables created if missing)")
except Exception as e:
    print("Error running db.create_all():", e)
