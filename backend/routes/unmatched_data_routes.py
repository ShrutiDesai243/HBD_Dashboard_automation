from flask import Blueprint, jsonify, request
from sqlalchemy import text, func
from extensions import db
import logging
from model.unmatched_data_review import UnmatchedDataReview
from model.master_table_model import MasterTable

logger = logging.getLogger("UnmatchedDataRoutes")
unmatched_data_bp = Blueprint("unmatched_data", __name__)

def reconcile_review_records_present_in_active_tables():
    """
    Pending unmatched review rows should point to records removed from active tables.
    If a rollback or manual restore put the row back, hide it from pending review.
    """
    db.session.execute(text("""
        UPDATE unmatched_data_review u
        INNER JOIN master_table m ON u.row_id = m.id
        SET u.correction_status = 'corrected'
        WHERE u.correction_status = 'pending'
          AND u.table_name = 'master_table'
          AND u.row_id IS NOT NULL
    """))
    db.session.execute(text("""
        UPDATE unmatched_data_review u
        INNER JOIN product_master p ON u.row_id = p.id
        SET u.correction_status = 'corrected'
        WHERE u.correction_status = 'pending'
          AND u.table_name = 'product_master'
          AND u.row_id IS NOT NULL
    """))

def bulk_reintegrate_master_table_raw(row_datas):
    import json
    if not row_datas:
        return
    params = []
    for row_data in row_datas:
        r_data = json.loads(row_data) if row_data else {}
        if not r_data:
            continue
        params.append({
            "id": r_data.get("id"),
            "business_name": r_data.get("business_name"),
            "primary_phone": r_data.get("primary_phone"),
            "secondary_phone": r_data.get("secondary_phone"),
            "other_phones": r_data.get("other_phones"),
            "email": r_data.get("email"),
            "address": r_data.get("address"),
            "city": r_data.get("city"),
            "state": r_data.get("state"),
            "area": r_data.get("area"),
            "pincode": r_data.get("pincode")
        })
    if not params:
        return
    
    batch_size = 1000
    for i in range(0, len(params), batch_size):
        batch = params[i:i+batch_size]
        db.session.execute(
            text("""
                INSERT INTO master_table (id, business_name, primary_phone, secondary_phone, other_phones, email, address, city, state, area, pincode)
                VALUES (:id, :business_name, :primary_phone, :secondary_phone, :other_phones, :email, :address, :city, :state, :area, :pincode)
                ON DUPLICATE KEY UPDATE
                    business_name=VALUES(business_name),
                    primary_phone=VALUES(primary_phone),
                    secondary_phone=VALUES(secondary_phone),
                    other_phones=VALUES(other_phones),
                    email=VALUES(email),
                    address=VALUES(address),
                    city=VALUES(city),
                    state=VALUES(state),
                    area=VALUES(area),
                    pincode=VALUES(pincode)
            """),
            batch
        )

def bulk_reintegrate_product_master_raw(row_datas):
    import json
    if not row_datas:
        return
    params = []
    for row_data in row_datas:
        r_data = json.loads(row_data) if row_data else {}
        if not r_data:
            continue
        params.append({
            "id": r_data.get("id"),
            "marketplace_name": r_data.get("marketplace_name"),
            "asin": r_data.get("asin"),
            "product_name": r_data.get("product_name"),
            "brand": r_data.get("brand"),
            "category_name": r_data.get("category_name"),
            "sub_category_name": r_data.get("sub_category_name"),
            "price": r_data.get("price"),
            "list_price": r_data.get("list_price")
        })
    if not params:
        return
    
    batch_size = 1000
    for i in range(0, len(params), batch_size):
        batch = params[i:i+batch_size]
        db.session.execute(
            text("""
                INSERT INTO product_master (id, marketplace_name, asin, product_name, brand, category_name, sub_category_name, price, list_price)
                VALUES (:id, :marketplace_name, :asin, :product_name, :brand, :category_name, :sub_category_name, :price, :list_price)
                ON DUPLICATE KEY UPDATE
                    marketplace_name=VALUES(marketplace_name),
                    asin=VALUES(asin),
                    product_name=VALUES(product_name),
                    brand=VALUES(brand),
                    category_name=VALUES(category_name),
                    sub_category_name=VALUES(sub_category_name),
                    price=VALUES(price),
                    list_price=VALUES(list_price)
            """),
            batch
        )

def reintegrate_and_mark_corrected(review_record):
    import json
    r_data = json.loads(review_record.row_data) if review_record.row_data else {}
    
    if r_data:
        if review_record.table_name == 'master_table':
            bulk_reintegrate_master_table_raw([review_record.row_data])
        elif review_record.table_name == 'product_master':
            bulk_reintegrate_product_master_raw([review_record.row_data])
                
    review_record.correction_status = 'corrected'
    if r_data:
        review_record.invalid_value = r_data.get(review_record.data_type)
    logger.info(f"Auto-resolved unmatched record: {review_record.review_id} (value: {review_record.invalid_value}) because it was found in Location Master")

def auto_resolve_matched_records():
    """
    Checks all pending unmatched location records in unmatched_data_review.
    If the invalid_value is now present in Location_Master_India,
    automatically re-integrates the record and marks it as corrected.
    """
    try:
        reconcile_review_records_present_in_active_tables()

        # Load valid states, cities, and areas from Location_Master_India
        states_res = db.session.execute(
            text("SELECT DISTINCT LOWER(state_full_name), LOWER(state_short_code) FROM Location_Master_India")
        ).fetchall()
        valid_states = set()
        for r in states_res:
            if r[0]: valid_states.add(r[0].strip())
            if r[1]: valid_states.add(r[1].strip())
            
        cities_res = db.session.execute(
            text("SELECT DISTINCT LOWER(city_name) FROM Location_Master_India")
        ).fetchall()
        valid_cities = {r[0].strip() for r in cities_res if r[0]}

        areas_res = db.session.execute(
            text("SELECT DISTINCT LOWER(area_name) FROM Location_Master_India")
        ).fetchall()
        valid_areas = {r[0].strip() for r in areas_res if r[0]}

        for dtype, valid_set in [('state', valid_states), ('city', valid_cities), ('area', valid_areas)]:
            # Get distinct pending invalid_values for this data_type
            distinct_pending = db.session.execute(
                text("""
                    SELECT DISTINCT invalid_value 
                    FROM unmatched_data_review 
                    WHERE data_type = :dtype AND correction_status = 'pending'
                """),
                {"dtype": dtype}
            ).fetchall()
            
            for (val_raw,) in distinct_pending:
                if not val_raw:
                    continue
                val = val_raw.strip().lower()
                if val in valid_set:
                    # 1. Fetch the payloads for records that have non-empty row_data and need reintegration
                    records_with_data = db.session.execute(
                        text("""
                            SELECT table_name, row_data 
                            FROM unmatched_data_review 
                            WHERE data_type = :dtype 
                            AND invalid_value = :val_raw 
                            AND correction_status = 'pending'
                            AND row_data IS NOT NULL 
                            AND row_data != '' 
                            AND row_data != '{}'
                        """),
                        {"dtype": dtype, "val_raw": val_raw}
                    ).fetchall()
                    
                    master_rows_data = []
                    product_rows_data = []
                    for table_name, row_data in records_with_data:
                        if table_name == 'master_table':
                            master_rows_data.append(row_data)
                        elif table_name == 'product_master':
                            product_rows_data.append(row_data)
                            
                    # Perform bulk reintegration
                    bulk_reintegrate_master_table_raw(master_rows_data)
                    bulk_reintegrate_product_master_raw(product_rows_data)
                    
                    # 2. Bulk resolve all records in unmatched_data_review for this invalid_value
                    db.session.execute(
                        text("""
                            UPDATE unmatched_data_review 
                            SET correction_status = 'corrected' 
                            WHERE data_type = :dtype 
                            AND invalid_value = :val_raw 
                            AND correction_status = 'pending'
                        """),
                        {"dtype": dtype, "val_raw": val_raw}
                    )
                    logger.info(f"Auto-resolved {len(records_with_data)} records for {dtype} '{val_raw}' because it was found in Location Master")
                        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in auto_resolve_matched_records: {e}")

@unmatched_data_bp.route("/counts", methods=["GET"])
def get_counts():
    try:
        auto_resolve_matched_records()
        counts = db.session.query(
            UnmatchedDataReview.data_type,
            func.count(UnmatchedDataReview.review_id).label('count')
        ).filter(UnmatchedDataReview.correction_status == 'pending').group_by(UnmatchedDataReview.data_type).all()
        
        data = {"state": 0, "city": 0, "area": 0, "category": 0}
        for row in counts:
            data[row.data_type] = row.count
            
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        logger.error(f"Error fetching unmatched counts: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@unmatched_data_bp.route("/list", methods=["GET"])
def get_list():
    try:
        auto_resolve_matched_records()
        data_type = request.args.get('data_type')
        if not data_type:
            return jsonify({"status": "error", "message": "data_type parameter is required"}), 400
            
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit

        records = UnmatchedDataReview.query.filter_by(
            data_type=data_type, 
            correction_status='pending'
        ).limit(limit).offset(offset).all()

        total = UnmatchedDataReview.query.filter_by(
            data_type=data_type, 
            correction_status='pending'
        ).count()

        data_list = []
        for r in records:
            r_dict = r.to_dict()
            row_id = r.row_id
            table_name = r.table_name or "master_table"
            
            live_context = None
            if row_id:
                if table_name == "master_table":
                    live_row = db.session.execute(
                        text("SELECT business_name, address FROM master_table WHERE id = :id"),
                        {"id": row_id}
                    ).fetchone()
                    if live_row:
                        live_context = {
                            "business_name": live_row[0] or "—",
                            "address": live_row[1] or "—"
                        }
                elif table_name == "product_master":
                    live_row = db.session.execute(
                        text("SELECT product_name, brand FROM product_master WHERE id = :id"),
                        {"id": row_id}
                    ).fetchone()
                    if live_row:
                        live_context = {
                            "business_name": live_row[0] or "—",
                            "address": live_row[1] or "—"
                        }
            
            r_dict["live_context"] = live_context
            data_list.append(r_dict)

        return jsonify({
            "status": "success",
            "data": data_list,
            "total": total,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        logger.error(f"Error fetching unmatched list: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@unmatched_data_bp.route("/fix", methods=["POST"])
def manual_fix():
    try:
        req_data = request.get_json()
        if not req_data:
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

        review_id = req_data.get('id')
        new_value = req_data.get('new_value')

        if not review_id or new_value is None:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        # Start transaction
        review_record = UnmatchedDataReview.query.get(review_id)
        if not review_record:
            return jsonify({"status": "error", "message": "Review record not found"}), 404

        import json
        r_data = json.loads(review_record.row_data) if review_record.row_data else {}
        
        if r_data:
            dtype = review_record.data_type
            # Update the corrected field value in the payload
            if dtype == 'state':
                r_data['state'] = new_value
            elif dtype == 'city':
                r_data['city'] = new_value
            elif dtype == 'area':
                r_data['area'] = new_value
            elif dtype == 'category' and review_record.table_name == 'product_master':
                r_data['category_name'] = new_value
                
            # Re-insert row back into its original database table (or update if it already exists)
            if review_record.table_name == 'master_table':
                exists = db.session.execute(
                    text("SELECT 1 FROM master_table WHERE id = :id"),
                    {"id": r_data.get("id")}
                ).fetchone() is not None
                
                if exists:
                    db.session.execute(
                        text("""
                            UPDATE master_table 
                            SET business_name=:business_name, primary_phone=:primary_phone, secondary_phone=:secondary_phone,
                                other_phones=:other_phones, email=:email, address=:address, city=:city, state=:state,
                                area=:area, pincode=:pincode
                            WHERE id=:id
                        """),
                        {
                            "id": r_data.get("id"),
                            "business_name": r_data.get("business_name"),
                            "primary_phone": r_data.get("primary_phone"),
                            "secondary_phone": r_data.get("secondary_phone"),
                            "other_phones": r_data.get("other_phones"),
                            "email": r_data.get("email"),
                            "address": r_data.get("address"),
                            "city": r_data.get("city"),
                            "state": r_data.get("state"),
                            "area": r_data.get("area"),
                            "pincode": r_data.get("pincode")
                        }
                    )
                else:
                    db.session.execute(
                        text("""
                            INSERT INTO master_table (id, business_name, primary_phone, secondary_phone, other_phones, email, address, city, state, area, pincode)
                            VALUES (:id, :business_name, :primary_phone, :secondary_phone, :other_phones, :email, :address, :city, :state, :area, :pincode)
                        """),
                        {
                            "id": r_data.get("id"),
                            "business_name": r_data.get("business_name"),
                            "primary_phone": r_data.get("primary_phone"),
                            "secondary_phone": r_data.get("secondary_phone"),
                            "other_phones": r_data.get("other_phones"),
                            "email": r_data.get("email"),
                            "address": r_data.get("address"),
                            "city": r_data.get("city"),
                            "state": r_data.get("state"),
                            "area": r_data.get("area"),
                            "pincode": r_data.get("pincode")
                        }
                    )
            elif review_record.table_name == 'product_master':
                exists = db.session.execute(
                    text("SELECT 1 FROM product_master WHERE id = :id"),
                    {"id": r_data.get("id")}
                ).fetchone() is not None
                
                if exists:
                    db.session.execute(
                        text("""
                            UPDATE product_master
                            SET marketplace_name=:marketplace_name, asin=:asin, product_name=:product_name,
                                brand=:brand, category_name=:category_name, sub_category_name=:sub_category_name,
                                price=:price, list_price=:list_price
                            WHERE id=:id
                        """),
                        {
                            "id": r_data.get("id"),
                            "marketplace_name": r_data.get("marketplace_name"),
                            "asin": r_data.get("asin"),
                            "product_name": r_data.get("product_name"),
                            "brand": r_data.get("brand"),
                            "category_name": r_data.get("category_name"),
                            "sub_category_name": r_data.get("sub_category_name"),
                            "price": r_data.get("price"),
                            "list_price": r_data.get("list_price")
                        }
                    )
                else:
                    db.session.execute(
                        text("""
                            INSERT INTO product_master (id, marketplace_name, asin, product_name, brand, category_name, sub_category_name, price, list_price)
                            VALUES (:id, :marketplace_name, :asin, :product_name, :brand, :category_name, :sub_category_name, :price, :list_price)
                        """),
                        {
                            "id": r_data.get("id"),
                            "marketplace_name": r_data.get("marketplace_name"),
                            "asin": r_data.get("asin"),
                            "product_name": r_data.get("product_name"),
                            "brand": r_data.get("brand"),
                            "category_name": r_data.get("category_name"),
                            "sub_category_name": r_data.get("sub_category_name"),
                            "price": r_data.get("price"),
                            "list_price": r_data.get("list_price")
                        }
                    )

        review_record.correction_status = 'corrected'
        review_record.invalid_value = new_value 

        db.session.commit()
        return jsonify({"status": "success", "message": "Record corrected successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during manual fix: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@unmatched_data_bp.route("/add-to-location-master", methods=["POST"])
def add_to_location_master():
    try:
        req_data = request.get_json()
        if not req_data:
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

        review_id = req_data.get('id')
        if not review_id:
            return jsonify({"status": "error", "message": "Missing required field: id"}), 400

        # Load unmatched review record
        review_record = UnmatchedDataReview.query.get(review_id)
        if not review_record:
            return jsonify({"status": "error", "message": "Review record not found"}), 404

        # Parse row_data
        import json
        r_data = json.loads(review_record.row_data) if review_record.row_data else {}
        if not r_data:
            return jsonify({"status": "error", "message": "Raw record payload is empty"}), 400

        # Extract area, city, state from r_data
        area = r_data.get("area")
        city = r_data.get("city")
        state = r_data.get("state")

        if not state:
            return jsonify({"status": "error", "message": "Record state is missing or empty"}), 400
        
        area_clean = area.strip() if area else ""
        city_clean = city.strip() if city else ""
        state_clean = state.strip() if state else ""

        # Find state short code from Location_Master_India
        state_short = None
        state_res = db.session.execute(
            text("SELECT DISTINCT state_short_code FROM Location_Master_India WHERE LOWER(state_full_name) = LOWER(:state) OR LOWER(state_short_code) = LOWER(:state) LIMIT 1"),
            {"state": state_clean}
        ).fetchone()
        
        if state_res and state_res[0]:
            state_short = state_res[0]
        else:
            state_short = state_clean[:2].upper()

        # Check if this area/city/state combination already exists in Location_Master_India
        exists = db.session.execute(
            text("""
                SELECT 1 FROM Location_Master_India 
                WHERE LOWER(COALESCE(area_name, '')) = LOWER(:area) 
                AND LOWER(COALESCE(city_name, '')) = LOWER(:city) 
                AND LOWER(COALESCE(state_full_name, '')) = LOWER(:state) 
                LIMIT 1
            """),
            {
                "area": area_clean,
                "city": city_clean,
                "state": state_clean
            }
        ).fetchone() is not None

        if not exists:
            area_exact = area_clean if area_clean else None
            city_exact = city_clean if city_clean else None
            state_exact = state_clean
            # Insert into Location_Master_India
            db.session.execute(
                text("""
                    INSERT INTO Location_Master_India (area_name, city_name, state_full_name, state_short_code, country_name)
                    VALUES (:area, :city, :state, :state_short, 'India')
                """),
                {
                    "area": area_exact,
                    "city": city_exact,
                    "state": state_exact,
                    "state_short": state_short
                }
            )
            db.session.commit()
            logger.info(f"Successfully added location to Location_Master_India: area={area_exact}, city={city_exact}, state={state_exact}")

        # Now, perform the same re-integration of this business record back into master_table
        if review_record.table_name == 'master_table':
            exists_in_master = db.session.execute(
                text("SELECT 1 FROM master_table WHERE id = :id"),
                {"id": r_data.get("id")}
            ).fetchone() is not None
            
            if exists_in_master:
                db.session.execute(
                    text("""
                        UPDATE master_table 
                        SET business_name=:business_name, primary_phone=:primary_phone, secondary_phone=:secondary_phone,
                            other_phones=:other_phones, email=:email, address=:address, city=:city, state=:state,
                            area=:area, pincode=:pincode
                        WHERE id=:id
                    """),
                    {
                        "id": r_data.get("id"),
                        "business_name": r_data.get("business_name"),
                        "primary_phone": r_data.get("primary_phone"),
                        "secondary_phone": r_data.get("secondary_phone"),
                        "other_phones": r_data.get("other_phones"),
                        "email": r_data.get("email"),
                        "address": r_data.get("address"),
                        "city": r_data.get("city"),
                        "state": r_data.get("state"),
                        "area": r_data.get("area"),
                        "pincode": r_data.get("pincode")
                    }
                )
            else:
                db.session.execute(
                    text("""
                        INSERT INTO master_table (id, business_name, primary_phone, secondary_phone, other_phones, email, address, city, state, area, pincode)
                        VALUES (:id, :business_name, :primary_phone, :secondary_phone, :other_phones, :email, :address, :city, :state, :area, :pincode)
                    """),
                    {
                        "id": r_data.get("id"),
                        "business_name": r_data.get("business_name"),
                        "primary_phone": r_data.get("primary_phone"),
                        "secondary_phone": r_data.get("secondary_phone"),
                        "other_phones": r_data.get("other_phones"),
                        "email": r_data.get("email"),
                        "address": r_data.get("address"),
                        "city": r_data.get("city"),
                        "state": r_data.get("state"),
                        "area": r_data.get("area"),
                        "pincode": r_data.get("pincode")
                    }
                )

        # Mark review record as corrected
        review_record.correction_status = 'corrected'
        review_record.invalid_value = r_data.get(review_record.data_type)

        db.session.commit()
        return jsonify({"status": "success", "message": "Location added and record re-integrated successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during add_to_location_master: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
