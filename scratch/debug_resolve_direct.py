import os
import sys
from sqlalchemy import text

# Add current directory to path
sys.path.append(os.path.abspath('.'))

from app import app
from extensions import db
from routes.unmatched_data_routes import auto_resolve_matched_records
from model.unmatched_data_review import UnmatchedDataReview

with app.app_context():
    print("Checking database directly...")
    
    # Check total pending vijaywada
    pending_vijaywada = UnmatchedDataReview.query.filter(
        UnmatchedDataReview.data_type == 'city',
        UnmatchedDataReview.correction_status == 'pending',
        db.func.lower(UnmatchedDataReview.invalid_value) == 'vijaywada'
    ).all()
    print(f"Pending 'vijaywada' records in model: {len(pending_vijaywada)}")
    
    # Check valid cities in Location_Master_India
    cities_res = db.session.execute(
        text("SELECT DISTINCT LOWER(city_name) FROM Location_Master_India WHERE LOWER(city_name) LIKE '%vijay%'")
    ).fetchall()
    print("Vijay cities in Location_Master_India:", [r[0] for r in cities_res])
    
    # Let's run auto_resolve_matched_records
    print("Running auto_resolve_matched_records()...")
    auto_resolve_matched_records()
    
    # Check again
    pending_vijaywada_after = UnmatchedDataReview.query.filter(
        UnmatchedDataReview.data_type == 'city',
        UnmatchedDataReview.correction_status == 'pending',
        db.func.lower(UnmatchedDataReview.invalid_value) == 'vijaywada'
    ).all()
    print(f"Pending 'vijaywada' records in model AFTER resolve: {len(pending_vijaywada_after)}")
    
    corrected_vijaywada = UnmatchedDataReview.query.filter(
        UnmatchedDataReview.data_type == 'city',
        UnmatchedDataReview.correction_status == 'corrected',
        db.func.lower(UnmatchedDataReview.invalid_value) == 'vijaywada'
    ).all()
    print(f"Corrected 'vijaywada' records in model AFTER resolve: {len(corrected_vijaywada)}")
