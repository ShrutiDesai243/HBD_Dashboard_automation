import os
import re
import json
import logging
import threading
from datetime import datetime
from sqlalchemy import bindparam, text
from extensions import db
from model.data_cleaning_log import DataCleaningLog
from model.duplicate_records_review import DuplicateRecordsReview
from model.unmatched_data_review import UnmatchedDataReview

logger = logging.getLogger("DataCleaningService")

# Global dict to track active running tasks
active_tasks = {}

# Common spelling mistakes map for Indian cities/states
COMMON_SPELLING_MAP = {
    "banglore": "Bangalore",
    "bengaluru": "Bangalore",
    "calcutta": "Kolkata",
    "bombay": "Mumbai",
    "delhi ncr": "Delhi",
    "madras": "Chennai",
    "poona": "Pune",
    "banaras": "Varanasi",
    "gurgaon": "Gurugram",
    "orissa": "Odisha",
    "pondicherry": "Puducherry",
    "trivandrum": "Thiruvananthapuram",
    "cochin": "Kochi",
    "secunderabad": "Hyderabad",
    "gauhati": "Guwahati",
    "vizag": "Visakhapatnam",
    "waltair": "Visakhapatnam",
    "baroda": "Vadodara"
}

def load_location_master():
    """Load states, cities, and areas from Location_Master_India into memory sets for fast O(1) matching"""
    try:
        # States
        states_res = db.session.execute(text("SELECT DISTINCT state_full_name, state_short_code FROM Location_Master_India")).fetchall()
        states = set()
        state_map = {} # maps lower to exact casing
        for r in states_res:
            if r[0]:
                states.add(r[0].lower())
                state_map[r[0].lower()] = r[0]
            if r[1]:
                states.add(r[1].lower())
                state_map[r[1].lower()] = r[1]
                
        # Cities
        cities_res = db.session.execute(text("SELECT DISTINCT city_name FROM Location_Master_India")).fetchall()
        cities = set()
        city_map = {}
        for r in cities_res:
            if r[0]:
                cities.add(r[0].lower())
                city_map[r[0].lower()] = r[0]

        # Areas by City mapping
        areas_res = db.session.execute(text("SELECT DISTINCT LOWER(area_name), LOWER(city_name), area_name FROM Location_Master_India WHERE area_name IS NOT NULL")).fetchall()
        areas_by_city = {}
        area_map = {}
        for area_lower, city_lower, area_exact in areas_res:
            if city_lower not in areas_by_city:
                areas_by_city[city_lower] = set()
            areas_by_city[city_lower].add(area_lower)
            area_map[area_lower] = area_exact

        return states, cities, areas_by_city, state_map, city_map, area_map
    except Exception as e:
        logger.error(f"Error loading location master: {e}")
        return set(), set(), {}, {}, {}, {}

def load_product_category_master():
    """Load product categories from product_category_master for fast O(1) matching"""
    try:
        cat_res = db.session.execute(text("SELECT DISTINCT LOWER(category_name), category_name FROM product_category_master")).fetchall()
        categories = set(r[0] for r in cat_res)
        cat_map = {r[0]: r[1] for r in cat_res}
        return categories, cat_map
    except Exception as e:
        logger.error(f"Error loading product category master: {e}")
        return set(), {}

def validate_phone(phone):
    """Simple validator for Indian phone numbers (10 digits, optional 0 / +91 / 91 prefix)"""
    if not phone:
        return False
    # Remove standard spaces, dashes, parentheses
    clean = re.sub(r'[\s\-\(\)\+]', '', str(phone))
    # Check if all digits and length is reasonable (10 to 12 digits)
    if not clean.isdigit():
        return False
    # Standard Indian mobile regex
    if len(clean) == 10 and clean[0] in '6789':
        return True
    if len(clean) == 11 and clean.startswith('0') and clean[1] in '6789':
        return True
    if len(clean) == 12 and clean.startswith('91') and clean[2] in '6789':
        return True
    # General landline / fallback check (must have 10-12 digits)
    if 8 <= len(clean) <= 12:
        return True
    return False

def validate_email(email):
    """Email validation helper using standard regex"""
    if not email:
        return False
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_regex, str(email).strip()))

def extract_pincode_from_address(address):
    """Regex helper to extract a 6-digit pin code from address string"""
    if not address:
        return None
    match = re.search(r'\b\d{6}\b', str(address))
    return match.group(0) if match else None

def delete_rows_by_ids(table_name, ids):
    """Delete rows using SQLAlchemy's expanding bind parameters."""
    ids = [row_id for row_id in ids if row_id is not None]
    if not ids:
        return
    stmt = text(f"DELETE FROM {table_name} WHERE id IN :ids").bindparams(bindparam("ids", expanding=True))
    db.session.execute(stmt, {"ids": ids})

def reconcile_review_records_present_in_active_tables():
    """
    Pending review rows should represent records removed from active tables.
    Rollbacks restore active rows, so those review records must stop appearing as pending.
    """
    db.session.execute(text("""
        UPDATE unmatched_data_review u
        INNER JOIN master_table m ON u.row_id = m.id
        SET u.correction_status = 'corrected'
        WHERE u.correction_status = 'pending'
          AND u.table_name = 'master_table'
          AND u.row_id IS NOT NULL
    """))
    db.session.execute(text("""
        UPDATE unmatched_data_review u
        INNER JOIN product_master p ON u.row_id = p.id
        SET u.correction_status = 'corrected'
        WHERE u.correction_status = 'pending'
          AND u.table_name = 'product_master'
          AND u.row_id IS NOT NULL
    """))

def get_table_counts_and_metrics():
    """Fast database analyzer queries for both master_table and product_master"""
    metrics = {
        "master_table": {
            "total_rows": 0,
            "duplicate_rows": 0,
            "missing_location": 0,
            "invalid_phone_email": 0,
            "unmatched_location": 0,
            "incomplete_records": 0
        },
        "product_master": {
            "total_rows": 0,
            "duplicate_rows": 0,
            "wrong_category": 0,
            "incomplete_records": 0
        }
    }
    
    try:
        # --- master_table ---
        metrics["master_table"]["total_rows"] = db.session.execute(text("SELECT COUNT(*) FROM master_table")).fetchone()[0]
        
        # Duplicates (SUM(cnt-1) of duplicate keys business_name, primary_phone, address)
        dupe_q = text("""
            SELECT SUM(cnt - 1) FROM (
                SELECT COUNT(*) as cnt 
                FROM master_table 
                WHERE business_name IS NOT NULL AND primary_phone IS NOT NULL AND address IS NOT NULL
                GROUP BY business_name, primary_phone, address
                HAVING cnt > 1
            ) t
        """)
        dupe_res = db.session.execute(dupe_q).fetchone()[0]
        metrics["master_table"]["duplicate_rows"] = int(dupe_res) if dupe_res else 0
        
        # Missing City/State/Area
        missing_q = text("SELECT COUNT(*) FROM master_table WHERE city IS NULL OR city = '' OR state IS NULL OR state = '' OR area IS NULL OR area = ''")
        metrics["master_table"]["missing_location"] = db.session.execute(missing_q).fetchone()[0]
        
        # Invalid Phone/Email (Uses regex check in SQL if possible, otherwise simple check)
        invalid_q = text("""
            SELECT COUNT(*) FROM master_table 
            WHERE (primary_phone IS NOT NULL AND primary_phone != '' AND NOT (primary_phone REGEXP '^[0-9+ -]{8,20}$'))
               OR (email IS NOT NULL AND email != '' AND NOT (email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'))
        """)
        metrics["master_table"]["invalid_phone_email"] = db.session.execute(invalid_q).fetchone()[0]
        
        # Unmatched City/State/Area
        # State not in location master
        unmatched_loc_q = text("""
            SELECT COUNT(*) FROM master_table 
            WHERE (state IS NOT NULL AND state != '' AND state NOT IN (SELECT DISTINCT state_full_name FROM Location_Master_India) AND state NOT IN (SELECT DISTINCT state_short_code FROM Location_Master_India))
               OR (city IS NOT NULL AND city != '' AND city NOT IN (SELECT DISTINCT city_name FROM Location_Master_India))
               OR (area IS NOT NULL AND area != '' AND area NOT IN (SELECT DISTINCT area_name FROM Location_Master_India))
        """)
        metrics["master_table"]["unmatched_location"] = db.session.execute(unmatched_loc_q).fetchone()[0]

        # Incomplete Records
        incomplete_m_q = text("""
            SELECT COUNT(*) FROM master_table 
            WHERE business_name IS NULL OR business_name = '' 
               OR primary_phone IS NULL OR primary_phone = '' 
               OR city IS NULL OR city = '' 
               OR address IS NULL OR address = '' 
               OR (primary_phone IS NOT NULL AND primary_phone != '' AND NOT (primary_phone REGEXP '^[0-9+ -]{8,20}$'))
        """)
        metrics["master_table"]["incomplete_records"] = db.session.execute(incomplete_m_q).fetchone()[0]
        
        # --- product_master ---
        metrics["product_master"]["total_rows"] = db.session.execute(text("SELECT COUNT(*) FROM product_master")).fetchone()[0]
        
        # Product duplicates based on ASIN + marketplace (or product_name + brand if ASIN is null)
        asin_dupes_q = text("""
            SELECT SUM(cnt - 1) FROM (
                SELECT COUNT(*) as cnt 
                FROM product_master 
                WHERE asin IS NOT NULL AND asin != ''
                GROUP BY marketplace_name, asin
                HAVING cnt > 1
            ) t
        """)
        asin_dupes = db.session.execute(asin_dupes_q).fetchone()[0]
        
        name_dupes_q = text("""
            SELECT SUM(cnt - 1) FROM (
                SELECT COUNT(*) as cnt 
                FROM product_master 
                WHERE (asin IS NULL OR asin = '') AND product_name IS NOT NULL
                GROUP BY marketplace_name, LEFT(product_name, 200), brand
                HAVING cnt > 1
            ) t
        """)
        name_dupes = db.session.execute(name_dupes_q).fetchone()[0]
        metrics["product_master"]["duplicate_rows"] = (int(asin_dupes) if asin_dupes else 0) + (int(name_dupes) if name_dupes else 0)
        
        # Wrong Category Mapping
        wrong_cat_q = text("""
            SELECT COUNT(*) FROM product_master 
            WHERE category_name IS NOT NULL AND category_name != '' 
              AND category_name COLLATE utf8mb4_general_ci NOT IN (SELECT DISTINCT category_name COLLATE utf8mb4_general_ci FROM product_category_master)
        """)
        metrics["product_master"]["wrong_category"] = db.session.execute(wrong_cat_q).fetchone()[0]

        # Incomplete Records
        incomplete_p_q = text("""
            SELECT COUNT(*) FROM product_master 
            WHERE product_name IS NULL OR product_name = '' 
               OR marketplace_name IS NULL OR marketplace_name = '' 
               OR category_name IS NULL OR category_name = ''
        """)
        metrics["product_master"]["incomplete_records"] = db.session.execute(incomplete_p_q).fetchone()[0]
        
    except Exception as e:
        logger.error(f"Error executing analysis queries: {e}")
        
    return metrics

def run_cleaning_async(run_id, table_name, run_type, app_context):
    """Asynchronous runner to execute cleaning dry-run or apply in batches inside a background thread"""
    with app_context:
        log_entry = DataCleaningLog.query.filter_by(run_id=run_id).first()
        if not log_entry:
            logger.error(f"Log entry not found for run_id: {run_id}")
            return

        backup_table_master = None
        backup_table_product = None
            
        try:
            logger.info(f"Starting async data cleaning run_id={run_id}, table={table_name}, type={run_type}")
            
            # 1. Load context data
            states_set, cities_set, areas_by_city, state_map, city_map, area_map = load_location_master()
            categories_set, cat_map = load_product_category_master()
            
            # Suffix for backup tables
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_table_master = f"master_table_backup_{date_str}"
            backup_table_product = f"product_master_backup_{date_str}"
            
            # 2. Database Backup (ONLY for apply run_type)
            if run_type == 'apply':
                db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                if table_name in ('master_table', 'all'):
                    db.session.execute(text(f"CREATE TABLE {backup_table_master} LIKE master_table"))
                    db.session.execute(text(f"INSERT INTO {backup_table_master} SELECT * FROM master_table"))
                    log_entry.backup_table_name = backup_table_master
                    logger.info(f"Backup created: {backup_table_master}")
                if table_name in ('product_master', 'all'):
                    db.session.execute(text(f"CREATE TABLE {backup_table_product} LIKE product_master"))
                    db.session.execute(text(f"INSERT INTO {backup_table_product} SELECT * FROM product_master"))
                    if log_entry.backup_table_name:
                        log_entry.backup_table_name += f", {backup_table_product}"
                    else:
                        log_entry.backup_table_name = backup_table_product
                    logger.info(f"Backup created: {backup_table_product}")
                db.session.commit()
            
            # Initial metrics before starting
            initial_metrics = get_table_counts_and_metrics()
            
            total_rows = 0
            duplicate_count = 0
            missing_count = 0
            invalid_phone_email_count = 0
            unmatched_count = 0
            wrong_cat_count = 0
            cleaned_count = 0
            incomplete_master_count = 0
            incomplete_product_count = 0
            
            batch_size = 5000
            
            # 3. Clean master_table
            if table_name in ('master_table', 'all'):
                logger.info("Cleaning master_table...")
                total_m_rows = initial_metrics["master_table"]["total_rows"]
                log_entry.total_rows += total_m_rows
                
                last_id = 0
                processed_duplicates = set() # duplicate keys already seen
                
                while True:
                    rows_res = db.session.execute(
                        text("""
                            SELECT id, business_name, primary_phone, secondary_phone, other_phones, email, address, city, state, area, pincode
                            FROM master_table
                            WHERE id > :last_id
                            ORDER BY id
                            LIMIT :limit
                        """),
                        {"limit": batch_size, "last_id": last_id}
                    ).fetchall()
                    
                    if not rows_res:
                        break
                        
                    last_id = rows_res[-1][0]
                    logger.info(f"Processing master_table batch last_id={last_id} limit={batch_size}")
                    
                    # Store update modifications
                    batch_updates = []
                    batch_duplicates = []
                    batch_unmatched = []
                    batch_incomplete_master_ids = []
                    
                    for row in rows_res:
                        row_id = row[0]
                        b_name = row[1]
                        phone = row[2]
                        sec_phone = row[3]
                        oth_phone = row[4]
                        email = row[5]
                        address = row[6]
                        city = row[7]
                        state = row[8]
                        area = row[9]
                        pincode = row[10]
                        
                        # Apply trimming and convert empty to None
                        b_name_clean = b_name.strip() if b_name else None
                        phone_clean = phone.strip() if phone else None
                        sec_phone_clean = sec_phone.strip() if sec_phone else None
                        oth_phone_clean = oth_phone.strip() if oth_phone else None
                        email_clean = email.strip() if email else None
                        address_clean = address.strip() if address else None
                        city_clean = city.strip() if city else None
                        state_clean = state.strip() if state else None
                        area_clean = area.strip() if area else None
                        pincode_clean = pincode.strip() if pincode else None
                        
                        if b_name_clean == '': b_name_clean = None
                        if phone_clean == '': phone_clean = None
                        if sec_phone_clean == '': sec_phone_clean = None
                        if oth_phone_clean == '': oth_phone_clean = None
                        if email_clean == '': email_clean = None
                        if address_clean == '': address_clean = None
                        if city_clean == '': city_clean = None
                        if state_clean == '': state_clean = None
                        if area_clean == '': area_clean = None
                        if pincode_clean == '': pincode_clean = None

                        # Validate Phone and Email
                        is_phone_valid = validate_phone(phone_clean) if phone_clean else True
                        is_email_valid = validate_email(email_clean) if email_clean else True
                        
                        if not is_phone_valid or not is_email_valid:
                            invalid_phone_email_count += 1
                            # Nullify invalid fields safely
                            if not is_phone_valid: phone_clean = None
                            if not is_email_valid: email_clean = None
                        
                        # Extract pincode from address if empty
                        if not pincode_clean and address_clean:
                            extracted_pin = extract_pincode_from_address(address_clean)
                            if extracted_pin:
                                pincode_clean = extracted_pin
                                cleaned_count += 1 # increment count of changes

                        # Check if record is incomplete (missing crucial details)
                        is_incomplete = False
                        if not b_name_clean or not phone_clean or not city_clean or not address_clean:
                            is_incomplete = True
                        if phone_clean and not is_phone_valid:
                            is_incomplete = True
                        
                        if is_incomplete:
                            incomplete_master_count += 1
                            batch_incomplete_master_ids.append(row_id)
                            continue

                        # Check for Duplication key: normalized (business_name + phone + address)
                        dupe_key = f"{b_name_clean or ''}_{phone_clean or ''}_{address_clean or ''}".lower().replace(' ', '')
                        if dupe_key in processed_duplicates and (b_name_clean or phone_clean or address_clean):
                            duplicate_count += 1
                            row_dict = {
                                "id": row_id, "business_name": b_name_clean, "primary_phone": phone_clean, 
                                "secondary_phone": sec_phone_clean, "other_phones": oth_phone_clean, "email": email_clean,
                                "address": address_clean, "city": city_clean, "state": state_clean, 
                                "area": area_clean, "pincode": pincode_clean
                            }
                            batch_duplicates.append((row_id, dupe_key, row_dict))
                            continue
                        else:
                            processed_duplicates.add(dupe_key)

                        # Missing city/state/area check
                        if not city_clean or not state_clean or not area_clean:
                            missing_count += 1

                        # Casing and spelling standardizations using Location_Master_India
                        is_loc_unmatched = False
                        unmatched_val = None
                        unmatched_type = None

                        # State matching
                        if state_clean:
                            state_lower = state_clean.lower()
                            if state_lower in COMMON_SPELLING_MAP:
                                state_clean = COMMON_SPELLING_MAP[state_lower]
                                state_lower = state_clean.lower()
                                cleaned_count += 1
                            
                            if state_lower in states_set:
                                state_clean = state_map.get(state_lower, state_clean)
                            else:
                                is_loc_unmatched = True
                                unmatched_val = state_clean
                                unmatched_type = 'state'
                                
                        # City matching
                        if city_clean and not is_loc_unmatched:
                            city_lower = city_clean.lower()
                            if city_lower in COMMON_SPELLING_MAP:
                                city_clean = COMMON_SPELLING_MAP[city_lower]
                                city_lower = city_clean.lower()
                                cleaned_count += 1
                                
                            if city_lower in cities_set:
                                city_clean = city_map.get(city_lower, city_clean)
                            else:
                                is_loc_unmatched = True
                                unmatched_val = city_clean
                                unmatched_type = 'city'

                        # Area matching within the city context
                        if area_clean and city_clean and not is_loc_unmatched:
                            area_lower = area_clean.lower()
                            city_lower = city_clean.lower()
                            city_areas = areas_by_city.get(city_lower, set())
                            
                            if area_lower in city_areas:
                                area_clean = area_map.get(area_lower, area_clean)
                            else:
                                is_loc_unmatched = True
                                unmatched_val = area_clean
                                unmatched_type = 'area'

                        if is_loc_unmatched:
                            unmatched_count += 1
                            row_dict = {
                                "id": row_id, "business_name": b_name_clean, "primary_phone": phone_clean, 
                                "secondary_phone": sec_phone_clean, "other_phones": oth_phone_clean, "email": email_clean,
                                "address": address_clean, "city": city_clean, "state": state_clean, 
                                "area": area_clean, "pincode": pincode_clean
                            }
                            batch_unmatched.append((row_id, unmatched_type, unmatched_val, row_dict))
                            continue

                        # Check if fields were updated/cleaned
                        if (b_name_clean != b_name or phone_clean != phone or sec_phone_clean != sec_phone or 
                            oth_phone_clean != oth_phone or email_clean != email or address_clean != address or 
                            city_clean != city or state_clean != state or area_clean != area or pincode_clean != pincode):
                            cleaned_count += 1
                            batch_updates.append({
                                "id": row_id, "business_name": b_name_clean, "primary_phone": phone_clean,
                                "secondary_phone": sec_phone_clean, "other_phones": oth_phone_clean, "email": email_clean,
                                "address": address_clean, "city": city_clean, "state": state_clean, 
                                "area": area_clean, "pincode": pincode_clean
                            })

                    # Perform Apply modifications to DB
                    if run_type == 'apply':
                        # 1. Bulk insert duplicates and delete duplicate rows
                        if batch_duplicates:
                            dupe_params = []
                            dupe_ids = []
                            for dupe_id, key, r_data in batch_duplicates:
                                dupe_ids.append(dupe_id)
                                dupe_params.append({
                                    "table_name": "master_table",
                                    "duplicate_key": key,
                                    "original_id": 0,
                                    "duplicate_id": dupe_id,
                                    "record_data": json.dumps(r_data)
                                })
                            
                            # Bulk insert
                            db.session.execute(
                                text("""
                                    INSERT IGNORE INTO duplicate_records_review
                                        (table_name, duplicate_key, original_id, duplicate_id, record_data)
                                    VALUES (:table_name, :duplicate_key, :original_id, :duplicate_id, :record_data)
                                """),
                                dupe_params
                            )
                            
                            # Bulk delete
                            delete_rows_by_ids("master_table", dupe_ids)

                        # 2. Bulk insert unmatched and delete unmatched rows
                        if batch_unmatched:
                            unmatched_params = []
                            unmatched_ids = []
                            for un_id, u_type, u_val, r_data in batch_unmatched:
                                unmatched_ids.append(un_id)
                                unmatched_params.append({
                                    "data_type": u_type,
                                    "invalid_value": u_val,
                                    "correction_status": "pending",
                                    "table_name": "master_table",
                                    "row_id": un_id,
                                    "row_data": json.dumps(r_data)
                                })
                            
                            # Bulk insert
                            db.session.execute(
                                text("""
                                    INSERT IGNORE INTO unmatched_data_review
                                        (data_type, invalid_value, correction_status, table_name, row_id, row_data)
                                    VALUES (:data_type, :invalid_value, :correction_status, :table_name, :row_id, :row_data)
                                """),
                                unmatched_params
                            )
                            
                            # Bulk delete
                            delete_rows_by_ids("master_table", unmatched_ids)

                        # 3. Bulk insert incomplete records to uncleaned table and delete from master_table
                        if batch_incomplete_master_ids:
                            res_m = db.session.execute(text("SHOW COLUMNS FROM master_table")).fetchall()
                            res_u = db.session.execute(text("SHOW COLUMNS FROM uncleaned_listing_master_table")).fetchall()
                            m_cols = {r[0].lower(): r[0] for r in res_m}
                            u_cols = {r[0].lower(): r[0] for r in res_u}
                            common_cols = set(m_cols.keys()).intersection(set(u_cols.keys()))
                            
                            insert_cols = ", ".join([f"`{u_cols[c]}`" for c in common_cols])
                            select_cols = ", ".join([f"`{m_cols[c]}`" for c in common_cols])
                            
                            sql = f"INSERT IGNORE INTO uncleaned_listing_master_table ({insert_cols}) SELECT {select_cols} FROM master_table WHERE id IN :ids"
                            db.session.execute(text(sql).bindparams(bindparam("ids", expanding=True)), {"ids": batch_incomplete_master_ids})
                            delete_rows_by_ids("master_table", batch_incomplete_master_ids)

                        # 4. Bulk updates
                        if batch_updates:
                            db.session.execute(
                                text("""
                                    UPDATE master_table 
                                    SET business_name=:business_name, primary_phone=:primary_phone, secondary_phone=:secondary_phone,
                                        other_phones=:other_phones, email=:email, address=:address, city=:city, state=:state,
                                        area=:area, pincode=:pincode
                                    WHERE id=:id
                                """),
                                batch_updates
                            )
                        db.session.commit()
                        
            # 4. Clean product_master
            if table_name in ('product_master', 'all'):
                logger.info("Cleaning product_master...")
                total_p_rows = initial_metrics["product_master"]["total_rows"]
                log_entry.total_rows += total_p_rows
                
                last_id = 0
                processed_asin_duplicates = set()
                processed_name_duplicates = set()
                
                while True:
                    rows_res = db.session.execute(
                        text("""
                            SELECT id, marketplace_name, asin, product_name, brand, category_name, sub_category_name, price, list_price, product_category_id
                            FROM product_master
                            WHERE id > :last_id
                            ORDER BY id
                            LIMIT :limit
                        """),
                        {"limit": batch_size, "last_id": last_id}
                    ).fetchall()
                    
                    if not rows_res:
                        break
                        
                    last_id = rows_res[-1][0]
                    logger.info(f"Processing product_master batch last_id={last_id} limit={batch_size}")
                    
                    batch_updates = []
                    batch_duplicates = []
                    batch_unmatched = []
                    batch_incomplete_product_ids = []
                    
                    for row in rows_res:
                        row_id = row[0]
                        market = row[1]
                        asin = row[2]
                        p_name = row[3]
                        brand = row[4]
                        category = row[5]
                        sub_cat = row[6]
                        price = row[7]
                        list_price = row[8]
                        p_cat_id = row[9]
                        
                        # Apply trimming and convert empty to None
                        market_clean = market.strip() if market else None
                        asin_clean = asin.strip() if asin else None
                        p_name_clean = p_name.strip() if p_name else None
                        brand_clean = brand.strip() if brand else None
                        category_clean = category.strip() if category else None
                        sub_cat_clean = sub_cat.strip() if sub_cat else None
                        
                        if market_clean == '': market_clean = None
                        if asin_clean == '': asin_clean = None
                        if p_name_clean == '': p_name_clean = None
                        if brand_clean == '': brand_clean = None
                        if category_clean == '': category_clean = None
                        if sub_cat_clean == '': sub_cat_clean = None

                        # Check if record is incomplete
                        is_incomplete = False
                        if not p_name_clean or not market_clean or not category_clean:
                            is_incomplete = True
                        
                        if is_incomplete:
                            incomplete_product_count += 1
                            batch_incomplete_product_ids.append(row_id)
                            continue

                        # Check for Duplication
                        is_dupe = False
                        dupe_key = ""
                        if asin_clean:
                            dupe_key = f"{market_clean or ''}_{asin_clean}".lower()
                            if dupe_key in processed_asin_duplicates:
                                is_dupe = True
                            else:
                                processed_asin_duplicates.add(dupe_key)
                        elif p_name_clean:
                            dupe_key = f"{market_clean or ''}_{p_name_clean}_{brand_clean or ''}".lower().replace(' ', '')
                            if dupe_key in processed_name_duplicates:
                                is_dupe = True
                            else:
                                processed_name_duplicates.add(dupe_key)

                        if is_dupe:
                            duplicate_count += 1
                            row_dict = {
                                "id": row_id, "marketplace_name": market_clean, "asin": asin_clean, 
                                "product_name": p_name_clean, "brand": brand_clean, "category_name": category_clean, 
                                "sub_category_name": sub_cat_clean, "price": str(price), "list_price": str(list_price)
                            }
                            batch_duplicates.append((row_id, dupe_key, row_dict))
                            continue

                        # Check Category Mapping validity using product_category_master
                        if category_clean:
                            cat_lower = category_clean.lower()
                            if cat_lower in cat_map:
                                category_clean = cat_map[cat_lower]
                            else:
                                wrong_cat_count += 1
                                row_dict = {
                                    "id": row_id, "marketplace_name": market_clean, "asin": asin_clean, 
                                    "product_name": p_name_clean, "brand": brand_clean, "category_name": category_clean, 
                                    "sub_category_name": sub_cat_clean, "price": str(price), "list_price": str(list_price)
                                }
                                batch_unmatched.append((row_id, 'category', category_clean, row_dict))
                                continue

                        # Check updates
                        if (market_clean != market or asin_clean != asin or p_name_clean != p_name or 
                            brand_clean != brand or category_clean != category or sub_cat_clean != sub_cat):
                            cleaned_count += 1
                            batch_updates.append({
                                "id": row_id, "marketplace_name": market_clean, "asin": asin_clean,
                                "product_name": p_name_clean, "brand": brand_clean, "category_name": category_clean,
                                "sub_category_name": sub_cat_clean
                            })

                    # Perform Apply modifications to DB
                    if run_type == 'apply':
                        # 1. Bulk insert duplicates and delete duplicate rows
                        if batch_duplicates:
                            dupe_params = []
                            dupe_ids = []
                            for dupe_id, key, r_data in batch_duplicates:
                                dupe_ids.append(dupe_id)
                                dupe_params.append({
                                    "table_name": "product_master",
                                    "duplicate_key": key,
                                    "original_id": 0,
                                    "duplicate_id": dupe_id,
                                    "record_data": json.dumps(r_data)
                                })
                            
                            # Bulk insert
                            db.session.execute(
                                text("""
                                    INSERT IGNORE INTO duplicate_records_review
                                        (table_name, duplicate_key, original_id, duplicate_id, record_data)
                                    VALUES (:table_name, :duplicate_key, :original_id, :duplicate_id, :record_data)
                                """),
                                dupe_params
                            )
                            
                            # Bulk delete
                            delete_rows_by_ids("product_master", dupe_ids)

                        # 2. Bulk insert unmatched and delete unmatched rows
                        if batch_unmatched:
                            unmatched_params = []
                            unmatched_ids = []
                            for un_id, u_type, u_val, r_data in batch_unmatched:
                                unmatched_ids.append(un_id)
                                unmatched_params.append({
                                    "data_type": u_type,
                                    "invalid_value": u_val,
                                    "correction_status": "pending",
                                    "table_name": "product_master",
                                    "row_id": un_id,
                                    "row_data": json.dumps(r_data)
                                })
                            
                            # Bulk insert
                            db.session.execute(
                                text("""
                                    INSERT IGNORE INTO unmatched_data_review
                                        (data_type, invalid_value, correction_status, table_name, row_id, row_data)
                                    VALUES (:data_type, :invalid_value, :correction_status, :table_name, :row_id, :row_data)
                                """),
                                unmatched_params
                            )
                            
                            # Bulk delete
                            delete_rows_by_ids("product_master", unmatched_ids)

                        # 3. Bulk insert incomplete products to uncleaned table and delete from product_master
                        if batch_incomplete_product_ids:
                            db.session.execute(
                                text("INSERT IGNORE INTO uncleaned_product_master_table (id, marketplace_name, asin, product_name, brand, category_name, sub_category_name, price, list_price, product_category_id) SELECT id, marketplace_name, asin, product_name, brand, category_name, sub_category_name, price, list_price, product_category_id FROM product_master WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
                                {"ids": batch_incomplete_product_ids}
                            )
                            delete_rows_by_ids("product_master", batch_incomplete_product_ids)

                        # 4. Bulk updates
                        if batch_updates:
                            db.session.execute(
                                text("""
                                    UPDATE product_master 
                                    SET marketplace_name=:marketplace_name, asin=:asin, product_name=:product_name,
                                        brand=:brand, category_name=:category_name, sub_category_name=:sub_category_name
                                    WHERE id=:id
                                """),
                                batch_updates
                            )
                        db.session.commit()
                        
            # 5. Log summary and finish
            log_entry.duplicate_rows = duplicate_count
            log_entry.missing_location_rows = missing_count
            log_entry.invalid_phone_email_rows = invalid_phone_email_count
            log_entry.unmatched_location_rows = unmatched_count
            log_entry.wrong_category_rows = wrong_cat_count
            log_entry.cleaned_rows = cleaned_count
            log_entry.status = 'completed'
            log_entry.completed_at = datetime.now()
            
            # Save details JSON log
            log_entry.details = json.dumps({
                "message": f"Successfully completed data cleaning {run_type} execution.",
                "timestamp": datetime.now().isoformat(),
                "counts": {
                    "duplicates_removed": duplicate_count,
                    "missing_location_fields": missing_count,
                    "invalid_phones_or_emails": invalid_phone_email_count,
                    "unmatched_locations_removed": unmatched_count,
                    "wrong_categories_removed": wrong_cat_count,
                    "records_cleaned_or_updated": cleaned_count,
                    "incomplete_master_segregated": incomplete_master_count,
                    "incomplete_product_segregated": incomplete_product_count
                }
            })
            
            db.session.commit()
            logger.info(f"Async data cleaning task run_id={run_id} completed successfully.")
            
        except Exception as e:
            logger.error(f"Error executing async data cleaning run_id={run_id}: {e}", exc_info=True)
            db.session.rollback()
            
            # --- AUTO ROLLBACK IF FAIL ---
            if run_type == 'apply':
                logger.info(f"Starting automatic rollback for run_id={run_id} due to failure...")
                try:
                    db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                    if table_name in ('master_table', 'all') and backup_table_master:
                        db.session.execute(text("DROP TABLE IF EXISTS master_table"))
                        db.session.execute(text(f"CREATE TABLE master_table LIKE {backup_table_master}"))
                        db.session.execute(text(f"INSERT INTO master_table SELECT * FROM {backup_table_master}"))
                        logger.info("Automatic rollback master_table: SUCCESS")
                    if table_name in ('product_master', 'all') and backup_table_product:
                        db.session.execute(text("DROP TABLE IF EXISTS product_master"))
                        db.session.execute(text(f"CREATE TABLE product_master LIKE {backup_table_product}"))
                        db.session.execute(text(f"INSERT INTO product_master SELECT * FROM {backup_table_product}"))
                        logger.info("Automatic rollback product_master: SUCCESS")
                    reconcile_review_records_present_in_active_tables()
                    db.session.commit()
                except Exception as rollback_err:
                    logger.error(f"Critical error during auto rollback: {rollback_err}")
                    db.session.rollback()
            
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.completed_at = datetime.now()
            db.session.commit()
        finally:
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()
            # Remove from active tasks
            active_tasks.pop(run_id, None)

def rollback_from_backup(run_id, target_run_id, app_context):
    """Restore master_table and product_master from backup tables created in target_run_id"""
    with app_context:
        log_entry = DataCleaningLog.query.filter_by(run_id=run_id).first()
        if not log_entry:
            return
            
        try:
            target_log = DataCleaningLog.query.filter_by(run_id=target_run_id).first()
            if not target_log or not target_log.backup_table_name:
                raise ValueError(f"No backup tables found for target run_id {target_run_id}")
                
            backup_tables = [t.strip() for t in target_log.backup_table_name.split(',')]
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            
            for b_table in backup_tables:
                if 'master_table_backup' in b_table:
                    # Restore master_table
                    db.session.execute(text("DROP TABLE IF EXISTS master_table"))
                    db.session.execute(text(f"CREATE TABLE master_table LIKE {b_table}"))
                    db.session.execute(text(f"INSERT INTO master_table SELECT * FROM {b_table}"))
                    logger.info(f"Restored master_table from {b_table}")
                elif 'product_master_backup' in b_table:
                    # Restore product_master
                    db.session.execute(text("DROP TABLE IF EXISTS product_master"))
                    db.session.execute(text(f"CREATE TABLE product_master LIKE {b_table}"))
                    db.session.execute(text(f"INSERT INTO product_master SELECT * FROM {b_table}"))
                    logger.info(f"Restored product_master from {b_table}")

            reconcile_review_records_present_in_active_tables()
            db.session.commit()
            
            log_entry.status = 'completed'
            log_entry.completed_at = datetime.now()
            log_entry.details = json.dumps({
                "message": f"Successfully rolled back from target run_id {target_run_id}.",
                "timestamp": datetime.now().isoformat(),
                "restored_tables": backup_tables
            })
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error during rollback run_id={run_id}: {e}")
            db.session.rollback()
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.completed_at = datetime.now()
            db.session.commit()
        finally:
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()
            active_tasks.pop(run_id, None)
