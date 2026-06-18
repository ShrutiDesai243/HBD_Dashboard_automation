import os
import sys
import types
from sqlalchemy import text

# Monkeypatch migrations check to boot instantly
sys.modules['utils.db_migrations'] = types.ModuleType('utils.db_migrations')
sys.modules['utils.db_migrations'].run_pending_migrations = lambda app: print("Skipping migrations check for restore script.")

sys.path.append(os.path.abspath('.'))

from app import app
from extensions import db

with app.app_context():
    # In MySQL, CREATE/DROP/TRUNCATE cause implicit commits, but we use a transaction context for queries.
    try:
        print("1. Creating safety backup of the active master_table...")
        # Create backup table matching active table structure
        db.session.execute(text("CREATE TABLE IF NOT EXISTS `master_table_backup_before_restore_20260612` LIKE `master_table`"))
        # Clear backup table if exists to prevent duplicates
        db.session.execute(text("TRUNCATE TABLE `master_table_backup_before_restore_20260612`"))
        # Copy current rows
        db.session.execute(text("INSERT INTO `master_table_backup_before_restore_20260612` SELECT * FROM `master_table`"))
        
        backup_cnt = db.session.execute(text("SELECT COUNT(*) FROM `master_table_backup_before_restore_20260612`")).scalar()
        print(f"Safety backup created. Rows: {backup_cnt}")

        print("2. Dropping active master_table...")
        db.session.execute(text("DROP TABLE `master_table`"))

        print("3. Recreating master_table structure from master_table_backup_20260611...")
        db.session.execute(text("CREATE TABLE `master_table` LIKE `master_table_backup_20260611`"))

        print("4. Copying 100,000 rows from master_table_backup_20260611 into master_table...")
        db.session.execute(text("INSERT INTO `master_table` SELECT * FROM `master_table_backup_20260611`"))

        restored_cnt = db.session.execute(text("SELECT COUNT(*) FROM `master_table`")).scalar()
        print(f"Restoration complete! Restored master_table rows: {restored_cnt}")

        db.session.commit()
        print("Transaction committed successfully. Table restored!")
    except Exception as e:
        db.session.rollback()
        print(f"Error during restoration: {e}")
        import traceback
        traceback.print_exc()
