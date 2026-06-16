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
                    conn.commit()  # Close the SELECT autobegin transaction
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

                # === FIX: Use the actual ingestion table used by robust_gdrive_etl_v2 ===
                TARGET_TABLE = "raw_google_map_drive_data"

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
                        ("file_hash", "VARCHAR(32)"),
                        ("row_signature", "VARCHAR(32)")
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
                        ("idx_row_signature", f"CREATE UNIQUE INDEX idx_row_signature ON {TARGET_TABLE}(row_signature)"),
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

                # === ISSUE: raw_clean_google_map_data Upgrades === 
                CLEAN_TABLE = "raw_clean_google_map_data"
                if table_exists(CLEAN_TABLE):
                    clean_cols = [
                        ("signature_hash", "VARCHAR(64)"),
                        ("validation_status", "ENUM('PENDING', 'STRUCTURED', 'INVALID', 'UNSTRUCTURED', 'DUPLICATE', 'MISSING', 'VALID') DEFAULT 'PENDING'"),
                        ("cleaning_status", "ENUM('NOT_STARTED', 'CLEANED') DEFAULT 'NOT_STARTED'"),
                        ("missing_fields", "TEXT"),
                        ("invalid_format_fields", "TEXT"),
                        ("duplicate_reason", "TEXT"),
                        ("processed_at", "DATETIME")
                    ]
                    for col_name, col_type in clean_cols:
                        try:
                            # SQL injection safe in this context since it's hardcoded
                            res = conn.execute(text(f"SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{CLEAN_TABLE}' AND COLUMN_NAME = '{col_name}'"))
                            if res.scalar() == 0:
                                logger.info(f"⚠️ Column `{col_name}` missing in {CLEAN_TABLE}. Adding...")
                                conn.execute(text(f"ALTER TABLE {CLEAN_TABLE} ADD COLUMN {col_name} {col_type}"))
                        except Exception as e:
                            logger.error(f"❌ Failed to add `{col_name}` to {CLEAN_TABLE}: {e}")
                    
                    # Add sig_hash index if missing
                    try:
                        idx_check = text(f"SELECT COUNT(1) FROM INFORMATION_SCHEMA.STATISTICS WHERE table_schema = DATABASE() AND table_name = '{CLEAN_TABLE}' AND index_name = 'idx_sig_hash'")
                        if conn.execute(idx_check).scalar() == 0:
                            conn.execute(text(f"CREATE INDEX idx_sig_hash ON {CLEAN_TABLE}(signature_hash)"))
                            logger.info(f"✅ Created index: idx_sig_hash on {CLEAN_TABLE}")
                    except Exception as e:
                        logger.error(f"❌ Failed to create signature_hash index: {e}")
                else:
                    logger.warning(f"⏩ Table `{CLEAN_TABLE}` does not exist yet for migration check.")

                # === ISSUE 5: file_registry Missing Columns ===
                if table_exists('file_registry'):
                    columns_to_add = [
                        ("file_hash", "VARCHAR(32)"),
                        ("drive_folder_id", "VARCHAR(255)")
                    ]
                    for col_name, col_type in columns_to_add:
                        try:
                            col_check = text(f"""
                                SELECT COUNT(*) FROM information_schema.COLUMNS
                                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'file_registry' AND COLUMN_NAME = '{col_name}'
                            """)
                            if conn.execute(col_check).scalar() == 0:
                                conn.execute(text(f"ALTER TABLE file_registry ADD COLUMN {col_name} {col_type}"))
                                logger.info(f"✅ Column `{col_name}` added to file_registry.")
                        except Exception as e:
                            logger.error(f"❌ Failed to add `{col_name}` to file_registry: {e}")
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
                        ("raw_clean_google_map_data", """
                            CREATE TABLE IF NOT EXISTS raw_clean_google_map_data (
                                id BIGINT AUTO_INCREMENT PRIMARY KEY, raw_id BIGINT UNIQUE NOT NULL,
                                signature_hash VARCHAR(64) NULL,
                                name VARCHAR(500), address TEXT, website TEXT, phone_number VARCHAR(100),
                                reviews_count INT DEFAULT 0, reviews_avg FLOAT DEFAULT 0.00,
                                category VARCHAR(255), subcategory VARCHAR(255), city VARCHAR(255), state VARCHAR(255), area VARCHAR(255),
                                validation_status ENUM('PENDING', 'STRUCTURED', 'INVALID', 'UNSTRUCTURED', 'DUPLICATE', 'MISSING', 'VALID') NOT NULL DEFAULT 'PENDING',
                                cleaning_status ENUM('NOT_STARTED', 'CLEANED') NOT NULL DEFAULT 'NOT_STARTED',
                                missing_fields TEXT, invalid_format_fields TEXT, duplicate_reason TEXT, processed_at DATETIME NULL,
                                created_at DATETIME, UNIQUE INDEX idx_composite_dedup (name(100), phone_number, city(50), address(100)),
                                INDEX idx_sig_hash (signature_hash)
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                        """),
                        ("data_validation_log", """
                            CREATE TABLE IF NOT EXISTS data_validation_log (
                                id INT AUTO_INCREMENT PRIMARY KEY, total_processed INT, missing_count INT,
                                valid_count INT, duplicate_count INT, cleaned_count INT, last_id BIGINT, timestamp DATETIME
                            );
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

                # === DMart Category Mapping Table and Foreign Key Upgrade ===
                try:
                    # 1. Ensure dmart_categories exists
                    if not table_exists('dmart_categories'):
                        logger.info("⚠️ Table `dmart_categories` missing in MySQL. Creating now...")
                        conn.execute(text("""
                            CREATE TABLE dmart_categories (
                                category_id INT AUTO_INCREMENT PRIMARY KEY,
                                category_name VARCHAR(255) NOT NULL,
                                slug VARCHAR(255) NULL,
                                parent_id INT NULL,
                                category_level INT NULL,
                                category_path VARCHAR(512) NULL,
                                CONSTRAINT fk_categories_parent FOREIGN KEY (parent_id) 
                                    REFERENCES dmart_categories(category_id) ON DELETE SET NULL
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                        """))
                        logger.info("✅ Table `dmart_categories` created successfully.")
                    else:
                        # Ensure category_path column exists in dmart_categories
                        col_check = text("""
                            SELECT COUNT(*) FROM information_schema.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'dmart_categories' 
                            AND COLUMN_NAME = 'category_path'
                        """)
                        if conn.execute(col_check).scalar() == 0:
                            logger.info("⚠️ Column `category_path` missing in `dmart_categories`. Adding column...")
                            conn.execute(text("ALTER TABLE dmart_categories ADD COLUMN category_path VARCHAR(512) NULL"))
                            logger.info("✅ Column `category_path` successfully added to `dmart_categories`.")
 
                        # Ensure category_id has AUTO_INCREMENT enabled
                        auto_inc_check = text("""
                            SELECT EXTRA FROM information_schema.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'dmart_categories' 
                            AND COLUMN_NAME = 'category_id'
                        """)
                        extra = conn.execute(auto_inc_check).scalar()
                        if not extra or 'auto_increment' not in extra.lower():
                            logger.info("⚠️ Column `category_id` in `dmart_categories` does not have AUTO_INCREMENT. Adding it to align with sequential IDs...")
                            try:
                                conn.execute(text("ALTER TABLE dmart_categories MODIFY COLUMN category_id INT AUTO_INCREMENT"))
                                logger.info("✅ Successfully added AUTO_INCREMENT to `category_id`.")
                            except Exception as alter_err:
                                logger.warning(f"Direct AUTO_INCREMENT addition failed: {alter_err}. Attempting with FK drop...")
                                # Drop constraints
                                try:
                                    conn.execute(text("ALTER TABLE dmart_products DROP FOREIGN KEY fk_dmart_products_category"))
                                except Exception:
                                    try:
                                        conn.execute(text("ALTER TABLE dmart_products DROP FOREIGN KEY dmart_products_ibfk_1"))
                                    except Exception:
                                        pass
                                try:
                                    conn.execute(text("ALTER TABLE dmart_categories DROP FOREIGN KEY fk_categories_parent"))
                                except Exception:
                                    try:
                                        conn.execute(text("ALTER TABLE dmart_categories DROP FOREIGN KEY dmart_categories_ibfk_1"))
                                    except Exception:
                                        pass
                                # Alter column
                                conn.execute(text("ALTER TABLE dmart_categories MODIFY COLUMN category_id INT AUTO_INCREMENT"))
                                # Re-add constraints
                                try:
                                    conn.execute(text("""
                                        ALTER TABLE dmart_categories ADD CONSTRAINT fk_categories_parent 
                                        FOREIGN KEY (parent_id) REFERENCES dmart_categories(category_id) ON DELETE SET NULL
                                    """))
                                except Exception as readd_err:
                                    logger.error(f"Failed to restore dmart_categories parent FK: {readd_err}")
                                try:
                                    conn.execute(text("""
                                        ALTER TABLE dmart_products ADD CONSTRAINT fk_dmart_products_category 
                                        FOREIGN KEY (category_id) REFERENCES dmart_categories(category_id) ON DELETE SET NULL
                                    """))
                                except Exception as readd_err:
                                    logger.error(f"Failed to restore dmart_products category FK: {readd_err}")
                                logger.info("✅ Successfully added AUTO_INCREMENT to `category_id` via FK drop fallback.")

                    # 2. Check and Add category_id to dmart_products
                    if table_exists('dmart_products'):
                        col_check = text("""
                            SELECT COUNT(*) FROM information_schema.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'dmart_products' 
                            AND COLUMN_NAME = 'category_id'
                        """)
                        if conn.execute(col_check).scalar() == 0:
                            logger.info("⚠️ Column `category_id` missing in `dmart_products`. Adding column and Foreign Key constraint...")
                            # Add column
                            conn.execute(text("ALTER TABLE dmart_products ADD COLUMN category_id INT NULL"))
                            # Add Foreign Key Constraint
                            conn.execute(text("""
                                ALTER TABLE dmart_products 
                                ADD CONSTRAINT fk_dmart_products_category 
                                FOREIGN KEY (category_id) REFERENCES dmart_categories(category_id) 
                                ON DELETE SET NULL
                            """))
                            logger.info("✅ Column `category_id` and foreign key constraint successfully migrated on `dmart_products`.")

                        # Ensure ASIN column has a UNIQUE index to prevent duplicates at database level
                        idx_check_asin = text("""
                            SELECT COUNT(1) IndexIsThere 
                            FROM INFORMATION_SCHEMA.STATISTICS 
                            WHERE table_schema = DATABASE() 
                            AND table_name = 'dmart_products' 
                            AND index_name = 'idx_dmart_products_asin'
                        """)
                        if conn.execute(idx_check_asin).scalar() == 0:
                            logger.info("⚠️ Unique index `idx_dmart_products_asin` missing on `dmart_products`. Preparing database constraint...")
                            try:
                                # First, deduplicate existing data (delete older duplicates of the same ASIN, keeping the latest one)
                                logger.info("🧹 Deduplicating existing rows in `dmart_products` based on `ASIN`...")
                                conn.execute(text("""
                                    DELETE p1 FROM dmart_products p1
                                    INNER JOIN dmart_products p2 
                                    ON p1.ASIN = p2.ASIN AND p1.id < p2.id
                                """))
                                logger.info("✅ Table `dmart_products` successfully deduplicated.")
                                
                                # Second, add the UNIQUE index constraint
                                logger.info("🔨 Creating UNIQUE index on `ASIN` column...")
                                conn.execute(text("CREATE UNIQUE INDEX idx_dmart_products_asin ON dmart_products(ASIN)"))
                                logger.info("✅ Unique constraint idx_dmart_products_asin successfully created on `dmart_products`.")
                            except Exception as idx_err:
                                logger.error(f"❌ Failed to create UNIQUE index on ASIN: {idx_err}")

                        # Ensure listPrice column exists in dmart_products
                        col_check_lp = text("""
                            SELECT COUNT(*) FROM information_schema.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'dmart_products' 
                            AND COLUMN_NAME = 'listPrice'
                        """)
                        if conn.execute(col_check_lp).scalar() == 0:
                            logger.info("⚠️ Column `listPrice` missing in `dmart_products`. Adding column...")
                            conn.execute(text("ALTER TABLE dmart_products ADD COLUMN listPrice VARCHAR(100) NULL"))
                            logger.info("✅ Column `listPrice` successfully added to `dmart_products`.")

                        # Ensure quantity column exists in dmart_products
                        col_check_qty = text("""
                            SELECT COUNT(*) FROM information_schema.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'dmart_products' 
                            AND COLUMN_NAME = 'quantity'
                        """)
                        if conn.execute(col_check_qty).scalar() == 0:
                            logger.info("⚠️ Column `quantity` missing in `dmart_products`. Adding column...")
                            conn.execute(text("ALTER TABLE dmart_products ADD COLUMN quantity VARCHAR(100) NULL"))
                            logger.info("✅ Column `quantity` successfully added to `dmart_products`.")

                        # Ensure availability column exists in dmart_products
                        col_check_avail = text("""
                            SELECT COUNT(*) FROM information_schema.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'dmart_products' 
                            AND COLUMN_NAME = 'availability'
                        """)
                        if conn.execute(col_check_avail).scalar() == 0:
                            logger.info("⚠️ Column `availability` missing in `dmart_products`. Adding column...")
                            conn.execute(text("ALTER TABLE dmart_products ADD COLUMN availability INT DEFAULT 1"))
                            logger.info("✅ Column `availability` successfully added to `dmart_products`.")

                        # Ensure scraped_at column exists in dmart_products
                        col_check_sa = text("""
                            SELECT COUNT(*) FROM information_schema.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'dmart_products' 
                            AND COLUMN_NAME = 'scraped_at'
                        """)
                        if conn.execute(col_check_sa).scalar() == 0:
                            logger.info("⚠️ Column `scraped_at` missing in `dmart_products`. Adding column...")
                            conn.execute(text("ALTER TABLE dmart_products ADD COLUMN scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
                            logger.info("✅ Column `scraped_at` successfully added to `dmart_products`.")

                        # Drop redundant rating and description columns if present
                        for old_col in ["rating", "Number_of_ratings", "description"]:
                            col_check_old = text(f"""
                                SELECT COUNT(*) FROM information_schema.COLUMNS 
                                WHERE TABLE_SCHEMA = DATABASE() 
                                AND TABLE_NAME = 'dmart_products' 
                                AND COLUMN_NAME = '{old_col}'
                            """)
                            if conn.execute(col_check_old).scalar() > 0:
                                logger.info(f"⚠️ Column `{old_col}` is redundant in `dmart_products`. Dropping column...")
                                conn.execute(text(f"ALTER TABLE dmart_products DROP COLUMN {old_col}"))
                                logger.info(f"✅ Column `{old_col}` successfully dropped from `dmart_products`.")

                    # 3. MySQL dmart_categories seeding is disabled on boot as per User request.
                    # Instead, categories are dynamically saved and synchronized in real-time.
                    pass

                except Exception as dmart_mig_err:
                    logger.error(f"❌ DMart Category/Product MySQL migration failed: {dmart_mig_err}")

                # === Blinkit Category Mapping Table and Schema Upgrade ===
                try:
                    if table_exists('blinkit_mapping'):
                        # 1. Clean up duplicate categories
                        res = conn.execute(text("SELECT category_id, category_name, parent_id, category_level, full_category_path FROM blinkit_mapping"))
                        rows = res.mappings().fetchall()
                        
                        import re
                        by_name_level = {}
                        for r in rows:
                            if not r["category_name"]:
                                continue
                            norm_name = re.sub(r"\s+", " ", r["category_name"]).strip().lower()
                            level = int(r["category_level"] or 1)
                            key = (norm_name, level)
                            if key not in by_name_level:
                                by_name_level[key] = []
                            by_name_level[key].append(r)
                            
                        dupe_groups = {k: v for k, v in by_name_level.items() if len(v) > 1}
                        if dupe_groups:
                            logger.info(f"🧹 Found {len(dupe_groups)} duplicate groups in blinkit_mapping. Healing duplicates...")
                            id_mapping = {}
                            ids_to_delete = []
                            for (name, level), group in dupe_groups.items():
                                group_sorted = sorted(group, key=lambda x: int(x['category_id']))
                                master = group_sorted[0]
                                master_id = int(master['category_id'])
                                
                                for dupe in group_sorted[1:]:
                                    dupe_id = int(dupe['category_id'])
                                    id_mapping[dupe_id] = master_id
                                    ids_to_delete.append(dupe_id)
                                    
                            # Update child categories parent_id
                            for dupe_id, master_id in id_mapping.items():
                                conn.execute(
                                    text("UPDATE blinkit_mapping SET parent_id = :master_id WHERE parent_id = :dupe_id"),
                                    {"master_id": master_id, "dupe_id": dupe_id}
                                )
                            # Delete duplicate categories
                            for did in ids_to_delete:
                                conn.execute(
                                    text("DELETE FROM blinkit_mapping WHERE category_id = :did"),
                                    {"did": did}
                                )
                            logger.info(f"✅ Deduplicated categories. Deleted {len(ids_to_delete)} duplicate rows.")

                        # 2. Heal remaining orphans (invalid parent_id references)
                        res = conn.execute(text("SELECT category_id, category_name FROM blinkit_mapping WHERE category_level = 1"))
                        l1_cats = res.mappings().fetchall()
                        l1_map = {re.sub(r"\s+", " ", c['category_name']).strip().lower(): int(c['category_id']) for c in l1_cats}
                        l1_variations = {
                            "beauty & personal care": "personal care",
                            "cleaning & household": "cleaning essentials",
                            "pantry staples": "atta, rice & dal",
                            "dairy & breakfast": "dairy, bread & eggs",
                            "ice creams & sweets": "sweet tooth",
                            "paan & hookah": "paan corner",
                            "digital needs": "digital goods",
                            "meat & seafood": "chicken, meat & fish",
                            "vegetables & fruits": "vegetables & fruits",
                        }
                        
                        res = conn.execute(text("SELECT category_id, category_name, parent_id, full_category_path FROM blinkit_mapping WHERE category_level > 1"))
                        children = res.mappings().fetchall()
                        
                        healed_orphans = 0
                        for child in children:
                            child_id = int(child['category_id'])
                            parent_id = int(child['parent_id'] or 0)
                            path = child['full_category_path'] or ""
                            
                            # Check if parent exists
                            p_check = conn.execute(text("SELECT COUNT(*) FROM blinkit_mapping WHERE category_id = :pid"), {"pid": parent_id}).scalar()
                            if p_check == 0:
                                parts = [p.strip() for p in path.split('>') if p.strip()]
                                if len(parts) >= 2:
                                    parent_name = parts[0]
                                    name_lower = re.sub(r"\s+", " ", parent_name).strip().lower()
                                    resolved_parent_id = None
                                    
                                    if name_lower in l1_map:
                                        resolved_parent_id = l1_map[name_lower]
                                    elif name_lower in l1_variations:
                                        var_name = l1_variations[name_lower]
                                        if var_name in l1_map:
                                            resolved_parent_id = l1_map[var_name]
                                            
                                    if resolved_parent_id is not None:
                                        conn.execute(
                                            text("UPDATE blinkit_mapping SET parent_id = :rpid WHERE category_id = :cid"),
                                            {"rpid": resolved_parent_id, "cid": child_id}
                                        )
                                        healed_orphans += 1
                        if healed_orphans > 0:
                            logger.info(f"✅ Healed {healed_orphans} orphaned category mappings.")

                        # 3. Enforce category_id as PRIMARY KEY in blinkit_mapping
                        pk_check = conn.execute(text("""
                            SELECT COUNT(*) 
                            FROM information_schema.TABLE_CONSTRAINTS 
                            WHERE CONSTRAINT_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'blinkit_mapping' 
                            AND CONSTRAINT_TYPE = 'PRIMARY KEY'
                        """)).scalar()
                        if pk_check == 0:
                            logger.info("⚠️ Enforcing `category_id` as PRIMARY KEY on `blinkit_mapping`...")
                            conn.execute(text("ALTER TABLE blinkit_mapping MODIFY COLUMN category_id BIGINT NOT NULL"))
                            conn.execute(text("ALTER TABLE blinkit_mapping ADD PRIMARY KEY (category_id)"))
                            logger.info("✅ `category_id` successfully set as PRIMARY KEY on `blinkit_mapping`.")

                    # 4. Check and add category_id to blinkit table
                    if table_exists('blinkit'):
                        col_check = conn.execute(text("""
                            SELECT COUNT(*) FROM information_schema.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'blinkit' 
                            AND COLUMN_NAME = 'category_id'
                        """)).scalar()
                        if col_check == 0:
                            logger.info("⚠️ Column `category_id` missing in `blinkit` table. Adding column and Foreign Key constraint...")
                            conn.execute(text("ALTER TABLE blinkit ADD COLUMN category_id BIGINT NULL"))
                            
                            # Add Foreign Key referencing blinkit_mapping
                            if table_exists('blinkit_mapping'):
                                conn.execute(text("""
                                    ALTER TABLE blinkit 
                                    ADD CONSTRAINT fk_blinkit_category 
                                    FOREIGN KEY (category_id) REFERENCES blinkit_mapping(category_id) 
                                    ON DELETE SET NULL
                                """))
                            logger.info("✅ Column `category_id` and foreign key constraint successfully migrated on `blinkit`.")

                        # 5. Populate category_id on existing products where category_id is NULL
                        null_check = conn.execute(text("SELECT COUNT(*) FROM blinkit WHERE category_id IS NULL")).scalar()
                        if null_check > 0:
                            logger.info(f"🧹 Backfilling `category_id` for {null_check} products in `blinkit` table...")
                            
                            # Try to match sub_category name first
                            conn.execute(text("""
                                UPDATE blinkit b
                                JOIN blinkit_mapping bm ON LOWER(TRIM(bm.category_name)) = LOWER(TRIM(b.sub_category))
                                SET b.category_id = bm.category_id
                                WHERE b.category_id IS NULL
                            """))
                            
                            # Fallback to category name
                            conn.execute(text("""
                                UPDATE blinkit b
                                JOIN blinkit_mapping bm ON LOWER(TRIM(bm.category_name)) = LOWER(TRIM(b.category))
                                SET b.category_id = bm.category_id
                                WHERE b.category_id IS NULL
                            """))
                            
                            updated_null_check = conn.execute(text("SELECT COUNT(*) FROM blinkit WHERE category_id IS NULL")).scalar()
                            logger.info(f"✅ Backfill complete. Remaining unmapped products: {updated_null_check}")

                except Exception as blinkit_mig_err:
                    logger.error(f"❌ Blinkit Category/Product MySQL migration failed: {blinkit_mig_err}")

            print("[Migrations] DB Migrations check complete.")
            
        except Exception as e:
            logger.error(f"❌ Critical Migration Error: {e}")