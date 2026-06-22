import os
import sys
import requests
from sqlalchemy import create_engine, text

# Add current dir to path to import config
sys.path.append(os.getcwd())
try:
    from config import config
except ImportError:
    print("❌ ERROR: Could not import config. Make sure you run this script from the backend directory.")
    sys.exit(1)

API_BASE_URL = "http://127.0.0.1:8001"
TEST_TABLE = "raw_clean_google_map_data"

def print_header(title):
    print("\n" + "="*60)
    print(f"--- {title} ---".center(60))
    print("="*60)

def test_database_schema():
    print_header("Test 1: Checking Database Schema")
    engine = create_engine(config.DATABASE_URI)
    try:
        with engine.connect() as conn:
            # 1. Check if source table exists
            res = conn.execute(text(f"SHOW TABLES LIKE '{TEST_TABLE}'")).fetchone()
            if not res:
                print(f"❌ FAIL: Source table '{TEST_TABLE}' does NOT exist in the database.")
                return False
            print(f"✅ PASS: Source table '{TEST_TABLE}' exists.")

            # 2. Check if tracking columns exist
            cols = conn.execute(text(f"SHOW COLUMNS FROM {TEST_TABLE}")).fetchall()
            col_names = [c[0].lower() for c in cols]
            missing_cols = []
            for req in ['cleaning_status', 'assigned_tier', 'quality_score']:
                if req not in col_names:
                    missing_cols.append(req)
            
            if missing_cols:
                print(f"⚠️ WARNING: Table '{TEST_TABLE}' is missing columns: {missing_cols}")
                print("    (This is expected if you haven't prepared the table yet)")
            else:
                print(f"✅ PASS: Table '{TEST_TABLE}' has all required tracking columns.")

            # 3. Check if destination tier tables exist
            tier_tables = ["tier1_master_clean", "tier2_missing_contact", "tier3_missing_location", "tier4_partial_fragments", "tier5_linked_duplicates"]
            missing_tiers = False
            for tt in tier_tables:
                if not conn.execute(text(f"SHOW TABLES LIKE '{tt}'")).fetchone():
                    print(f"❌ FAIL: Destination table '{tt}' is missing!")
                    missing_tiers = True
            if missing_tiers:
                print("❌ FAIL: One or more destination tier tables are missing. The cleaner will crash.")
                return False
            else:
                print("✅ PASS: All 5 destination tier tables exist.")
                
        return True
    except Exception as e:
        print(f"❌ CRITICAL FAIL: Database connection error: {e}")
        return False

def test_api_endpoints():
    print_header("Test 2: Checking Backend API Routes")
    print(f"Connecting to Flask at {API_BASE_URL}...")
    
    # 1. Test Tables Endpoint
    try:
        r = requests.get(f"{API_BASE_URL}/api/tiers/tables", timeout=5)
        if r.status_code == 200:
            tables = r.json().get('tables', [])
            print(f"✅ PASS: GET /api/tiers/tables returned {len(tables)} tables.")
        else:
            print(f"❌ FAIL: GET /api/tiers/tables returned HTTP {r.status_code}")
            print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"❌ CRITICAL FAIL: Could not reach backend server. Is it running? {e}")
        return False

    # 2. Test Prepare Table Endpoint
    try:
        payload = {"table": TEST_TABLE}
        r = requests.post(f"{API_BASE_URL}/api/tiers/prepare-table", json=payload, timeout=10)
        if r.status_code == 200:
            print(f"✅ PASS: POST /api/tiers/prepare-table returned SUCCESS.")
            print(f"Response: {r.json().get('message')}")
        else:
            print(f"❌ FAIL: POST /api/tiers/prepare-table returned HTTP {r.status_code}")
            print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"❌ FAIL: prepare-table API test threw error: {e}")

    # 3. Test Run Cleaner Endpoint
    try:
        payload = {"limit": 10, "table": TEST_TABLE}
        r = requests.post(f"{API_BASE_URL}/api/tiers/run-cleaner", json=payload, timeout=5)
        if r.status_code == 202:
            print(f"✅ PASS: POST /api/tiers/run-cleaner successfully triggered the background task.")
        else:
            print(f"❌ FAIL: POST /api/tiers/run-cleaner returned HTTP {r.status_code}")
            print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"❌ FAIL: run-cleaner API test threw error: {e}")

    return True

if __name__ == "__main__":
    print("🔍 DYNAMIC CLEANER DIAGNOSTIC TOOL 🔍")
    print("This script will find the exact root cause of your cleaner issues.\n")
    
    db_ok = test_database_schema()
    
    if db_ok:
        test_api_endpoints()
        
    print_header("DIAGNOSIS COMPLETE")
    print("Review the RED (❌ FAIL) messages above to see exactly what is broken on your server.")
