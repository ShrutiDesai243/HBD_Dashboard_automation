import logging
from sqlalchemy import text, inspect
from extensions import db

logger = logging.getLogger(__name__)

def run_pending_migrations(app):
    """
    Executes safe, idempotent database migrations.
    Now includes existence checks to prevent "Table doesn't exist" crashes.
    """
    with app.app_context():
        try:
            logger.info("🔄 Checking for pending DB migrations...")
            engine = db.engine
            
            with engine.connect() as conn:
                
                # --- Helper function to check if a table exists ---
                def table_exists(table_name):
                    check = text("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tname")
                    return conn.execute(check, {"tname": table_name}).scalar() > 0

                # === ISSUE 2: drive_folder_registry Status ENUM Fix ===
                if table_exists('drive_folder_registry'):
                    trans = conn.begin()
                    try:
                        conn.execute(text("UPDATE drive_folder_registry SET status='DONE' WHERE status IN ('Completed', 'UPDATED', 'Processed')"))
                        conn.execute(text("UPDATE drive_folder_registry SET status='SCANNING' WHERE status IN ('Processing', 'Scanning', 'InProgress')"))
                        conn.execute(text("UPDATE drive_folder_registry SET status='PENDING' WHERE status IN ('Pending', 'New')"))
                        conn.execute(text("UPDATE drive_folder_registry SET status='ERROR' WHERE status IN ('Error', 'Failed')"))
                        
                        conn.execute(text("""
                            ALTER TABLE drive_folder_registry 
                            MODIFY COLUMN status ENUM('PENDING', 'SCANNING', 'DONE', 'ERROR') 
                            DEFAULT 'PENDING'
                        """))
                        logger.info("✅ `drive_folder_registry` status column migrated to ENUM.")
                    except Exception as e:
                        logger.warning(f"⚠️ drive_folder_registry migration skipped: {e}")
                        trans.rollback()
                    else:
                        trans.commit()
                else:
                    logger.warning("⏩ Table `drive_folder_registry` does not exist yet. Skipping ENUM update.")

                # === FIX: Use 'raw_google_map' instead of 'raw_google_map_drive_data' ===
                TARGET_TABLE = "raw_google_map"

                if table_exists(TARGET_TABLE):
                    # Check and Add Missing Columns
                    columns_to_check = [
                        ("full_drive_path", "TEXT"),
                        ("drive_uploaded_time", "DATETIME"),
                        ("source", "VARCHAR(50)"),
                        ("area", "VARCHAR(255)"),
                        ("etl_version", "VARCHAR(20)"),
                        ("processed_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                        ("task_id", "VARCHAR(255)"),
                        ("file_hash", "VARCHAR(32)")
                    ]

                    for col_name, col_type in columns_to_check:
                        try:
                            col_check = text(f"""
                                SELECT COUNT(*) FROM information_schema.COLUMNS 
                                WHERE TABLE_SCHEMA = DATABASE() 
                                AND TABLE_NAME = '{TARGET_TABLE}' 
                                AND COLUMN_NAME = '{col_name}'
                            """)
                            if conn.execute(col_check).scalar() == 0:
                                logger.info(f"⚠️ Column `{col_name}` missing. Adding it now...")
                                conn.execute(text(f"ALTER TABLE {TARGET_TABLE} ADD COLUMN {col_name} {col_type}"))
                                logger.info(f"✅ Column `{col_name}` added successfully.")
                        except Exception as e:
                            logger.error(f"❌ Failed to add column `{col_name}`: {e}")

                    # Check and Add Missing Indexes
                    indexes_to_create = [
                        ("idx_city", f"CREATE INDEX idx_city ON {TARGET_TABLE}(city)"),
                        ("idx_state_category", f"CREATE INDEX idx_state_category ON {TARGET_TABLE}(state, category)")
                    ]

                    for name, sql in indexes_to_create:
                        try:
                            check_sql = text(f"""
                                SELECT COUNT(1) IndexIsThere 
                                FROM INFORMATION_SCHEMA.STATISTICS 
                                WHERE table_schema = DATABASE() 
                                AND table_name = '{TARGET_TABLE}' 
                                AND index_name = :idx_name
                            """)
                            if conn.execute(check_sql, {"idx_name": name}).scalar() == 0:
                                conn.execute(text(sql))
                                logger.info(f"✅ Created index: {name}")
                        except Exception as e:
                            logger.error(f"❌ Failed to create index {name}: {e}")
                else:
                    logger.warning(f"⏩ Table `{TARGET_TABLE}` does not exist yet. Skipping column updates.")

                # === ISSUE 5: file_hash Column on file_registry ===
                if table_exists('file_registry'):
                    try:
                        col_check = text("""
                            SELECT COUNT(*) FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'file_registry' AND COLUMN_NAME = 'file_hash'
                        """)
                        if conn.execute(col_check).scalar() == 0:
                            conn.execute(text("ALTER TABLE file_registry ADD COLUMN file_hash VARCHAR(32)"))
                            logger.info("✅ Column `file_hash` added to file_registry.")
                    except Exception as e:
                        logger.error(f"❌ Failed to add `file_hash` to file_registry: {e}")
                else:
                    logger.warning("⏩ Table `file_registry` does not exist yet. Skipping column update.")

                # === ISSUE 3: Dead Letter Queue Table ===
                try:
                    if not table_exists('etl_dlq'):
                        logger.info("⚠️ Table `etl_dlq` missing. Creating it now...")
                        conn.execute(text("""
                            CREATE TABLE etl_dlq (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                file_id VARCHAR(255) NOT NULL,
                                file_name VARCHAR(500),
                                error TEXT,
                                task_id VARCHAR(255),
                                retry_count INT DEFAULT 0,
                                failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                INDEX idx_failed_at (failed_at)
                            )
                        """))
                        logger.info("✅ Table `etl_dlq` created successfully.")
                except Exception as e:
                    logger.error(f"❌ Failed to create `etl_dlq` table: {e}")

                # === ISSUE 6: Validation, Cleaning and Logging Tables ===
                # (These are already wrapped in CREATE TABLE IF NOT EXISTS, so they are safe)
                try:
                    tables_to_create = [
                        ("validation_raw_google_map", """
                            CREATE TABLE IF NOT EXISTS validation_raw_google_map (
                                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                                raw_id BIGINT UNIQUE NOT NULL,
                                name VARCHAR(500), address TEXT, website TEXT, phone_number VARCHAR(100),
                                reviews_count INT DEFAULT 0, reviews_avg FLOAT DEFAULT 0.00,
                                category VARCHAR(255), subcategory VARCHAR(255), city VARCHAR(255), state VARCHAR(255), area VARCHAR(255),
                                created_at DATETIME,
                                validation_status ENUM('PENDING', 'STRUCTURED', 'INVALID', 'UNSTRUCTURED', 'DUPLICATE', 'MISSING', 'VALID') NOT NULL DEFAULT 'PENDING',
                                cleaning_status ENUM('NOT_STARTED', 'CLEANED') NOT NULL DEFAULT 'NOT_STARTED',
                                missing_fields TEXT, invalid_format_fields TEXT, duplicate_reason TEXT, processed_at DATETIME NULL,
                                INDEX idx_validation_status (validation_status), INDEX idx_cleaning_status (cleaning_status)
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                        """),
                        ("raw_clean_google_map_data", """
                            CREATE TABLE IF NOT EXISTS raw_clean_google_map_data (
                                id BIGINT AUTO_INCREMENT PRIMARY KEY, raw_id BIGINT UNIQUE NOT NULL,
                                name VARCHAR(500), address TEXT, website TEXT, phone_number VARCHAR(100),
                                reviews_count INT DEFAULT 0, reviews_avg FLOAT DEFAULT 0.00,
                                category VARCHAR(255), subcategory VARCHAR(255), city VARCHAR(255), state VARCHAR(255), area VARCHAR(255),
                                created_at DATETIME, UNIQUE INDEX idx_composite_dedup (name(100), phone_number, city(50), address(100))
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                        """),
                        ("data_validation_log", """
                            CREATE TABLE IF NOT EXISTS data_validation_log (
                                id INT AUTO_INCREMENT PRIMARY KEY, total_processed INT, missing_count INT,
                                valid_count INT, duplicate_count INT, cleaned_count INT, last_id BIGINT, timestamp DATETIME
                            );
                        """),
                        ("invalid_google_map_data", """
                            CREATE TABLE IF NOT EXISTS invalid_google_map_data (
                                id BIGINT AUTO_INCREMENT PRIMARY KEY, raw_id BIGINT,
                                name VARCHAR(500), address TEXT, website TEXT, phone_number VARCHAR(100), bank_number VARCHAR(100),
                                reviews_count INT DEFAULT 0, reviews_avg FLOAT DEFAULT 0.00,
                                category VARCHAR(255), subcategory VARCHAR(255), city VARCHAR(255), state VARCHAR(255), area VARCHAR(255),
                                validation_label VARCHAR(100), missing_fields TEXT, invalid_format_fields TEXT, error_reason TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                        """),
                        ("g_map_master_table", """
                            CREATE TABLE IF NOT EXISTS g_map_master_table (
                                id BIGINT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(500), address TEXT, website TEXT,
                                phone_number VARCHAR(100), reviews_count INT DEFAULT 0, reviews_avg FLOAT DEFAULT 0.00,
                                category VARCHAR(255), subcategory VARCHAR(255), city VARCHAR(255), state VARCHAR(255), area VARCHAR(255),
                                created_at DATETIME, UNIQUE INDEX idx_unique_business (name(100), phone_number, city(50), address(100))
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                        """)
                    ]
                    for t_name, t_sql in tables_to_create:
                        conn.execute(text(t_sql))
                        logger.info(f"✅ Ensured table `{t_name}` exists.")
                except Exception as e:
                    logger.error(f"❌ Failed to ensure validation tables exist: {e}")

            print("🏁 DB Migrations check complete.")
            
        except Exception as e:
            logger.error(f"❌ Critical Migration Error: {e}")