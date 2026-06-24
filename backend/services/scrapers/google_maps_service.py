import os
import re
import time
import uuid
from urllib.parse import quote_plus
from dataclasses import dataclass, field
from typing import Optional
from pydantic import BaseModel, field_validator
import pandas as pd
import mysql.connector
from mysql.connector import Error
from playwright.sync_api import sync_playwright
from extensions import db
from model.scraper_task import ScraperTask 

def _log_to_file(task_id, message, level="INFO"):
    """Appends logs to a local file for terminal streaming."""
    try:
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        log_dir = os.path.join(backend_dir, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file_path = os.path.join(log_dir, f"google_map_task_{task_id}.log")
        
        timestamp = time.strftime("%H:%M:%S")
        log_line = f"{timestamp} | {level} | {message}\n"
        print(log_line.strip())
        
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"Log Error: {e}")

def transfer_to_master_table(task_id):
    """ETL script to move data from google_Map to master_table."""
    _log_to_file(task_id, "[SYSTEM] Starting ETL transfer to master_table...", "INFO")
    connection = None
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            port=os.getenv('DB_PORT')
        )
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Fetch recently scraped rows
            # We can select all that are not in master_table or just use ON DUPLICATE KEY UPDATE
            cursor.execute("SELECT name, address, website, phone_number, reviews_count, reviews_average, category, city, state, area FROM google_Map")
            rows = cursor.fetchall()
            
            _log_to_file(task_id, f"Found {len(rows)} total records in google_Map to process.", "INFO")
            
            insert_query = """
            INSERT INTO master_table (
                global_business_id, business_name, address, website_url, primary_phone, 
                reviews, ratings, business_category, city, state, area, data_source
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Google Maps')
            ON DUPLICATE KEY UPDATE
                website_url = VALUES(website_url),
                primary_phone = VALUES(primary_phone),
                reviews = VALUES(reviews),
                ratings = VALUES(ratings)
            """
            
            success_count = 0
            for r in rows:
                name, addr, web, phone, rev_c, rev_a, cat, city, state, area = r
                if not name: continue
                # Generate a unique business ID
                b_id = str(uuid.uuid4())
                try:
                    cursor.execute(insert_query, (b_id, name, addr, web, phone, rev_c, rev_a, cat, city, state, area))
                    success_count += 1
                except Exception as ex:
                    # Ignore duplicate key errors if global_business_id is unique, 
                    # but if there are other unique constraints, skip
                    pass
                    
            connection.commit()
            _log_to_file(task_id, f"✅ Successfully synced {success_count} records to master_table.", "SUCCESS")
    except Error as e:
        _log_to_file(task_id, f"MySQL Error during ETL: {e}", "ERROR")
    finally:
        if connection and connection.is_connected():
            connection.close()

def safe_filename(name: str) -> str:
    """Sanitize filename to remove/replace invalid characters."""
    name = name.strip().replace(' ', '_')
    return re.sub(r'[^\w\-]', '_', name)

class Business(BaseModel):
    """Pydantic model for business data validation"""
    name: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    phone_number: Optional[str] = None
    reviews_count: Optional[int] = None
    reviews_average: Optional[float] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    area: Optional[str] = None

    @field_validator('reviews_average')
    @classmethod
    def validate_rating(cls, v):
        if v is not None and (v < 0 or v > 5):
            raise ValueError('Rating must be between 0 and 5')
        return v

@dataclass
class BusinessList:
    business_list: list[Business] = field(default_factory=list)
    save_at: str = 'output'

    def dataframe(self):
        return pd.DataFrame([b.model_dump() for b in self.business_list])

    def save_to_excel(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(f"{self.save_at}/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(f"{self.save_at}/{filename}.csv", index=False)

    def save_to_mysql(self):
        """Save data to MySQL database using credentials from .env"""
        connection = None
        try:
            # print("Saving to DB:", os.getenv('DB_HOST'), os.getenv('DB_USER'), os.getenv('DB_NAME'))
            connection = mysql.connector.connect(
                host=os.getenv('DB_HOST'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('DB_NAME'),
                port=os.getenv('DB_PORT')
            )

            if connection.is_connected():
                cursor = connection.cursor()
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS google_Map (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(500),
                    address TEXT,
                    website VARCHAR(500),
                    phone_number VARCHAR(100),
                    reviews_count INT,
                    reviews_average FLOAT,
                    category VARCHAR(255),
                    subcategory VARCHAR(500),
                    city VARCHAR(100),
                    state VARCHAR(100),
                    area VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_business (name,address(255))
                )""")

                insert_query_complete_entries = """
                INSERT INTO google_Map (
                    name, address, website, phone_number,
                    reviews_count, reviews_average, category,
                    subcategory, city, state, area
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    website = VALUES(website),
                    phone_number = VALUES(phone_number),
                    reviews_count = VALUES(reviews_count),
                    reviews_average = VALUES(reviews_average),
                    subcategory = VALUES(subcategory),
                    area = VALUES(area)
                """

                for business in self.business_list:
                    cursor.execute(insert_query_complete_entries, (
                        business.name,
                        business.address,
                        business.website,
                        business.phone_number,
                        business.reviews_count,
                        business.reviews_average,
                        business.category,
                        business.subcategory,
                        business.city,
                        business.state,
                        business.area
                    ))

                connection.commit()
                print(f"✅ Successfully saved {len(self.business_list)} businesses to MySQL")

        except Error as e:
            print(f" MySQL Error: {e}")
        finally:
            if connection and connection.is_connected():
                connection.close()

def run_google_maps_scraper(task_id, app, search_list=None):
    """
    Runs the Playwright scraper.
    Note: We pass 'app' explicitly to handle Flask context inside the thread.
    """
    with app.app_context():
        task = ScraperTask.query.get(task_id)
        if not task: return

        # Initialize log file
        _log_to_file(task_id, "[SYSTEM] Initializing Google Maps Automation Engine...", "INFO")

        if not search_list:
            # Search query parsing logic
            search_query = task.search_query
            parts = search_query.split(' in ')
            cat = parts[0].strip() if len(parts) > 0 else search_query
            location_parts = parts[1].split(',') if len(parts) > 1 else [task.location]
            city = location_parts[0].strip()
            state = location_parts[1].strip() if len(location_parts) > 1 else ""
            
            search_list = [{"category": cat, "city": city, "state": state}]

        _log_to_file(task_id, f"[CONFIG] Scrape targets: {search_list}", "INFO")

        start_from_index = task.last_index if task.last_index else 0
        task.status = "RUNNING"
        task.should_stop = False
        db.session.commit()

        with sync_playwright() as p:
            browser = None
            try:
                _log_to_file(task_id, "Launching browser in background (headless=True)...", "INFO")
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )
                page = context.new_page()

                for search_for_index, search_item in enumerate(search_list):
                    if search_for_index < start_from_index: continue

                    # --- STOP CHECK ---
                    db.session.refresh(task)
                    if task.should_stop:
                        task.status = "STOPPED"
                        db.session.commit()
                        return

                    category = search_item.get('category', '')
                    city = search_item.get('city', '')
                    state = search_item.get('state', '')
                    
                    # Phase 1: Collect Links
                    _log_to_file(task_id, f"Phase 1: Discovering listings for {category} in {city}, {state}...", "SYSTEM")
                    encoded_query = quote_plus(f"{category} in {city} {state}".strip())
                    target_url = f"https://www.google.com/maps/search/{encoded_query}?hl=en"
                    
                    page.goto(target_url, timeout=60000)
                    
                    # Consent and Scroll
                    try:
                        page.wait_for_selector('div[role="feed"]', timeout=15000)
                    except: continue

                    total_scrolls = 15
                    for scroll_idx in range(total_scrolls): # Scroll for links
                        if task.should_stop: break
                        page.mouse.wheel(0, 5000)
                        page.wait_for_timeout(1000)
                        
                        # Calculate progress for scrolling phase (0% to 80%)
                        scroll_progress = int(((scroll_idx + 1) / total_scrolls) * 80)
                        task.progress = scroll_progress
                        db.session.commit()
                        
                        if scroll_idx % 2 == 0:
                            _log_to_file(task_id, f"Phase 1: Scrolling through Google Maps results... {scroll_progress}%", "INFO")

                    # Find all link elements
                    all_links = page.locator('a[href*="/maps/place/"]').all()
                    
                    # Deduplicate and extract name from aria-label
                    extracted_data = {}
                    for link in all_links:
                        try:
                            href = link.get_attribute('href')
                            if not href: continue
                            # aria-label contains the business name in Google Maps
                            name = link.get_attribute('aria-label')
                            if name and href not in extracted_data:
                                extracted_data[href] = name
                        except:
                            continue
                            
                    business_urls = list(extracted_data.keys())
                    
                    _log_to_file(task_id, f"Found {len(business_urls)} links. Starting Phase 2 (Fast Extraction)...", "SUCCESS")
                    business_list = BusinessList()

                    # Phase 2: Fast Detail Extraction (No extra page loads needed!)
                    for i, url in enumerate(business_urls):
                        # --- GRANULAR STOP CHECK ---
                        db.session.refresh(task)
                        if task.should_stop:
                            task.status = "STOPPED"
                            task.last_index = search_for_index
                            _log_to_file(task_id, "Stop signal received. Saving progress and halting.", "WARNING")
                            business_list.save_to_mysql()
                            db.session.commit()
                            return

                        name = extracted_data[url]
                        data = Business(
                            name=name, category=category, city=city, state=state,
                            address=url # Fallback parsing
                        )
                        business_list.business_list.append(data)
                        
                        if (i+1) % 5 == 0 or (i+1) == len(business_urls):
                            _log_to_file(task_id, f"Phase 2: Processed {i+1}/{len(business_urls)}: {name[:30]}...", "INFO")

                        # --- SYNC PROGRESS ---
                        task.total_found = i + 1
                        # Phase 2 progress (80% to 95%)
                        task.progress = 80 + int(((i + 1) / len(business_urls)) * 15)
                        db.session.commit()

                    # Batch Save
                    _log_to_file(task_id, f"Saving {len(business_list.business_list)} records to google_Map...", "SYSTEM")
                    business_list.save_to_mysql()
                    task.last_index = search_for_index + 1
                    db.session.commit()

                # Phase 3: Move to Master Table
                transfer_to_master_table(task_id)

                task.status = "COMPLETED"
                task.progress = 100
                db.session.commit()
                _log_to_file(task_id, "✅ Google Maps Scraping COMPLETE!", "SUCCESS")

            except Exception as e:
                _log_to_file(task_id, f"Scraper Error: {e}", "ERROR")
                task.status = "ERROR"
                task.error_message = str(e)
                db.session.commit()
            finally:
                if browser: browser.close()