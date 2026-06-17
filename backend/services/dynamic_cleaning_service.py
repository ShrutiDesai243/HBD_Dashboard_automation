import os
import re
import json
import logging
from sqlalchemy import text, bindparam
from extensions import db
from datetime import datetime

logger = logging.getLogger("DynamicCleaningService")

# Global dict to track active running tasks
active_tasks = {}

COMMON_SPELLING_MAP = {
    "banglore": "Bangalore", "bengaluru": "Bangalore", "calcutta": "Kolkata", "bombay": "Mumbai",
    "delhi ncr": "Delhi", "madras": "Chennai", "poona": "Pune", "banaras": "Varanasi",
    "gurgaon": "Gurugram", "orissa": "Odisha", "pondicherry": "Puducherry", "trivandrum": "Thiruvananthapuram",
    "cochin": "Kochi", "secunderabad": "Hyderabad", "gauhati": "Guwahati", "vizag": "Visakhapatnam",
    "waltair": "Visakhapatnam", "baroda": "Vadodara"
}

# Simple manual state mapping for demonstration
# Ideally, this should come from a DB query grouping city -> state
CITY_TO_STATE_INFERENCE = {
    "mumbai": "Maharashtra",
    "pune": "Maharashtra",
    "nagpur": "Maharashtra",
    "bangalore": "Karnataka",
    "mysore": "Karnataka",
    "chennai": "Tamil Nadu",
    "coimbatore": "Tamil Nadu",
    "delhi": "Delhi",
    "gurugram": "Haryana",
    "noida": "Uttar Pradesh",
    "hyderabad": "Telangana",
    "kolkata": "West Bengal",
    "ahmedabad": "Gujarat",
    "surat": "Gujarat",
    "jaipur": "Rajasthan"
}

def validate_phone(phone):
    """Simple validator for Indian phone numbers"""
    if not phone:
        return False
    clean = re.sub(r'[\s\-\(\)\+]', '', str(phone))
    if not clean.isdigit():
        return False
    if len(clean) == 10 and clean[0] in '6789': return True
    if len(clean) == 11 and clean.startswith('0') and clean[1] in '6789': return True
    if len(clean) == 12 and clean.startswith('91') and clean[2] in '6789': return True
    if 8 <= len(clean) <= 12: return True
    return False

def extract_pincode_from_address(address):
    """Regex helper to extract a 6-digit pin code from address string"""
    if not address:
        return None
    match = re.search(r'\b\d{6}\b', str(address))
    return match.group(0) if match else None

def clean_and_route_batch(source_table, records):
    """
    Evaluates, scores, and routes a batch of records.
    `records` should be a list of dicts:
    { "id": ..., "name": ..., "phone": ..., "email": ..., "address": ..., "city": ..., "state": ..., "pincode": ... }
    """
    tier1_inserts = []
    tier2_inserts = []
    tier3_inserts = []
    tier4_inserts = []
    tier5_inserts = []
    processed_ids = []
    updates_for_status = []

    # In a real scenario, you'd load existing deduplication keys from tier1 into memory
    seen_dedupe_keys = set() 

    for r in records:
        original_id = r.get("id")
        processed_ids.append(original_id)

        # 1. Standardization & Extraction
        name = (r.get("name") or "").strip()
        phone = (r.get("phone") or "").strip()
        email = (r.get("email") or "").strip()
        address = (r.get("address") or "").strip()
        city = (r.get("city") or "").strip()
        state = (r.get("state") or "").strip()
        pincode = (r.get("pincode") or "").strip()

        inferred_fields = []

        # Fix city spelling
        if city.lower() in COMMON_SPELLING_MAP:
            city = COMMON_SPELLING_MAP[city.lower()]
            inferred_fields.append("city_spelling")

        # Infer pincode
        if not pincode and address:
            pin = extract_pincode_from_address(address)
            if pin:
                pincode = pin
                inferred_fields.append("pincode_extracted")

        # Infer state from city
        if not state and city:
            c_lower = city.lower()
            if c_lower in CITY_TO_STATE_INFERENCE:
                state = CITY_TO_STATE_INFERENCE[c_lower]
                inferred_fields.append("state_inferred_from_city")

        # Validate
        is_phone_valid = validate_phone(phone)
        has_location = bool(city and state and address)
        has_contact = is_phone_valid or bool(email)
        has_name = bool(name)

        # Deduplication check
        dupe_key = f"{name.lower()}_{phone}_{address.lower()}".replace(" ", "")
        is_duplicate = False
        if dupe_key and dupe_key in seen_dedupe_keys:
            is_duplicate = True
        elif dupe_key:
            seen_dedupe_keys.add(dupe_key)

        # 2. Quality Scoring
        score = 0
        if is_phone_valid: score += 30
        elif email: score += 15
        
        if city and state: score += 30
        if address: score += 20
        if has_name: score += 20

        # 3. Routing
        assigned_tier = None
        if is_duplicate:
            assigned_tier = "tier5_linked_duplicates"
            tier5_inserts.append({
                "raw_source_table": source_table, "raw_source_id": original_id,
                "parent_tier": "tier1_master_clean", "parent_id": 0, # Should link to actual ID
                "duplicate_data": json.dumps(r), "duplicate_reason": "Dedupe Key Match"
            })
        elif score >= 90:
            assigned_tier = "tier1_master_clean"
            tier1_inserts.append({
                "raw_source_table": source_table, "raw_source_id": original_id, "business_name": name,
                "primary_phone": phone if is_phone_valid else None, "email": email, "address": address,
                "city": city, "state": state, "pincode": pincode, "quality_score": score,
                "inferred_fields": ",".join(inferred_fields)
            })
        elif has_location and not has_contact:
            assigned_tier = "tier2_missing_contact"
            tier2_inserts.append({
                "raw_source_table": source_table, "raw_source_id": original_id, "business_name": name,
                "address": address, "city": city, "state": state, "pincode": pincode,
                "quality_score": score, "inferred_fields": ",".join(inferred_fields)
            })
        elif has_contact and not has_location:
            assigned_tier = "tier3_missing_location"
            tier3_inserts.append({
                "raw_source_table": source_table, "raw_source_id": original_id, "business_name": name,
                "primary_phone": phone if is_phone_valid else None, "email": email,
                "partial_address": address, "quality_score": score,
                "inferred_fields": ",".join(inferred_fields)
            })
        else:
            assigned_tier = "tier4_partial_fragments"
            tier4_inserts.append({
                "raw_source_table": source_table, "raw_source_id": original_id, "business_name": name,
                "fragment_data": json.dumps(r), "quality_score": score
            })

        updates_for_status.append({
            "id": original_id,
            "cleaning_status": "PROCESSED",
            "assigned_tier": assigned_tier,
            "quality_score": score
        })

    # Execute Inserts & Updates safely within a transaction
    try:
        if tier1_inserts:
            db.session.execute(text("""
                INSERT INTO tier1_master_clean (raw_source_table, raw_source_id, business_name, primary_phone, email, address, city, state, pincode, quality_score, inferred_fields)
                VALUES (:raw_source_table, :raw_source_id, :business_name, :primary_phone, :email, :address, :city, :state, :pincode, :quality_score, :inferred_fields)
            """), tier1_inserts)
        
        if tier2_inserts:
            db.session.execute(text("""
                INSERT INTO tier2_missing_contact (raw_source_table, raw_source_id, business_name, address, city, state, pincode, quality_score, inferred_fields)
                VALUES (:raw_source_table, :raw_source_id, :business_name, :address, :city, :state, :pincode, :quality_score, :inferred_fields)
            """), tier2_inserts)
            
        if tier3_inserts:
            db.session.execute(text("""
                INSERT INTO tier3_missing_location (raw_source_table, raw_source_id, business_name, primary_phone, email, partial_address, quality_score, inferred_fields)
                VALUES (:raw_source_table, :raw_source_id, :business_name, :primary_phone, :email, :partial_address, :quality_score, :inferred_fields)
            """), tier3_inserts)
            
        if tier4_inserts:
            db.session.execute(text("""
                INSERT INTO tier4_partial_fragments (raw_source_table, raw_source_id, business_name, fragment_data, quality_score)
                VALUES (:raw_source_table, :raw_source_id, :business_name, :fragment_data, :quality_score)
            """), tier4_inserts)
            
        if tier5_inserts:
            db.session.execute(text("""
                INSERT INTO tier5_linked_duplicates (raw_source_table, raw_source_id, parent_tier, parent_id, duplicate_data, duplicate_reason)
                VALUES (:raw_source_table, :raw_source_id, :parent_tier, :parent_id, :duplicate_data, :duplicate_reason)
            """), tier5_inserts)

        # Note: We NEVER run DELETE on the source table. We only update its status.
        if updates_for_status:
            db.session.execute(text(f"""
                UPDATE {source_table} 
                SET cleaning_status = :cleaning_status, assigned_tier = :assigned_tier, quality_score = :quality_score
                WHERE id = :id
            """), updates_for_status)
                
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database transaction failed for batch. Rolling back. Error: {e}")
        # Raise it so the caller knows the batch failed
        raise e
        
    return len(records)
