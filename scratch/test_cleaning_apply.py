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
    print("Starting Safe Data Cleaning APPLY API Test")
    print("==================================================")
    
    with app.app_context():
        # 1. Ensure test user exists or find one to generate JWT
        user = User.query.first()
        if not user:
            print("No users found in DB. Creating a temporary test user...")
            user = User(email="testadmin@hbd.com", name="Test Admin")
            user.set_password("Admin@123")
            db.session.add(user)
            db.session.commit()
            print(f"Created user: {user.email}")
        else:
            print(f"Using existing user: {user.email} (ID: {user.id})")
            
        # Generate JWT token
        token = create_access_token(identity=user.email)
        print(f"Generated JWT token...")

        # 2. Test Client
        client = app.test_client()
        # Set JWT cookie for cookie-based authentication
        client.set_cookie('access_token_cookie', token)
        
        # Test 1: Apply Endpoint
        print("\n[TEST] POST /api/cleaning/apply...")
        res = client.post("/api/cleaning/apply", json={"table_name": "master_table"})
        print(f"Status: {res.status_code}")
        res_data = res.get_json()
        print(f"Response: {json.dumps(res_data, indent=2)}")
        assert res.status_code == 200, "Apply endpoint failed"
        
        run_id = res_data.get("run_id")
        print(f"Waiting for apply run {run_id} to finish...")
        
        # Poll Status
        for i in range(30):
            time.sleep(2)
            status_res = client.get(f"/api/cleaning/status/{run_id}")
            status_data = status_res.get_json().get("data", {})
            print(f" - Poll {i+1}: status={status_data.get('status')}, processed={status_data.get('total_rows')}, error={status_data.get('error_message')}")
            if status_data.get("status") not in ("running", "pending"):
                print(f"Finished. Final stats: {json.dumps(status_data, indent=2)}")
                break

        print("\n==================================================")
        print("Verification Tests complete.")
        print("==================================================")

if __name__ == "__main__":
    run_tests()
