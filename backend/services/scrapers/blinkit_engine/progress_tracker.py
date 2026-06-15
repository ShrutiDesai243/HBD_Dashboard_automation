"""
Blinkit Progress Tracker — Persistent state for scrape resume-from-failure.
Saves to JSON file so scrapes can resume after crashes.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from services.scrapers.blinkit_engine.config import STATE_FILE

logger = logging.getLogger(__name__)


class BlinkitProgressTracker:
    """
    Manages scrape state persistence.
    State is saved after each category batch so scrapes can resume.
    """

    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file
        self._state: Dict[str, Any] = self._load_or_init()

    def _load_or_init(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                logger.info(f"[State] Loaded existing state: {self.state_file}")
                return state
            except Exception as e:
                logger.warning(f"[State] Failed to load state file, resetting: {e}")
        return self._default_state()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "run_id": f"run_{int(time.time())}",
            "started_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
            "pincode": None,
            "mode": "full",
            "phase": "categories",  # "categories" | "products"
            "categories_discovered": 0,
            "categories_synced": 0,
            "products_scraped": 0,
            "products_inserted": 0,
            "products_updated": 0,
            "products_skipped": 0,
            "products_failed": 0,
            "duplicates_prevented": 0,
            "errors": [],
            "completed_category_ids": [],
            "current_category_id": None,
            "current_page": 1,
            "total_categories": 0,
            "is_complete": False,
        }

    def save(self):
        try:
            self._state["last_updated"] = datetime.utcnow().isoformat()
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"[State] Failed to save state: {e}")

    def reset(self, pincode: str, mode: str):
        self._state = self._default_state()
        self._state["pincode"] = pincode
        self._state["mode"] = mode
        self.save()

    # ── Accessors ──────────────────────────────────────────────────────────────

    def get(self, key: str, default=None):
        return self._state.get(key, default)

    def set(self, key: str, value):
        self._state[key] = value

    def increment(self, key: str, by: int = 1):
        self._state[key] = self._state.get(key, 0) + by

    def add_completed_category(self, category_id: int):
        completed = self._state.get("completed_category_ids", [])
        if category_id not in completed:
            completed.append(category_id)
        self._state["completed_category_ids"] = completed

    def is_category_completed(self, category_id: int) -> bool:
        return category_id in self._state.get("completed_category_ids", [])

    def add_error(self, error: str):
        errors = self._state.get("errors", [])
        errors.append({
            "timestamp": datetime.utcnow().isoformat(),
            "error": error[:500],
        })
        # Keep last 100 errors
        self._state["errors"] = errors[-100:]

    def mark_complete(self):
        self._state["is_complete"] = True
        self._state["phase"] = "completed"
        self.save()

    def summary(self) -> Dict[str, Any]:
        return {
            "products_scraped":     self._state.get("products_scraped", 0),
            "products_inserted":    self._state.get("products_inserted", 0),
            "products_updated":     self._state.get("products_updated", 0),
            "products_skipped":     self._state.get("products_skipped", 0),
            "duplicates_prevented": self._state.get("duplicates_prevented", 0),
            "categories_synced":    self._state.get("categories_synced", 0),
            "errors_count":         len(self._state.get("errors", [])),
            "is_complete":          self._state.get("is_complete", False),
        }
