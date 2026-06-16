import os
import sys
import types
from sqlalchemy import text

# Monkeypatch migrations check to boot instantly
sys.modules['utils.db_migrations'] = types.ModuleType('utils.db_migrations')
sys.modules['utils.db_migrations'].run_pending_migrations = lambda app: print("Skipping migrations check for verify script.")

sys.path.append(os.path.abspath('.'))

from app import app
from extensions import db

with app.app_context():
    print("Verifying database restoration...")
    
    # 1. Check row counts
    count = db.session.execute(text("SELECT COUNT(*) FROM `master_table`")).scalar()
    print(f"Restored master_table count: {count} (Target: 100000)")
    
    # 2. Check a few sample records
    res = db.session.execute(text("SELECT id, business_name, city, state FROM `master_table` LIMIT 5")).fetchall()
    print("Sample records from master_table:")
    for r in res:
        print(r)
        
    # 3. Hit the counts API
    print("\nVerifying counts API internally...")
    try:
        from routes.unmatched_data_routes import auto_resolve_matched_records
        auto_resolve_matched_records()
        print("auto_resolve_matched_records() completed successfully.")
    except Exception as e:
        print(f"API verification failed: {e}")
