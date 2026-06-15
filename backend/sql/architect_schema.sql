-- =============================================================================
-- PROD-READY DDL FOR HIGH-THROUGHPUT GOOGLE MAPS ETL SYSTEM
-- AUTHOR: SENIOR DATA ARCHITECT
-- UPDATED: 2026-02-25 (Unified Schema)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- TABLE 1: raw_google_map_drive_data (Ingestion Layer)
-- Purpose: Source of truth. Read-only.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_google_map_drive_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(500),
    address TEXT,
    website TEXT,
    phone_number VARCHAR(100),
    reviews_count INT DEFAULT 0,
    reviews_average FLOAT DEFAULT 0.00,
    category VARCHAR(255),
    subcategory VARCHAR(255),
    city VARCHAR(255),
    state VARCHAR(255),
    area VARCHAR(255),
    
    -- GDrive Metadata
    drive_folder_id VARCHAR(255),
    drive_folder_name VARCHAR(500),
    drive_file_id VARCHAR(255),
    drive_file_name VARCHAR(500),
    full_drive_path TEXT,
    drive_uploaded_time DATETIME,
    
    -- ETL Metadata
    source VARCHAR(50) DEFAULT 'google_drive',
    etl_version VARCHAR(50),
    task_id VARCHAR(255),
    file_hash VARCHAR(255),
    row_signature VARCHAR(32) COMMENT 'MD5 hash of all 11 business columns for exact deduplication',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_row_signature (row_signature),
    INDEX idx_drive_file_id (drive_file_id),
    INDEX idx_name (name(100)),
    INDEX idx_state (state(50)),
    INDEX idx_category (category(50)),
    INDEX idx_city (city(50)),
    INDEX idx_state_category (state(50), category(50))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- TABLE 2: raw_clean_google_map_data
-- Purpose: Store only fully validated + cleaned data
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_clean_google_map_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    raw_id BIGINT UNIQUE NOT NULL COMMENT 'Refers to validation_raw_google_map.raw_id',
    signature_hash VARCHAR(64) NULL,
    
    -- Cleaned Business Columns
    name VARCHAR(500),
    address TEXT,
    website TEXT,
    phone_number VARCHAR(100),
    reviews_count INT DEFAULT 0,
    reviews_avg FLOAT DEFAULT 0.00,
    category VARCHAR(255),
    subcategory VARCHAR(255),
    city VARCHAR(255),
    state VARCHAR(255),
    area VARCHAR(255),

    -- Processing Columns
    validation_status ENUM('PENDING', 'STRUCTURED', 'INVALID', 'UNSTRUCTURED', 'DUPLICATE', 'MISSING', 'VALID') NOT NULL DEFAULT 'PENDING',
    cleaning_status ENUM('NOT_STARTED', 'CLEANED') NOT NULL DEFAULT 'NOT_STARTED',
    missing_fields TEXT,
    invalid_format_fields TEXT,
    duplicate_reason TEXT,
    processed_at DATETIME NULL,
    created_at DATETIME,

    -- INDEXES
    UNIQUE INDEX idx_raw_id (raw_id),
    UNIQUE INDEX idx_composite_dedup (name(100), phone_number, city(50), address(100)),
    INDEX idx_sig_hash (signature_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- SUPPLEMTARY TABLES
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS file_registry (
    drive_file_id VARCHAR(255) PRIMARY KEY,
    filename VARCHAR(500),
    drive_folder_id VARCHAR(255),
    status ENUM('PENDING', 'IN_PROGRESS', 'PROCESSED', 'ERROR') DEFAULT 'PENDING',
    last_processed_row INT DEFAULT 0,
    error_message TEXT,
    file_hash VARCHAR(255),
    processed_at DATETIME
);

CREATE TABLE IF NOT EXISTS drive_folder_registry (
    folder_id VARCHAR(200) PRIMARY KEY,
    folder_name VARCHAR(500),
    drive_modified_at VARCHAR(100),
    csv_count INT DEFAULT 0,
    status ENUM('PENDING', 'SCANNING', 'DONE', 'ERROR') DEFAULT 'PENDING',
    scanned_at DATETIME
);

CREATE TABLE IF NOT EXISTS etl_metadata (
    meta_key VARCHAR(100) PRIMARY KEY,
    meta_value TEXT
);

CREATE TABLE IF NOT EXISTS data_validation_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    total_processed INT,
    missing_count INT,
    valid_count INT,
    duplicate_count INT,
    cleaned_count INT,
    timestamp DATETIME
);

CREATE TABLE IF NOT EXISTS etl_dlq (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id VARCHAR(255),
    file_name VARCHAR(500),
    error TEXT,
    task_id VARCHAR(255),
    retry_count INT,
    failed_at DATETIME
);

-- -----------------------------------------------------------------------------
-- TABLE 4: g_map_master_table (Enterprise Master Storage)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS g_map_master_table (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(500),
    address TEXT,
    website TEXT,
    phone_number VARCHAR(100),
    reviews_count INT DEFAULT 0,
    reviews_avg FLOAT DEFAULT 0.00,
    category VARCHAR(255),
    subcategory VARCHAR(255),
    city VARCHAR(255),
    state VARCHAR(255),
    area VARCHAR(255),
    created_at DATETIME,
    UNIQUE INDEX idx_unique_business (name(100), phone_number, city(50), address(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- TABLE 5: blinkit_mapping (Category Hierarchy)
-- Purpose: Stores Blinkit category tree (L1 parents + L2 subcategories).
--          category_id is PRIMARY KEY — guarantees no duplicate categories.
--          parent_id=0 for root L1 categories.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blinkit_mapping (
    category_id   BIGINT NOT NULL,
    category_name VARCHAR(50)  DEFAULT NULL,
    slug          VARCHAR(50)  DEFAULT NULL,
    parent_id     BIGINT       DEFAULT NULL COMMENT '0 = root L1 category',
    category_level BIGINT      DEFAULT NULL COMMENT '1=parent, 2=subcategory',
    full_category_path VARCHAR(58) DEFAULT NULL COMMENT 'e.g. "Dairy, Bread & Eggs > Milk"',
    PRIMARY KEY (category_id),
    KEY idx_blm_category_name  (category_name),
    KEY idx_blm_category_id    (category_id),
    KEY idx_blm_parent_id      (parent_id),
    KEY idx_blm_category_level (category_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------------------------------
-- TABLE 6: blinkit (Product Catalog)
-- Purpose: Stores all Blinkit products (40,000+).
--          product_id is PRIMARY KEY — guarantees zero product duplicates.
--          category_id FK references blinkit_mapping for proper hierarchy linkage.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blinkit (
    product_id    BIGINT NOT NULL,
    product_name  TEXT,
    brand         VARCHAR(255) DEFAULT NULL,
    category      VARCHAR(255) DEFAULT NULL  COMMENT 'L1 parent category name (text)',
    sub_category  VARCHAR(255) DEFAULT NULL  COMMENT 'L2 subcategory name (text)',
    category_id   BIGINT       DEFAULT NULL  COMMENT 'FK -> blinkit_mapping.category_id (L2)',
    price         DECIMAL(10,2) DEFAULT NULL,
    mrp           DECIMAL(10,2) DEFAULT NULL,
    discount      DECIMAL(10,2) DEFAULT NULL,
    quantity      VARCHAR(100) DEFAULT NULL,
    availability  TINYINT(1)   DEFAULT NULL,
    image_url     TEXT,
    product_url   TEXT,
    PRIMARY KEY (product_id),
    KEY idx_bl_category              (category(100)),
    KEY idx_bl_cat_subcat_composite  (category(100), sub_category(100)),
    KEY fk_blinkit_category          (category_id),
    CONSTRAINT fk_blinkit_category
        FOREIGN KEY (category_id)
        REFERENCES blinkit_mapping (category_id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- End of Schema