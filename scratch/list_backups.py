import os
import sys
from sqlalchemy import text

# Add backend directory to path
sys.path.append(os.path.abspath('backend'))

from app import app
from extensions import db

with app.app_context():
    # Fetch all tables
    res = db.session.execute(text("SHOW TABLES")).fetchall()
    print("All tables in database:")
    tables = [r[0] for r in res]
    for table in sorted(tables):
        if 'master_table' in table or 'backup' in table or '11' in table or 'june' in table or 'jun' in table:
            # Let's count rows if possible
            try:
                row_count = db.session.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
                print(f"Table: {table} - Rows: {row_count}")
            except Exception as e:
                print(f"Table: {table} - Error counting: {e}")
