import os
import sys

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, ".."))
sys.path.insert(0, os.path.join(backend_dir, "..", "backend"))

from app import app
from extensions import db
from model.platform_category_mapping import PlatformCategoryMapping
from model.master_category import MasterCategory

with app.app_context():
    print("=== Checking specific mapping: Dairy & Beverages > Beverages > Green Tea ===")
    m = PlatformCategoryMapping.query.filter_by(
        platform_name='DMart',
        platform_category_raw='Dairy & Beverages > Beverages > Green Tea',
        is_active=True
    ).first()
    
    if m:
        mc = MasterCategory.query.get(m.master_category_id) if m.master_category_id else None
        if mc:
            print(f"Mapping: '{m.platform_category_raw}' -> Master: '{mc.path}' (Level: {mc.level}, Active: {mc.is_active})")
        else:
            print(f"Mapping exists but has no master category associated.")
    else:
        print("Mapping not found.")
        
    print("\n=== Checking other three-level candidates ===")
    candidates = [
        'Dairy & Beverages > Beverages > Soft Drinks',
        'Dairy & Beverages > Dairy > Milk',
        'Home Cleaners & Bathroom Needs > Cleaners > Bathroom Cleaners',
        'Home Cleaners & Bathroom Needs > Detergent & Fabric Care > Detergent Powder'
    ]
    for c in candidates:
        m = PlatformCategoryMapping.query.filter_by(
            platform_name='DMart',
            platform_category_raw=c,
            is_active=True
        ).first()
        if m:
            mc = MasterCategory.query.get(m.master_category_id) if m.master_category_id else None
            if mc:
                print(f"Mapping: '{m.platform_category_raw}' -> Master: '{mc.path}' (Level: {mc.level})")
            else:
                print(f"Mapping: '{m.platform_category_raw}' -> PENDING")
        else:
            print(f"Mapping: '{c}' -> NOT FOUND")
