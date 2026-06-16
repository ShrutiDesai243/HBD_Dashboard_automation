import os
import sys
import subprocess
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task(name="tasks.products.scrape_dmart", ignore_result=True)
def run_dmart_scraper(task_id, search_term, mode="category", pincodes="400001", max_categories=None):
    """
    Celery task wrapper for DMart live scraping.
    Launches a clean background subprocess to bypass gevent monkey-patching conflict with asyncio/Playwright.
    """
    logger.info(f"Celery run_dmart_scraper starting subprocess | task_id={task_id} | search_term={search_term}")
    
    # Resolve the backend root directory
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    cmd = [
        sys.executable,
        "-m", "services.scrapers.dmart_service",
        "--search_term", str(search_term),
        "--mode", str(mode),
        "--pincodes", str(pincodes),
    ]
    if max_categories is not None:
        cmd.extend(["--max_categories", str(max_categories)])
    if task_id is not None:
        cmd.extend(["--task_id", str(task_id)])
        
    # Configure subprocess environment for Windows UTF-8 compatibility
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    try:
        # Run subprocess synchronously within the worker thread
        result = subprocess.run(
            cmd,
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.error(f"DMart Scraper Subprocess failed with exit code {result.returncode}!")
            logger.error(f"STDOUT:\n{result.stdout}")
            logger.error(f"STDERR:\n{result.stderr}")
            
            # Update ScraperTask to ERROR in case the subprocess didn't catch the error
            if task_id:
                from app import app
                from extensions import db
                from model.scraper_task import ScraperTask
                with app.app_context():
                    task = ScraperTask.query.get(task_id)
                    if task and task.status != "ERROR":
                        task.status = "ERROR"
                        task.error_message = f"Subprocess exited with code {result.returncode}. Error: {result.stderr[:500]}"
                        db.session.commit()
        else:
            logger.info("DMart Scraper Subprocess completed successfully.")
            logger.debug(f"STDOUT:\n{result.stdout}")
            
            # Automatically trigger category sync & auto-mapping for DMart in background
            try:
                from app import app
                from services.category_sync_service import auto_sync_platform
                with app.app_context():
                    auto_sync_platform('DMart')
            except Exception as sync_err:
                logger.error(f"[CategoryAutoSync] Error running sync for DMart after scraper: {sync_err}")
    except Exception as e:
        logger.error(f"Failed to launch or execute DMart scraper subprocess: {e}", exc_info=True)
        if task_id:
            from app import app
            from extensions import db
            from model.scraper_task import ScraperTask
            with app.app_context():
                task = ScraperTask.query.get(task_id)
                if task:
                    task.status = "ERROR"
                    task.error_message = f"Failed to start scraper subprocess: {str(e)}"
                    db.session.commit()
