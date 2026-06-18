import threading
import datetime
import os

_state_lock = threading.Lock()

# Define backend log file location relative to this file
_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_logs_dir = os.path.join(_backend_dir, "logs")
_log_file_path = os.path.join(_logs_dir, "zepto_scraper.log")

# Initial State Structure
_state = {
    "status": "idle",  # "idle" | "running" | "stopping"
    "current_category": None,
    "current_subcategory": None,
    "current_pincode": None,
    "total_scraped": 0,
    "start_time": None,
    "end_time": None,
    "errors": [],
    "warnings": [],
    "logs": []  # List of dicts: {"timestamp": str, "message": str, "level": str}
}

def get_state():
    """Returns a copy of the structured state object."""
    with _state_lock:
        return {
            "status": _state["status"],
            "current_category": _state["current_category"],
            "current_subcategory": _state["current_subcategory"],
            "current_pincode": _state["current_pincode"],
            "total_scraped": _state["total_scraped"],
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
            _state["start_time"] = datetime.datetime.now().isoformat()
            _state["end_time"] = None
            _state["current_category"] = None
            _state["current_subcategory"] = None
            _state["current_pincode"] = None
            _state["total_scraped"] = 0
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

def request_stop():
    """Sets the status to stopping indicating stop has been requested."""
    with _state_lock:
        if _state["status"] == "running":
            _state["status"] = "stopping"

def should_stop():
    """Checks if stop has been requested."""
    with _state_lock:
        return _state["status"] == "stopping"

def set_current_state(category=None, subcategory=None, pincode=None):
    """Updates the scraper's active progress coordinates."""
    with _state_lock:
        if category is not None:
            _state["current_category"] = category
        if subcategory is not None:
            _state["current_subcategory"] = subcategory
        if pincode is not None:
            _state["current_pincode"] = pincode

def increment_scraped(count: int = 1):
    """Increments the total count of products scraped."""
    with _state_lock:
        _state["total_scraped"] += count

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
