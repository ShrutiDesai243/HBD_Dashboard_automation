"""
Blinkit Scraper Celery Task — Subprocess wrapper
Mirrors the DMart pattern: spawns a clean subprocess to avoid gevent conflicts.
"""
import os
import sys
import subprocess
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.products.scrape_blinkit", ignore_result=True)
def run_blinkit_scraper(task_id: int, pincode: str = "110001", mode: str = "full",
                        max_categories=None, resume: bool = False):
    """
    Celery task wrapper for Blinkit live scraping.
    Launches a clean subprocess to bypass gevent monkey-patching conflicts.
    """
    logger.info(f"[Celery] run_blinkit_scraper | task_id={task_id} | pincode={pincode} | mode={mode}")

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    cmd = [
        sys.executable, "-m", "services.scrapers.blinkit_service",
        "--pincode", str(pincode),
        "--mode", str(mode),
    ]
    if task_id:
        cmd.extend(["--task_id", str(task_id)])
    if max_categories:
        cmd.extend(["--max_categories", str(max_categories)])
    if resume:
        cmd.append("--resume")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        result = subprocess.run(
            cmd,
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            logger.error(f"[Celery] Blinkit scraper subprocess failed (exit={result.returncode})")
            logger.error(f"STDERR: {result.stderr[:1000]}")
            if task_id:
                _mark_error(task_id, f"Subprocess exited {result.returncode}: {result.stderr[:500]}")
        else:
            logger.info("[Celery] Blinkit scraper subprocess completed successfully")
    except Exception as e:
        logger.error(f"[Celery] Failed to launch Blinkit scraper subprocess: {e}", exc_info=True)
        if task_id:
            _mark_error(task_id, f"Failed to start subprocess: {str(e)}")


def _mark_error(task_id: int, message: str):
    try:
        from app import app
        from extensions import db
        from model.scraper_task import ScraperTask
        with app.app_context():
            task = db.session.get(ScraperTask, task_id)
            if task and task.status != "COMPLETED":
                task.status = "ERROR"
                task.error_message = message[:2000]
                db.session.commit()
    except Exception as e:
        logger.error(f"[Celery] Could not mark task as ERROR: {e}")
