import threading
import datetime
import os
import json

_state_lock = threading.Lock()

# Define backend log file location relative to this file
_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_logs_dir = os.path.join(_backend_dir, "logs")
_log_file_path = os.path.join(_logs_dir, "zepto_scraper.log")
_state_file_path = os.path.join(_backend_dir, "output", "zepto_last_run_state.json")

# Initial State Structure
_state = {
    "status": "idle",  # "idle" | "running" | "stopping"
    "task_id": None,
    "current_category": None,
    "current_subcategory": None,
    "current_pincode": None,
    "target_pincodes": "",
    "total_scraped": 0,
    "products_inserted": 0,
    "products_updated": 0,
    "products_skipped": 0,
    "categories_scraped": 0,
    "new_categories_mapped": 0,
    "new_categories": [],
    "new_products": [],
    "start_time": None,
    "end_time": None,
    "errors": [],
    "warnings": [],
    "logs": []  # List of dicts: {"timestamp": str, "message": str, "level": str}
}

def save_state_to_disk():
    """Saves key scraper state parameters to disk to persist across server restarts."""
    try:
        os.makedirs(os.path.dirname(_state_file_path), exist_ok=True)
        state_to_save = {
            "status": _state["status"],
            "task_id": _state["task_id"],
            "current_category": _state["current_category"],
            "current_subcategory": _state["current_subcategory"],
            "current_pincode": _state["current_pincode"],
            "target_pincodes": _state.get("target_pincodes", ""),
            "total_scraped": _state["total_scraped"],
            "products_inserted": _state["products_inserted"],
            "products_updated": _state["products_updated"],
            "products_skipped": _state["products_skipped"],
            "categories_scraped": _state.get("categories_scraped", 0),
            "new_categories_mapped": _state.get("new_categories_mapped", 0),
            "new_categories": list(_state.get("new_categories", [])),
            "new_products": list(_state.get("new_products", [])),
            "start_time": _state["start_time"],
            "end_time": _state["end_time"],
            "errors": list(_state.get("errors", [])),
            "warnings": list(_state.get("warnings", [])),
        }
        with open(_state_file_path, "w", encoding="utf-8") as f:
            json.dump(state_to_save, f, indent=2)
    except Exception:
        pass

def load_state_from_disk():
    """Loads key scraper state parameters from disk to restore status across server restarts."""
    global _state
    try:
        if os.path.exists(_state_file_path):
            with open(_state_file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for k, v in loaded.items():
                if k in _state:
                    _state[k] = v
            # Reset active status to idle if it was left running
            if _state["status"] in ("running", "stopping"):
                _state["status"] = "idle"
    except Exception:
        pass

def get_state():
    """Returns a copy of the structured state object."""
    with _state_lock:
        return {
            "status": _state["status"],
            "task_id": _state["task_id"],
            "current_category": _state["current_category"],
            "current_subcategory": _state["current_subcategory"],
            "current_pincode": _state["current_pincode"],
            "target_pincodes": _state.get("target_pincodes", ""),
            "total_scraped": _state["total_scraped"],
            "products_inserted": _state["products_inserted"],
            "products_updated": _state["products_updated"],
            "products_skipped": _state["products_skipped"],
            "categories_scraped": _state.get("categories_scraped", 0),
            "new_categories_mapped": _state.get("new_categories_mapped", 0),
            "new_categories": list(_state.get("new_categories", [])),
            "new_products": list(_state.get("new_products", [])),
            "start_time": _state["start_time"],
            "end_time": _state["end_time"],
            "errors_count": len(_state["errors"]),
            "warnings_count": len(_state["warnings"]),
            "errors": list(_state["errors"]),
            "warnings": list(_state["warnings"]),
        }

def set_running(running: bool):
    """Initializes or resets the state when the scraper starts/stops."""
    with _state_lock:
        if running:
            _state["status"] = "running"
            _state["task_id"] = None
            _state["start_time"] = datetime.datetime.now().isoformat()
            _state["end_time"] = None
            _state["current_category"] = None
            _state["current_subcategory"] = None
            _state["current_pincode"] = None
            _state["target_pincodes"] = ""
            _state["total_scraped"] = 0
            _state["products_inserted"] = 0
            _state["products_updated"] = 0
            _state["products_skipped"] = 0
            _state["categories_scraped"] = 0
            _state["new_categories_mapped"] = 0
            _state["new_categories"] = []
            _state["new_products"] = []
            _state["errors"] = []
            _state["warnings"] = []
            _state["logs"] = []
            
            # Truncate the file log on scraper startup
            try:
                os.makedirs(_logs_dir, exist_ok=True)
                with open(_log_file_path, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass
        else:
            _state["status"] = "idle"
            _state["end_time"] = datetime.datetime.now().isoformat()
        save_state_to_disk()

def request_stop():
    """Sets the status to stopping indicating stop has been requested."""
    with _state_lock:
        if _state["status"] == "running":
            _state["status"] = "stopping"
            save_state_to_disk()

def should_stop():
    """Checks if stop has been requested."""
    with _state_lock:
        return _state["status"] == "stopping"

def set_task_id(task_id):
    """Sets the active MySQL task ID in the state."""
    with _state_lock:
        _state["task_id"] = task_id
        save_state_to_disk()

def sync_task_to_db():
    """Updates the task status and total scraped items in MySQL DB."""
    with _state_lock:
        task_id = _state["task_id"]
        if not task_id:
            return
        status = _state["status"]
        total_scraped = _state["total_scraped"]
        current_pincode = _state["current_pincode"]
        current_category = _state["current_category"]
        current_subcategory = _state["current_subcategory"]
        
    def _run_sync():
        try:
            from app import app
            from extensions import db
            from model.scraper_task import ScraperTask
            with app.app_context():
                task = db.session.get(ScraperTask, task_id)
                if task:
                    task.total_found = total_scraped
                    if status == "running":
                        task.status = f"Pincode {current_pincode}: scraping {current_category} > {current_subcategory}"
                    db.session.commit()
        except Exception:
            pass
            
    import threading
    threading.Thread(target=_run_sync, daemon=True).start()

def set_current_state(category=None, subcategory=None, pincode=None):
    """Updates the scraper's active progress coordinates."""
    with _state_lock:
        if category is not None:
            _state["current_category"] = category
        if subcategory is not None:
            _state["current_subcategory"] = subcategory
        if pincode is not None:
            _state["current_pincode"] = pincode
        save_state_to_disk()
    sync_task_to_db()

def increment_scraped(count: int = 1):
    """Increments the total count of products scraped."""
    with _state_lock:
        _state["total_scraped"] += count
        save_state_to_disk()
    sync_task_to_db()

def increment_stats(inserted: int = 0, updated: int = 0, skipped: int = 0):
    """Increments the count of inserted, updated, and skipped items."""
    with _state_lock:
        _state["products_inserted"] += inserted
        _state["products_updated"] += updated
        _state["products_skipped"] += skipped
        save_state_to_disk()
    sync_task_to_db()

def increment_categories_scraped(count: int = 1):
    """Increments the total count of categories scraped."""
    with _state_lock:
        _state["categories_scraped"] += count
        save_state_to_disk()
    sync_task_to_db()

def increment_new_categories_mapped(count: int = 1):
    """Increments the total count of newly mapped categories."""
    with _state_lock:
        _state["new_categories_mapped"] += count
        save_state_to_disk()
    sync_task_to_db()

def set_target_pincodes(pincodes_str: str):
    """Sets the targeted pincodes list in the state."""
    with _state_lock:
        _state["target_pincodes"] = pincodes_str
        save_state_to_disk()
    sync_task_to_db()

def add_new_categories(categories_list: list):
    """Appends newly mapped categories to the state list, capping at 100 entries."""
    if not categories_list:
        return
    with _state_lock:
        if "new_categories" not in _state:
            _state["new_categories"] = []
        _state["new_categories"].extend(categories_list)
        # Cap at 100 items
        if len(_state["new_categories"]) > 100:
            _state["new_categories"] = _state["new_categories"][-100:]
        save_state_to_disk()
    sync_task_to_db()

def add_new_products(products_list: list):
    """Appends newly inserted products to the state list, capping at 100 entries."""
    if not products_list:
        return
    with _state_lock:
        if "new_products" not in _state:
            _state["new_products"] = []
        _state["new_products"].extend(products_list)
        # Cap at 100 items
        if len(_state["new_products"]) > 100:
            _state["new_products"] = _state["new_products"][-100:]
        save_state_to_disk()
    sync_task_to_db()

def add_log_entry(message: str, level: str = "INFO"):
    """Adds a log entry, limiting the history to 500 records to manage memory."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": timestamp,
        "message": message,
        "level": level.upper()
    }
    with _state_lock:
        _state["logs"].append(entry)
        # Cap log history at 500 entries
        if len(_state["logs"]) > 500:
            _state["logs"].pop(0)
        
        # Track errors and warnings separately for quick access
        if level.upper() == "ERROR":
            _state["errors"].append(f"[{timestamp}] {message}")
            if len(_state["errors"]) > 100:
                _state["errors"].pop(0)
        elif level.upper() == "WARNING":
            _state["warnings"].append(f"[{timestamp}] {message}")
            if len(_state["warnings"]) > 100:
                _state["warnings"].pop(0)

    # Append the log to the disk file
    try:
        os.makedirs(_logs_dir, exist_ok=True)
        with open(_log_file_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level.upper()}] {message}\n")
    except Exception:
        pass

def get_logs(limit: int = 100):
    """Retrieves the latest logs up to the specified limit."""
    with _state_lock:
        # Return a copy of logs up to the limit from the end
        return list(_state["logs"][-limit:])

# Load any saved last scrape task state on startup
load_state_from_disk()
