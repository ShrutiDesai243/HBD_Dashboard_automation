import os
import sys
import subprocess
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task(name="tasks.products.scrape_indiamart", ignore_result=True)
def run_indiamart_scraper(task_id, search_term, pages=1):
    """
    Celery task wrapper for IndiaMART live scraping.
    Launches a clean background subprocess to avoid asyncio/Playwright conflicts inside Celery's event loop.
    """
    logger.info(f"Celery run_indiamart_scraper starting subprocess | task_id={task_id} | query={search_term}")
    
    # Resolve the backend root directory
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    cmd = [
        sys.executable,
        "-m", "services.scrapers.indiamart_service",
        "--search_term", str(search_term),
        "--pages", str(pages),
    ]
    if task_id is not None:
        cmd.extend(["--task_id", str(task_id)])
        
    # Configure environment for Windows UTF-8 logs compatibility
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    try:
        # Run subprocess synchronously within the Celery worker thread
        result = subprocess.run(
            cmd,
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.error(f"IndiaMART Scraper Subprocess failed with exit code {result.returncode}!")
            logger.error(f"STDOUT:\n{result.stdout}")
            logger.error(f"STDERR:\n{result.stderr}")
            
            # Update ScraperTask to ERROR in case the subprocess crashed or timed out
            if task_id:
                from app import app
                from extensions import db
                from model.scraper_task import ScraperTask
                with app.app_context():
                    task = db.session.get(ScraperTask, task_id)
                    if task and task.status != "ERROR":
                        task.status = "ERROR"
                        task.error_message = f"Subprocess exited with code {result.returncode}. Error: {result.stderr[:500]}"
                        db.session.commit()
        else:
            logger.info("IndiaMART Scraper Subprocess completed successfully.")
            logger.debug(f"STDOUT:\n{result.stdout}")
            
            # Automatically trigger category sync & mapping in case it hasn't run
            try:
                from app import app
                from services.category_sync_service import auto_sync_platform
                with app.app_context():
                    auto_sync_platform('IndiaMart')
            except Exception as sync_err:
                logger.error(f"[CategoryAutoSync] Error running sync for IndiaMart: {sync_err}")
                
    except Exception as e:
        logger.error(f"Failed to launch or execute IndiaMART scraper subprocess: {e}", exc_info=True)
        if task_id:
            from app import app
            from extensions import db
            from model.scraper_task import ScraperTask
            with app.app_context():
                task = db.session.get(ScraperTask, task_id)
                if task:
                    task.status = "ERROR"
                    task.error_message = f"Failed to start scraper subprocess: {str(e)}"
                    db.session.commit()
