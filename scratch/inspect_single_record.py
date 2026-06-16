import os
import sys
from sqlalchemy import text

# Add backend directory to path
sys.path.append(os.path.abspath('backend'))

from app import app
from extensions import db

with app.app_context():
    row_in_master = db.session.execute(
        text("SELECT id, city, state, area FROM master_table WHERE id = 55180")
    ).fetchone()
    print("Row 55180 in master_table:", row_in_master)
