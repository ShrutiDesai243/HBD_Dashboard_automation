import os
import sys
import json
import time

# Ensure backend folder is in path and set it as working directory BEFORE imports
backend_path = os.path.abspath('backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
os.chdir(backend_path)
print(f"Changed working directory to: {backend_path}")

from dotenv import load_dotenv
load_dotenv('.env')

from app import app
from extensions import db
from model.user import User
from model.data_cleaning_log import DataCleaningLog
from flask_jwt_extended import create_access_token

def run_tests():
    print("==================================================")
    print("Starting Safe Data Cleaning API Verification Test")
    print("==================================================")
    
    with app.app_context():
        # 1. Ensure test user exists or find one to generate JWT
        user = User.query.first()
        if not user:
            print("No users found in DB. Creating a temporary test user...")
            user = User(email="testadmin@hbd.com", name="Test Admin")
            user.set_password("Admin@123") # Assuming User model has set_password
            db.session.add(user)
            db.session.commit()
            print(f"Created user: {user.email}")
        else:
            print(f"Using existing user: {user.email} (ID: {user.id})")
            
        # Generate JWT token
        token = create_access_token(identity=user.email)
        print(f"Generated JWT token (first 30 chars): {token[:30]}...")

        # 2. Test Client
        client = app.test_client()
        # Set JWT cookie for cookie-based authentication
        client.set_cookie('access_token_cookie', token)
        
        # Test 1: Analyze Endpoint
        print("\n[TEST 1] GET /api/cleaning/analyze...")
        res = client.get("/api/cleaning/analyze")
        print(f"Status: {res.status_code}")
        print(f"Response: {json.dumps(res.get_json(), indent=2)}")
        assert res.status_code == 200, "Analyze endpoint failed"
        
        # Test 2: History Endpoint
        print("\n[TEST 2] GET /api/cleaning/history...")
        res = client.get("/api/cleaning/history")
        print(f"Status: {res.status_code}")
        print(f"Response count: {len(res.get_json().get('data', []))}")
        assert res.status_code == 200, "History endpoint failed"

        # Test 3: Dry Run Endpoint
        print("\n[TEST 3] POST /api/cleaning/dry-run...")
        res = client.post("/api/cleaning/dry-run", json={"table_name": "master_table"})
        print(f"Status: {res.status_code}")
        res_data = res.get_json()
        print(f"Response: {json.dumps(res_data, indent=2)}")
        assert res.status_code == 200, "Dry-run trigger failed"
        
        run_id = res_data.get("run_id")
        print(f"Waiting for dry-run {run_id} to finish...")
        
        # Poll Status
        for _ in range(15):
            time.sleep(2)
            status_res = client.get(f"/api/cleaning/status/{run_id}")
            status_data = status_res.get_json().get("data", {})
            print(f" - Poll status: {status_data.get('status')}")
            if status_data.get("status") != "running":
                print(f"Finished. Final stats: {json.dumps(status_data, indent=2)}")
                break

        # Test 4: Verify Admin Protection (Request without Cookie)
        print("\n[TEST 4] Verify Admin protection on GET /api/cleaning/analyze...")
        client_no_auth = app.test_client()
        res_no_auth = client_no_auth.get("/api/cleaning/analyze")
        print(f"Status: {res_no_auth.status_code}")
        print(f"Response: {res_no_auth.get_json()}")
        # Should return 401 unauthorized
        assert res_no_auth.status_code == 401, "API is not protected!"
        print("API protection: VERIFIED")

        print("\n==================================================")
        print("Verification Tests: ALL PASSED!")
        print("==================================================")

if __name__ == "__main__":
    run_tests()
