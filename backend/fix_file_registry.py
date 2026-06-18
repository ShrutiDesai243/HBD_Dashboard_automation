import logging
from sqlalchemy import create_engine, text
import os
import sys

# Add current dir to path
sys.path.append(os.getcwd())
from config import config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ManualMigration")

def run_migration():
    engine = create_engine(config.DATABASE_URI)
    with engine.begin() as conn:
        # Define columns that need to be checked and added if missing
        required_columns = {
            'drive_folder_id': 'VARCHAR(255)',
            'folder_name': 'VARCHAR(255)',
            'path': 'TEXT',
            'modified_time': 'DATETIME'
        }

        try:
            for col_name, col_type in required_columns.items():
                res = conn.execute(text(f"SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'file_registry' AND COLUMN_NAME = '{col_name}'"))
                if res.scalar() == 0:
                    logger.info(f"⚠️ Column `{col_name}` missing in file_registry. Adding...")
                    conn.execute(text(f"ALTER TABLE file_registry ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"✅ Column `{col_name}` added successfully.")
                else:
                    logger.info(f"✅ Column `{col_name}` already exists in file_registry.")
        except Exception as e:
            logger.error(f"❌ Failed to migrate file_registry: {e}")

if __name__ == "__main__":
    run_migration()
