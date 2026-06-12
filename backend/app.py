import os
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import verify_jwt_in_request
from dotenv import load_dotenv

from config import Config
from extensions import db, jwt, cors, mail, migrate

# --- Import Models ---
from model.user import User
from model.scraper_task import ScraperTask
from model.googlemap_data import GoogleMapData 
from model.item_csv_model import ItemData
from model.master_table_model import MasterTable
from model.upload_master_reports_model import UploadReport
from model.listing_master import ListingMaster
from model.heyplaces import HeyPlaces
from model.location_master import LocationMaster 

# Existing Models
from model.asklaila import Asklaila
from model.atm import ATM
from model.bank import Bank
from model.college_dunia import CollegeDunia
from model.justdial import JustDial
from model.magicpin import MagicPin
from model.nearbuy import NearBuy
from model.pinda import Pinda
from model.post_office import PostOffice
from model.schoolgis import SchoolGIS
from model.shiksha import Shiksha
from model.yellow_pages import YellowPages
from model.google_map_scrape import GoogleMapScrape
from model.robust_gdrive_etl_v2 import start_background_etl
from model.unmatched_data_review import UnmatchedDataReview

# --- Product Models ---
from model.product_model.amazon_product import AmazonProduct 
from model.product_model.bigbasket_product_model import BigBasket
from model.product_model.additional_products import BigBasketNew, Zepto

# --- Dynamic Categories Mapping Master Models ---
from model.master_category import MasterCategory
from model.platform_category_mapping import PlatformCategoryMapping
from model.category_mapping_history import CategoryMappingHistory
from model.category_mapping_platforms import CategoryMappingPlatform
from model.category_mapping_synonyms import CategoryMappingSynonym

# --- Import Blueprints ---
from routes.auth_route import auth_bp
from routes.scraper_routes import scraper_bp
from routes.amazon_routes import amazon_api_bp
from routes.dmart_routes import dmart_api_bp
from routes.zepto_routes import zepto_api_bp
from routes.googlemap import googlemap_bp 
from routes.master_table import master_table_bp
from routes.upload_product_csv import product_csv_bp
from routes.upload_item_csv import item_csv_bp



# Listing & Product Blueprints
from routes.items_data import item_bp
from routes.item_csv_download import item_csv_bp as item_csv_download_bp
from routes.item_duplicate import item_duplicate_bp
from routes.upload_others_csv import upload_others_csv_bp
from routes.listing_master_route import listing_master_bp
from routes.location_master_route import location_master_bp 

# Sub-folder listing routes
from routes.listing_routes.upload_asklaila_route import asklaila_bp
from routes.listing_routes.upload_atm_route import atm_bp
from routes.listing_routes.upload_bank_route import bank_bp
from routes.listing_routes.upload_college_dunia_route import college_dunia_bp
from routes.listing_routes.upload_freelisting_route import freelisting_bp
from routes.listing_routes.upload_google_map_route import google_map_bp as gmap_upload_bp
from routes.listing_routes.upload_google_map_scrape_route import google_map_scrape_bp
from routes.listing_routes.upload_heyplaces_route import heyplaces_bp
from routes.listing_routes.upload_justdial_route import justdial_bp
from routes.listing_routes.upload_magicpin_route import magicpin_bp
from routes.listing_routes.upload_nearbuy_route import nearbuy_bp
from routes.listing_routes.upload_pinda_route import pinda_bp
from routes.listing_routes.upload_post_office_route import post_office_bp
from routes.listing_routes.upload_schoolgis_route import schoolgis_bp
from routes.listing_routes.upload_shiksha_route import shiksha_bp
from routes.listing_routes.upload_yellow_pages_route import yellow_pages_bp

# Product sub-routes
from routes.product_routes.upload_amazon_products_route import amazon_bp as amazon_upload_bp
from routes.product_routes.upload_vivo_route import vivo_bp
from routes.product_routes.upload_big_basket_route import bigbasket_bp
from routes.product_routes.upload_blinkit_route import blinkit_bp
from routes.product_routes.upload_dmart_route import dmart_bp
from routes.product_routes.upload_flipkart_products_route import flipkart_bp
from routes.product_routes.upload_india_mart_route import indiamart_bp
from routes.product_routes.upload_jio_mart_route import jiomart_bp
from routes.product_routes.upload_zepto_route import zepto_bp
from routes.product_master_route import product_master_bp
# New Dashboard Blueprints
from routes.gdrive_etl_routes.validation_dashboard import validation_dashboard_bp
from routes.gdrive_etl_routes.dashboard_stats import dashboard_bp
from routes.report_aggregate_routes import report_aggregate_bp
from routes.unmatched_data_routes import unmatched_data_bp
from routes.listing_upload_routes import listing_upload_bp
from routes.product_report_routes import product_report_bp

# --- Dynamic Categories Mapping Master Blueprints ---
from routes.master_category_routes import master_category_bp
from routes.category_mapping_routes import category_mapping_bp

# --- Initialize App ---
load_dotenv(override=True)
app = Flask(__name__)
app.config.from_object(Config)

# Init extensions
db.init_app(app)
migrate.init_app(app, db)
jwt.init_app(app)
cors.init_app(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True) 
mail.init_app(app)

with app.app_context():
    try:
        db.session.execute(db.text('SELECT 1'))
        db_host = os.getenv('DB_HOST', 'localhost')
        try:
            print(f"✅ DATABASE CONNECTION: SUCCESS (Connected to {db_host})")
        except UnicodeEncodeError:
            print(f"[SUCCESS] DATABASE CONNECTION: Connected to {db_host}")
    except Exception as e:
        try:
            print(f"❌ DATABASE CONNECTION: FAILED! Error: {e}")
        except UnicodeEncodeError:
            print(f"[FAILED] DATABASE CONNECTION! Error: {e}")

    db.create_all()
  
  #Migration Logic...

    try:
        from utils.db_migrations import run_pending_migrations
        try:
            print("🔄 Running Database Migrations...")
        except UnicodeEncodeError:
            print("Running Database Migrations...")
        run_pending_migrations(app)
    except ImportError:
        pass
    finally:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        finally:
            db.session.remove()

# --- GLOBAL JWT PROTECTION ---
PUBLIC_ROUTES = [
    "/",
    "/api/auth/signup",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/forgot-password",
    "/api/auth/verify-otp",
    "/api/auth/reset-password",
    "/health",
    "/master_table/list",
    "/master-dashboard-stats",
    "/atm/fetch-data",
    "/bank/fetch-data",
    "/asklaila/fetch-data",
    "/college-dunia/fetch-data",
    "/google-map/fetch-data",
    "/listing-master",
    "/complete-data",
    "/heyplaces/fetch-data",
    "/justdial/fetch-data",
    "/magicpin/fetch-data",
    "/nearbuy/fetch-data",
    "/pinda/fetch-data",
    "/post-office/fetch-data",
    "/schoolgis/fetch-data",
    "/shiksha/fetch-data",
    "/yellow-pages/fetch-data",
    "/google-map-scrape/fetch-data",
    "/amazon/fetch-data",
    "/big-basket/fetch-data",
    "/location-master/fetch-data",
    "/validation/dashboard",
    "/product-master/fetch-data",
    "/api/report/aggregate",
    "/api/report/health",
    "/api/googlemap_data",
    "/api/unmatched/counts",
    "/api/unmatched/list",
    "/api/unmatched/fix",
    "/api/listing-upload",
    "/api/listing-upload/history",
    "/api/listing-upload/pending",
    "/api/product-report/top-products",
    "/api/product-report/dmart/data",
    "/api/product-report/indiamart/data",
    "/api/product-report/bigbasket/data",
    "/api/product-report/zepto/data",
    "/api/product-report/blinkit/data",
    "/api/product-report/amazon/data",
    "/api/product-report/mapping/blinkit",
    "/api/product-report/mapping/bigbasket",
    "/api/product-report/mapping/dmart",
    "/api/product-report/mapping/indiamart",
    "/api/product-report/mapping/zepto",
    "/api/scrape_dmart",
    "/api/scrape_amazon",
    "/api/master-categories",
    "/api/category-mapping",
    "/api/category-mapping/stats",
    "/api/category-mapping/pending",
    "/api/category-mapping/sync",
    "/api/category-mapping/history",
    "/api/category-mapping/settings/platforms",
    "/api/category-mapping/settings/synonyms",
    "/api/scrape_zepto",
]

@app.before_request
def protect_all_routes():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight successful"}), 200

    normalized_path = request.path.rstrip('/')
    public_paths = [route.rstrip('/') for route in PUBLIC_ROUTES]

    # Bypass for whitelist, fetch-data routes, or listing-upload / product-report / source- / tasks / master-categories / category-mapping prefixes
    if (normalized_path in public_paths or 
        normalized_path.endswith('/fetch-data') or 
        normalized_path.startswith('/api/listing-upload') or 
        normalized_path.startswith('/api/product-report') or 
        normalized_path.startswith('/api/report/source-') or 
        normalized_path.startswith('/api/master-categories') or
        normalized_path.startswith('/api/category-mapping') or
        normalized_path.startswith('/api/tasks')):
        return None

    try:
        verify_jwt_in_request()
    except Exception as e:
        print(f"❌ JWT REJECTED for {request.path}: {str(e)}")
        return jsonify({"message": "Missing or invalid token", "error": str(e)}), 401

# --- Register Blueprints ---
# As requested, we follow the working file's lead: no manual '/api' addition here 
# if Nginx handles it.
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(scraper_bp, url_prefix="/api")
app.register_blueprint(amazon_api_bp, url_prefix="/api")
app.register_blueprint(dmart_api_bp, url_prefix="/api")
app.register_blueprint(googlemap_bp, url_prefix='/api')
app.register_blueprint(master_table_bp)
app.register_blueprint(product_csv_bp)
app.register_blueprint(item_csv_bp)
app.register_blueprint(item_bp, url_prefix="/items")
app.register_blueprint(item_csv_download_bp)
app.register_blueprint(item_duplicate_bp)
app.register_blueprint(upload_others_csv_bp)
app.register_blueprint(listing_master_bp, url_prefix="/api")
app.register_blueprint(validation_dashboard_bp, url_prefix="/validation")
app.register_blueprint(dashboard_bp, url_prefix="/stats")
app.register_blueprint(product_master_bp, url_prefix="/product-master")
app.register_blueprint(report_aggregate_bp)
app.register_blueprint(unmatched_data_bp, url_prefix="/api/unmatched")
app.register_blueprint(listing_upload_bp, url_prefix="/api/listing-upload")
app.register_blueprint(product_report_bp, url_prefix="/api/product-report")
app.register_blueprint(zepto_api_bp, url_prefix="/api")

# --- Dynamic Categories Mapping Master Blueprints ---
app.register_blueprint(master_category_bp, url_prefix="/api/master-categories")
app.register_blueprint(category_mapping_bp, url_prefix="/api/category-mapping")

# --- Register Listing & Product Blueprints (Batch) ---
blueprints_listing = [
    (asklaila_bp, "/asklaila"), (atm_bp, "/atm"), (bank_bp, "/bank"),
    (college_dunia_bp, "/college-dunia"), (freelisting_bp, "/freelisting"),
    (gmap_upload_bp, "/google-map"), (google_map_scrape_bp, "/google-map-scrape"),
    (heyplaces_bp, "/heyplaces"), (justdial_bp, "/justdial"), (magicpin_bp, "/magicpin"),
    (nearbuy_bp, "/nearbuy"), (pinda_bp, "/pinda"), (post_office_bp, "/post-office"),
    (schoolgis_bp, "/schoolgis"), (shiksha_bp, "/shiksha"), (yellow_pages_bp, "/yellow-pages"),
    (amazon_upload_bp, "/amazon"), (vivo_bp, "/vivo"), (blinkit_bp, "/blinkit"),
    (zepto_bp, "/zepto"),
    (dmart_bp, "/dmart"), (flipkart_bp, "/flipkart"), (indiamart_bp, "/india-mart"),
    (jiomart_bp, "/jio-mart"), (bigbasket_bp, "/big-basket"),
    (location_master_bp, "/location-master")
]

for bp, prefix in blueprints_listing:
    # Standardizing under /api to match frontend expectations
    app.register_blueprint(bp, url_prefix=f"/api{prefix}")

@app.route('/')
def index():
    return jsonify({"message": "Flask API is running! Clean and Modular."})

if __name__ == '__main__':
    run_server_only = "--runserver" in sys.argv
    
    ingestor = None
    if run_server_only:
        print("[SERVER] Mode: API Server Only (Background ETL disabled for manual run)")
    else:
        print("[ALL-IN-ONE] Mode: All-in-One (Starting Background Sync Tool...)")
        ingestor = start_background_etl()
        
        # Daemonize the ingestor thread if possible
        try:
            if hasattr(ingestor, 'daemon'):
                ingestor.daemon = True
        except Exception:
            pass

    def shutdown():
        try:
            print('\n🛑 Shutdown requested...')
        except UnicodeEncodeError:
            print('\n[SHUTDOWN] Shutdown requested...')
        if ingestor:
            ingestor.shutdown()
        sys.argv = [sys.argv[0]] # clean args for safe shutdown
        sys.exit(0)

    # --- Run Flask standard server ---
    try:
        try:
            print("Starting Flask standard server on port 8001. Press CTRL+C to quit.")
        except UnicodeEncodeError:
            print("Starting Flask standard server on port 8001. Press CTRL+C to quit.")
        app.run(host='0.0.0.0', port=8001, debug=False) 
    except KeyboardInterrupt:
        shutdown()

@app.route('/health')
def health_check():
    return jsonify({"status": "ok", "message": "Backend is reachable"})
