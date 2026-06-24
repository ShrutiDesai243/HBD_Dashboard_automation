from app import app
from routes.product_report_routes import refresh_report_summary
import json

with app.app_context():
    try:
        from flask import request
        with app.test_request_context('/api/product-report/refresh?marketplace=all', method='POST'):
            res = refresh_report_summary()
            print("Response:", res[0].get_data(as_text=True))
    except Exception as e:
        print("Error:", e)
