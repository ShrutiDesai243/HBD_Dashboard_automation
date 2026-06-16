import os
import sys
import json
import re

# Ensure backend folder is in path
backend_path = os.path.abspath('backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
os.chdir(backend_path)

from dotenv import load_dotenv
load_dotenv('.env')

from app import app
from extensions import db
from sqlalchemy import text
from services.data_cleaning_service import (
    validate_phone,
    validate_email,
    extract_pincode_from_address,
    load_location_master,
    load_product_category_master,
    COMMON_SPELLING_MAP
)

def find_and_clean_samples():
    print("Connecting and loading reference master data...")
    with app.app_context():
        # Load Location and Product Category reference data
        states_set, cities_set, areas_by_city, state_map, city_map, area_map = load_location_master()
        prod_cats, cat_map = load_product_category_master()
        
        print("\n--- 1. MASTER TABLE SAMPLES (LISTING DATA) ---")
        
        # A. Sample with Invalid Phone / Email or Typos or Missing Pincode
        query_m = text("""
            SELECT id, business_name, primary_phone, email, address, city, state, area, pincode 
            FROM master_table 
            LIMIT 200
        """)
        rows_m = db.session.execute(query_m).fetchall()
        
        samples_found = 0
        for r in rows_m:
            row_id, name, phone, email, addr, city, state, area, pin = r
            
            # Check for error conditions
            has_whitespace = any(isinstance(x, str) and (x.startswith(' ') or x.endswith(' ')) for x in [name, phone, email, addr, city, state, area, pin])
            invalid_phone = phone and not validate_phone(phone.strip())
            invalid_email = email and not validate_email(email.strip())
            missing_pin_but_extractable = not pin and addr and re.search(r'\b\d{6}\b', str(addr))
            
            # Casing typo / common spelling mistake
            has_typo = False
            state_clean = state.strip() if state else ""
            city_clean = city.strip() if city else ""
            if state_clean.lower() in COMMON_SPELLING_MAP or city_clean.lower() in COMMON_SPELLING_MAP:
                has_typo = True
            
            # Unmatched location
            state_unmatched = state_clean and state_clean.lower() not in states_set
            city_unmatched = city_clean and city_clean.lower() not in cities_set
            
            if invalid_phone or invalid_email or missing_pin_but_extractable or has_typo or state_unmatched or city_unmatched:
                print(f"\n[Example {samples_found+1}] Row ID: {row_id} | Business: {name}")
                print(f"  * BEFORE:")
                print(f"    - Phone:   {repr(phone)}")
                print(f"    - Email:   {repr(email)}")
                print(f"    - Address: {repr(addr)}")
                print(f"    - City:    {repr(city)}")
                print(f"    - State:   {repr(state)}")
                print(f"    - Area:    {repr(area)}")
                print(f"    - Pincode: {repr(pin)}")
                
                # Perform cleaning simulation
                c_phone = phone.strip() if phone else None
                c_email = email.strip() if email else None
                c_addr = addr.strip() if addr else None
                c_city = city.strip() if city else None
                c_state = state.strip() if state else None
                c_area = area.strip() if area else None
                c_pin = pin.strip() if pin else None
                
                # Trimming empty strings
                if c_phone == '': c_phone = None
                if c_email == '': c_email = None
                if c_addr == '': c_addr = None
                if c_city == '': c_city = None
                if c_state == '': c_state = None
                if c_area == '': c_area = None
                if c_pin == '': c_pin = None
                
                # 1. Validate phone/email
                err_msg = []
                if c_phone and not validate_phone(c_phone):
                    err_msg.append("Invalid Phone (Nullified)")
                    c_phone = None
                if c_email and not validate_email(c_email):
                    err_msg.append("Invalid Email (Nullified)")
                    c_email = None
                    
                # 2. Pincode
                if not c_pin and c_addr:
                    ext = extract_pincode_from_address(c_addr)
                    if ext:
                        err_msg.append(f"Pincode Extracted: {ext}")
                        c_pin = ext
                        
                # 3. Spelling correction
                if c_state and c_state.lower() in COMMON_SPELLING_MAP:
                    err_msg.append(f"State Corrected: {c_state} -> {COMMON_SPELLING_MAP[c_state.lower()]}")
                    c_state = COMMON_SPELLING_MAP[c_state.lower()]
                if c_city and c_city.lower() in COMMON_SPELLING_MAP:
                    err_msg.append(f"City Corrected: {c_city} -> {COMMON_SPELLING_MAP[c_city.lower()]}")
                    c_city = COMMON_SPELLING_MAP[c_city.lower()]
                    
                # 4. Standard casing matching
                if c_state and c_state.lower() in states_set:
                    c_state = state_map.get(c_state.lower(), c_state)
                else:
                    if c_state: err_msg.append(f"Unmatched State: {c_state} (Moved to unmatched_data_review)")
                if c_city and c_city.lower() in cities_set:
                    c_city = city_map.get(c_city.lower(), c_city)
                else:
                    if c_city: err_msg.append(f"Unmatched City: {c_city} (Moved to unmatched_data_review)")
                
                print(f"  * ACTION / DETECTION: {', '.join(err_msg) if err_msg else 'Formatting Clean'}")
                print(f"  * AFTER:")
                print(f"    - Phone:   {repr(c_phone)}")
                print(f"    - Email:   {repr(c_email)}")
                print(f"    - City:    {repr(c_city)}")
                print(f"    - State:   {repr(c_state)}")
                print(f"    - Area:    {repr(c_area)}")
                print(f"    - Pincode: {repr(c_pin)}")
                
                samples_found += 1
                if samples_found >= 3:
                    break
                    
        # B. Duplicate sample search
        print("\nChecking for master_table duplicates...")
        dupe_q = text("""
            SELECT business_name, primary_phone, address, COUNT(*) as cnt
            FROM master_table
            WHERE business_name IS NOT NULL AND primary_phone IS NOT NULL AND address IS NOT NULL
            GROUP BY business_name, primary_phone, address
            HAVING cnt > 1
            LIMIT 1
        """)
        dupe_res = db.session.execute(dupe_q).fetchone()
        if dupe_res:
            name, phone, addr, count = dupe_res
            print(f"  * Duplicate Group Found: Name={repr(name)} | Phone={repr(phone)} | Address={repr(addr)} | Count: {count}")
            print(f"    - ACTION: Deletes {count-1} duplicate rows, leaving 1 original row.")
            print(f"    - DESTINATION: The deleted {count-1} duplicate rows are logged as JSON in the 'duplicate_records_review' table.")
        else:
            print("  * No active duplicates found in the sample set.")

        print("\n--- 2. PRODUCT MASTER SAMPLES ---")
        
        # Wrong Category Mapping sample
        query_p = text("""
            SELECT id, marketplace_name, asin, product_name, brand, category_name 
            FROM product_master 
            LIMIT 500
        """)
        rows_p = db.session.execute(query_p).fetchall()
        
        samples_found_p = 0
        for r in rows_p:
            row_id, market, asin, p_name, brand, category = r
            if category:
                cat_lower = category.strip().lower()
                if cat_lower not in prod_cats:
                    print(f"\n[Example {samples_found_p+1}] Row ID: {row_id} | Product: {p_name[:60]}")
                    print(f"  * BEFORE:")
                    print(f"    - Marketplace: {repr(market)}")
                    print(f"    - ASIN:        {repr(asin)}")
                    print(f"    - Category:    {repr(category)}")
                    
                    c_category = category.strip()
                    err_msg_p = []
                    # check casing standard
                    if cat_lower in cat_map:
                        c_category = cat_map[cat_lower]
                        err_msg_p.append(f"Casing standardized to: {c_category}")
                    else:
                        err_msg_p.append(f"Unmapped Category: {c_category} (Deleted and moved to unmatched_data_review)")
                        
                    print(f"  * ACTION / DETECTION: {', '.join(err_msg_p)}")
                    print(f"  * AFTER:")
                    print(f"    - Category:    {repr(c_category) if cat_lower in cat_map else 'DELETED (To review table)'}")
                    
                    samples_found_p += 1
                    if samples_found_p >= 2:
                        break
        
        if samples_found_p == 0:
            print("  * No wrong category mapping found in product samples.")
            
        # Duplicate Product sample
        print("\nChecking for product_master duplicates...")
        p_dupe_q = text("""
            SELECT marketplace_name, asin, COUNT(*) as cnt
            FROM product_master
            WHERE asin IS NOT NULL AND asin != ''
            GROUP BY marketplace_name, asin
            HAVING cnt > 1
            LIMIT 1
        """)
        p_dupe_res = db.session.execute(p_dupe_q).fetchone()
        if p_dupe_res:
            m_name, asin, count = p_dupe_res
            print(f"  * Duplicate Product Found: Marketplace={repr(m_name)} | ASIN={repr(asin)} | Count: {count}")
            print(f"    - ACTION: Deletes {count-1} duplicate rows, leaving 1 original row.")
            print(f"    - DESTINATION: The deleted {count-1} rows are stored in the 'duplicate_records_review' table.")
        else:
            print("  * No product duplicates found in the sample set.")

if __name__ == "__main__":
    find_and_clean_samples()
