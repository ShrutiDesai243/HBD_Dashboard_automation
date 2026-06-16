import os
import sys

# Ensure backend directory is in path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import app
from extensions import db
from model.category_mapping_platforms import CategoryMappingPlatform
from model.category_mapping_synonyms import CategoryMappingSynonym
from services.category_sync_service import PLATFORM_CATEGORY_QUERIES, CATEGORY_SYNONYMS

print("Starting table initialization and seeding...")
with app.app_context():
    try:
        # 1. Create tables
        db.create_all()
        print("SQLAlchemy tables created successfully.")

        # 2. Seed platforms config
        if CategoryMappingPlatform.query.count() == 0:
            print("Seeding initial 8 platform query configurations...")
            for platform, config in PLATFORM_CATEGORY_QUERIES.items():
                p_cfg = CategoryMappingPlatform(
                    platform_name=platform,
                    query_sql=config['query'].strip(),
                    is_active=True
                )
                db.session.add(p_cfg)
            db.session.commit()
            print("Platforms configuration seeded successfully.")
        else:
            print("Platforms config table already contains data. Skipping seeding.")

        # 3. Seed synonyms dictionary
        if CategoryMappingSynonym.query.count() == 0:
            print("Seeding initial synonym rules...")
            for raw, canonical in CATEGORY_SYNONYMS.items():
                syn = CategoryMappingSynonym(
                    raw_value=raw,
                    canonical_value=canonical
                )
                db.session.add(syn)
            db.session.commit()
            print("Synonyms dictionary seeded successfully.")
        else:
            print("Synonyms table already contains data. Skipping seeding.")

        print("DB Initialization and Seeding completed successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error during initialization/seeding: {str(e)}")
