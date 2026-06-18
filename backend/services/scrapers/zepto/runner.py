import asyncio
import threading
import traceback
import sys
import os

from . import zepto_scraper
from .state import set_running, add_log_entry, get_state, request_stop
from . import logger

_scraper_thread = None
_thread_lock = threading.Lock()

def _run_scraper_thread(category, pincodes):
    # Create and set a new event loop for this background thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    add_log_entry("[SYSTEM] Isolated scraper thread and asyncio event loop initialized.", "INFO")
    
    try:
        # Prepare arguments list to pass programmatically to zepto_scraper's main
        args_list = []
        if category:
            args_list.extend(["--category", category])
        if pincodes:
            args_list.extend(["--pincodes", pincodes])
            
        # Execute the main async scraper function
        loop.run_until_complete(zepto_scraper.main(args_list))
        
        add_log_entry("[SYSTEM] Scraper completed execution successfully.", "INFO")
    except Exception as e:
        error_msg = f"[SYSTEM] Scraper encountered an error: {str(e)}\n{traceback.format_exc()}"
        add_log_entry(error_msg, "ERROR")
    finally:
        # Cleanup
        try:
            loop.close()
        except Exception as le:
            add_log_entry(f"[SYSTEM] Error closing asyncio event loop: {str(le)}", "WARNING")
            
        logger.stop_intercepting()
        set_running(False)
        add_log_entry("[SYSTEM] Scraper thread terminated, resources cleaned up.", "INFO")

def start_scraper(category: str, pincodes: str):
    """Starts the scraper thread if not already running."""
    global _scraper_thread
    with _thread_lock:
        current_state = get_state()
        if current_state["status"] != "idle":
            return False, "Scraper is already active or stopping."
            
        set_running(True)
        add_log_entry(f"[SYSTEM] Starting scraper run with category: '{category or 'ALL'}', pincodes: '{pincodes or 'DEFAULT'}'.", "INFO")
        
        _scraper_thread = threading.Thread(
            target=_run_scraper_thread,
            args=(category, pincodes),
            name="ZeptoScraperBackgroundThread"
        )
        _scraper_thread.daemon = True
        
        # Start capturing stdout print calls from this thread
        logger.start_intercepting(_scraper_thread)
        _scraper_thread.start()
        
        return True, "Scraper started successfully."

def stop_scraper():
    """Triggers the stopping sequence."""
    with _thread_lock:
        current_state = get_state()
        if current_state["status"] != "running":
            return False, "Scraper is not running."
            
        request_stop()
        add_log_entry("[SYSTEM] Stop request received. Initiating graceful shutdown...", "WARNING")
        return True, "Stop signal transmitted to scraper."
