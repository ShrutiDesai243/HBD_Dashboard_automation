from app import app
from routes.product_report_routes import refresh_flipkart_jiomart

with app.app_context():
    try:
        res = refresh_flipkart_jiomart()
        print(res)
    except Exception as e:
        print("Error:", e)
