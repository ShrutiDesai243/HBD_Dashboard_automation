from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    try:
        print("--- DESCRIBE product_category_master ---")
        res = db.session.execute(text("DESCRIBE product_category_master")).fetchall()
        for r in res:
            print(r)

        print("\n--- DESCRIBE platform_category_mapping ---")
        res = db.session.execute(text("DESCRIBE platform_category_mapping")).fetchall()
        for r in res:
            print(r)

        print("\n--- SAMPLE platform_category_mapping FOR IndiaMart ---")
        res = db.session.execute(text("SELECT * FROM platform_category_mapping WHERE platform_name = 'IndiaMart' LIMIT 5")).fetchall()
        for r in res:
            print(r)

        print("\n--- SAMPLE indiamart_mappings hierarchy sample ---")
        res = db.session.execute(text("SELECT * FROM indiamart_mappings WHERE category_level > 1 LIMIT 5")).fetchall()
        for r in res:
            print(r)

    except Exception as e:
        print(f"Error: {e}")
