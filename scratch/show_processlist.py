import os
import sys
from sqlalchemy import text

# Add backend directory to path
sys.path.append(os.path.abspath('backend'))

from app import app
from extensions import db

with app.app_context():
    res = db.session.execute(text("SHOW PROCESSLIST")).fetchall()
    print("MySQL Processes:")
    for r in res:
        print(r)
