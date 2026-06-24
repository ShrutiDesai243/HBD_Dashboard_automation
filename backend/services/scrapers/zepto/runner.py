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

def _update_task_db(task_id, status, progress=None, error_msg=None):
    """Safely updates ScraperTask record in DB."""
    if not task_id:
        return
    try:
        from app import app
        from extensions import db
        from model.scraper_task import ScraperTask
        from datetime import datetime
        
        with app.app_context():
            task = db.session.get(ScraperTask, task_id)
            if task:
                task.status = status
                if progress is not None:
                    task.progress = progress
                
                # Format Stopped time in error_message column
                stop_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if error_msg:
                    task.error_message = f"Stopped: {stop_time_str} | Error: {error_msg}"
                else:
                    task.error_message = f"Stopped: {stop_time_str}"
                
                from .state import get_state
                current_state = get_state()
                task.total_found = current_state.get("total_scraped", 0)
                
                db.session.commit()
    except Exception as e:
        print(f"[!] Failed to update ScraperTask {task_id}: {e}")

def _run_scraper_thread(category, pincodes, task_id, resume):
    # Create and set a new event loop for this background thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    from .state import set_task_id
    set_task_id(task_id)
    
    add_log_entry("[SYSTEM] Isolated scraper thread and asyncio event loop initialized.", "INFO")
    
    try:
        # Prepare arguments list to pass programmatically to zepto_scraper's main
        args_list = []
        if category:
            args_list.extend(["--category", category])
        if pincodes:
            args_list.extend(["--pincodes", pincodes])
        if resume:
            args_list.append("--resume")
            
        # Execute the main async scraper function
        loop.run_until_complete(zepto_scraper.main(args_list))
        
        add_log_entry("[SYSTEM] Scraper completed execution successfully.", "INFO")
        _update_task_db(task_id, status="COMPLETED", progress=100)
    except Exception as e:
        error_msg = f"[SYSTEM] Scraper encountered an error: {str(e)}\n{traceback.format_exc()}"
        add_log_entry(error_msg, "ERROR")
        _update_task_db(task_id, status="ERROR", error_msg=str(e))
    finally:
        # Cleanup
        try:
            loop.close()
        except Exception as le:
            add_log_entry(f"[SYSTEM] Error closing asyncio event loop: {str(le)}", "WARNING")
            
        logger.stop_intercepting()
        set_running(False)
        set_task_id(None)
        add_log_entry("[SYSTEM] Scraper thread terminated, resources cleaned up.", "INFO")

def start_scraper(category: str, pincodes: str, task_id: int, resume: bool = False):
    """Starts the scraper thread if not already running."""
    global _scraper_thread
    with _thread_lock:
        current_state = get_state()
        if current_state["status"] != "idle":
            return False, "Scraper is already active or stopping."
            
        set_running(True)
        add_log_entry(f"[SYSTEM] Starting scraper run with category: '{category or 'ALL'}', pincodes: '{pincodes or 'DEFAULT'}', resume: {resume}.", "INFO")
        
        _scraper_thread = threading.Thread(
            target=_run_scraper_thread,
            args=(category, pincodes, task_id, resume),
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
        
        task_id = current_state.get("task_id")
        if task_id:
            _update_task_db(task_id, status="STOPPED")
            
        return True, "Stop signal transmitted to scraper."
