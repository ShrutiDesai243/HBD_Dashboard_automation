import re
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env') 

DB_USER = os.getenv('DB_USER')
DB_PASS = getattr(config, "DB_PASSWORD", "")
# DB_PASS = quote_plus(os.getenv('DB_PASSWORD_PLAIN') or '')  # REFACTORED: Now using config.py
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
engine = create_engine(config.DATABASE_URI)

# --- NORMALIZATION SETTINGS --- #

INDIAN_STATES = [
    # 28 States
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", 
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", 
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", 
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", 
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", 
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    # 8 Union Territories
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
    # Common Aliases
    "Pondicherry"
]

def normalize_city_state(city, state):
    """Detects if city ends with a state name and normalizes it."""
    city_str = str(city or "").strip()
    state_str = str(state or "").strip()
    
    if state_str.lower() == 'unknown' and city_str:
        for s in INDIAN_STATES:
            if city_str.endswith(f" {s}"):
                return city_str[:-len(s)].strip(), s
    return city, state

# ---------------- VALIDATORS ---------------- #

def is_placeholder(val):
    if not val: return True
    placeholders = ['n/a', 'none', 'null', 'placeholder', 'unknown']
    return str(val).lower().strip() in placeholders

def check_mandatory(row):
    required = ["name", "address", "category", "city", "state", "phone_number"]
    missing = [f for f in required if not row.get(f) or str(row.get(f)).strip() == "" or is_placeholder(row.get(f))]
    return missing

def validate_formats(row):
    invalid_fields = []
    
    # Phone: 10-15 digits after normalization (strips 0/91)
    phone = normalize_phone(row.get('phone_number', ''))
    if not (10 <= len(phone) <= 15):
        invalid_fields.append("phone_number")
        
    # Address: Must NOT be purely numerical (e.g., "12345678" is junk)
    address = str(row.get('address', '')).strip()
    if address and address.isdigit():
        invalid_fields.append("address")

    # Website: Force https (if present)
    website = str(row.get('website', '')).lower().strip()
    if website and not (website.startswith('http://') or website.startswith('https://')):
        # We can clean this later, but for now mark as invalid if it's garbage
        if '.' not in website:
            invalid_fields.append("website")
            
    # Reviews Avg: 0-5
    try:
        avg = float(row.get('reviews_avg', 0) or 0)
        if not (0 <= avg <= 5):
            invalid_fields.append("reviews_avg")
    except:
        invalid_fields.append("reviews_avg")
        
    return invalid_fields

# ---------------- CORE PIPELINE ---------------- #

def run_ingestion():
    """Phase 1: Raw → Validation (INSERT ONLY)"""
    query = text("""
    INSERT INTO validation_raw_google_map (
        raw_id, name, address, website, phone_number, reviews_count, reviews_avg, 
        category, subcategory, city, state, area, created_at
    )
    SELECT 
        r.id, r.name, r.address, r.website, r.phone_number, r.reviews_count, r.reviews_avg, 
        r.category, r.subcategory, r.city, r.state, r.area, r.created_at
    FROM raw_google_map_drive_data r
    LEFT JOIN validation_raw_google_map v ON r.id = v.raw_id
    WHERE v.raw_id IS NULL;
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("✅ Ingestion Phase Complete.")

def run_validation():
    """Phase 2: Validation Engine"""
    # Fetch PENDING rows
    df = pd.read_sql("SELECT * FROM validation_raw_google_map WHERE validation_status = 'PENDING' LIMIT 5000", engine)

    if df.empty:
        print("ℹ️ No pending data to validate.")
        return

    for index, row in df.iterrows():
        validation_status = "STRUCTURED"
        missing_fields = []
        invalid_format_fields = []
        duplicate_reason = None
        
        # 1. Normalize City/State immediately (Moves state name from city if found)
        # This ensures validation and deduplication work on correct data
        clean_city, clean_state = normalize_city_state(row['city'], row['state'])
        
        # 2. Mandatory Fields
        # We use the normalized values for checking
        validation_row = row.copy()
        validation_row['city'] = clean_city
        validation_row['state'] = clean_state
        
        missing = check_mandatory(validation_row)
        if missing:
            validation_status = "UNSTRUCTURED"
            missing_fields = missing
        
        # 3. Format Validation (Blocks numerical addresses, etc.)
        if validation_status == "STRUCTURED":
            invalid = validate_formats(validation_row)
            if invalid:
                validation_status = "INVALID"
                invalid_format_fields = invalid
        
        # 4. Duplicate Detection (check against master/clean table)
        if validation_status == "STRUCTURED":
            # Check against the composite index: name + phone_number + city + address
            check_query = text("""
                SELECT id FROM raw_clean_google_map_data 
                WHERE name = :name 
                  AND phone_number = :phone 
                  AND city = :city 
                  AND address = :address 
                LIMIT 1
            """)
            with engine.connect() as conn:
                dup = conn.execute(check_query, {
                    "name": validation_row['name'], 
                    "address": validation_row['address'], 
                    "phone": validation_row['phone_number'],
                    "city": validation_row['city']
                }).fetchone()
                if dup:
                    validation_status = "DUPLICATE"
                    duplicate_reason = "Composite match in clean data"

        # Update the validation record with FIXED city/state and status
        update_query = text("""
            UPDATE validation_raw_google_map 
            SET city = :city,
                state = :state,
                validation_status = :status,
                missing_fields = :missing,
                invalid_format_fields = :invalid,
                duplicate_reason = :dup_reason,
                processed_at = NOW()
            WHERE id = :id
        """)
        with engine.begin() as conn:
            conn.execute(update_query, {
                "city": validation_row['city'],
                "state": validation_row['state'],
                "status": validation_status,
                "missing": ",".join(missing_fields) if missing_fields else None,
                "invalid": ",".join(invalid_format_fields) if invalid_format_fields else None,
                "dup_reason": duplicate_reason,
                "id": row['id']
            })

    print(f"✅ Validation Phase Complete for {len(df)} rows.")

def run_cleaning():
    """Phase 3: Cleaning Engine"""
    df = pd.read_sql("""
        SELECT * FROM validation_raw_google_map 
        WHERE validation_status = 'STRUCTURED' AND cleaning_status = 'NOT_STARTED' 
        LIMIT 5000
    """, engine)
    
    if df.empty:
        print("ℹ️ No data to clean.")
        return
        
    for index, row in df.iterrows():
        # Clean data in memory
        # Note: City and State were already normalized during the validation phase
        clean_row = {
            "raw_id": row['raw_id'],
            "name": str(row['name']).strip(),
            "address": str(row['address']).strip(),
            "website": str(row['website']).lower().strip() if row['website'] else None,
            "phone_number": normalize_phone(row['phone_number']),
            "reviews_count": row['reviews_count'],
            "reviews_avg": row['reviews_avg'],
            "category": row['category'],
            "subcategory": row['subcategory'],
            "city": row['city'],
            "state": row['state'],
            "area": row['area'],
            "created_at": row['created_at'],
            "cleaning_status": "CLEANED"
        }
        
        # Force https on website if missing
        if clean_row['website'] and not (clean_row['website'].startswith('http://') or clean_row['website'].startswith('https://')):
            clean_row['website'] = 'https://' + clean_row['website']

        # Insert into clean table
        insert_query = text("""
            INSERT IGNORE INTO raw_clean_google_map_data (
                raw_id, name, address, website, phone_number, reviews_count, reviews_avg,
                category, subcategory, city, state, area, created_at, cleaning_status
            ) VALUES (
                :raw_id, :name, :address, :website, :phone_number, :reviews_count, :reviews_avg,
                :category, :subcategory, :city, :state, :area, :created_at, :cleaning_status
            )
        """)
        
        with engine.begin() as conn:
            conn.execute(insert_query, clean_row)
            
            # Update cleaning status in validation table
            conn.execute(text("UPDATE validation_raw_google_map SET cleaning_status = 'CLEANED' WHERE id = :id"), {"id": row['id']})
            
    print(f"✅ Cleaning Phase Complete for {len(df)} rows.")

def run_full_pipeline():
    print("🚀 Starting ETL Pipeline...")
    run_ingestion()
    run_validation()
    run_cleaning()
    print("⭐ ETL Pipeline Cycle Finished.")

if __name__ == "__main__":
    run_full_pipeline()
