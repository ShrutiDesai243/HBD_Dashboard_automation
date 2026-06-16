import urllib.request
import json

try:
    print("Testing backend connection...")
    response = urllib.request.urlopen("http://127.0.0.1:8001/api/product-master/fetch-data?page=1&limit=1", timeout=5)
    print(f"Status Code: {response.status}")
    data = json.loads(response.read().decode('utf-8'))
    print("Response Data:", data)
except Exception as e:
    print("Connection Failed:", e)
