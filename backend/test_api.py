import requests

try:
    response = requests.post("http://localhost:8001/api/tiers/run-cleaner", json={"limit": 100})
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
