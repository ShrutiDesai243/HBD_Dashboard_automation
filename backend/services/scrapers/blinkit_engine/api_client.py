"""
Blinkit API Client — Async HTTP client with rate limiting, retries, and User-Agent rotation.
Uses requests (sync) wrapped in threading to avoid asyncio/Celery conflicts.
"""
import time
import random
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any

from services.scrapers.blinkit_engine.config import (
    BASE_HEADERS, USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX,
    MAX_RETRIES, BACKOFF_BASE, BACKOFF_MAX, REQUEST_TIMEOUT,
    CATEGORY_LIST_URL, SUBCATEGORY_LIST_URL, PRODUCTS_BY_CAT_URL,
    DEFAULT_PINCODE,
)

logger = logging.getLogger(__name__)


class BlinkitAPIClient:
    """
    Thread-safe Blinkit API client with:
    - User-Agent rotation
    - Exponential backoff retries
    - Rate limiting
    - Pincode/location header injection
    """

    def __init__(self, pincode: str = DEFAULT_PINCODE):
        self.pincode = str(pincode)
        self._ua_index = 0
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _rotate_ua(self) -> str:
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    def _get_headers(self, extra: Optional[Dict] = None) -> Dict[str, str]:
        headers = dict(BASE_HEADERS)
        headers["User-Agent"] = self._rotate_ua()
        headers["l"] = self.pincode  # Blinkit location header
        if extra:
            headers.update(extra)
        return headers

    def _rate_limit(self):
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)

    def _get(self, url: str, params: Optional[Dict] = None, attempt: int = 0) -> Optional[Dict[str, Any]]:
        """Execute GET request with exponential backoff retry."""
        try:
            self._rate_limit()
            resp = self._session.get(
                url,
                headers=self._get_headers(),
                params=params or {},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                # Rate limited — longer backoff
                wait = min(BACKOFF_MAX, BACKOFF_BASE ** attempt * 5 + random.uniform(1, 3))
                logger.warning(f"[RateLimit] 429 on {url} | waiting {wait:.1f}s | attempt {attempt+1}")
                time.sleep(wait)
                if attempt < MAX_RETRIES:
                    return self._get(url, params, attempt + 1)
            elif resp.status_code in (403, 401):
                logger.error(f"[Auth] {resp.status_code} on {url} — may need session cookies")
                return None
            elif resp.status_code >= 500:
                wait = min(BACKOFF_MAX, BACKOFF_BASE ** attempt * 2 + random.uniform(0.5, 2))
                logger.warning(f"[ServerError] {resp.status_code} on {url} | waiting {wait:.1f}s | attempt {attempt+1}")
                time.sleep(wait)
                if attempt < MAX_RETRIES:
                    return self._get(url, params, attempt + 1)
            else:
                logger.warning(f"[HTTP {resp.status_code}] {url}")
            return None
        except requests.exceptions.Timeout:
            wait = min(BACKOFF_MAX, BACKOFF_BASE ** attempt * 2)
            logger.warning(f"[Timeout] {url} | waiting {wait:.1f}s | attempt {attempt+1}")
            time.sleep(wait)
            if attempt < MAX_RETRIES:
                return self._get(url, params, attempt + 1)
            return None
        except requests.exceptions.ConnectionError as e:
            wait = min(BACKOFF_MAX, BACKOFF_BASE ** attempt * 3)
            logger.warning(f"[ConnError] {url} | {e} | waiting {wait:.1f}s | attempt {attempt+1}")
            time.sleep(wait)
            if attempt < MAX_RETRIES:
                return self._get(url, params, attempt + 1)
            return None
        except Exception as e:
            logger.error(f"[UnexpectedError] {url} | {e}", exc_info=True)
            return None

    # ── Category APIs ────────────────────────────────────────────────────────

    def fetch_main_categories(self) -> Optional[Dict]:
        """Fetch top-level category list from Blinkit header slot API."""
        logger.info(f"[API] Fetching main categories for pincode={self.pincode}")
        result = self._get(CATEGORY_LIST_URL)
        return result

    def fetch_subcategories(self, category_id: int) -> Optional[Dict]:
        """Fetch subcategories for a given category_id."""
        params = {"category_id": category_id}
        logger.info(f"[API] Fetching subcategories for category_id={category_id}")
        return self._get(SUBCATEGORY_LIST_URL, params=params)

    # ── Product APIs ─────────────────────────────────────────────────────────

    def fetch_products_by_category(self, category_id: int, page: int = 1) -> Optional[Dict]:
        """
        Fetch paginated products for a category.
        Returns None if no more products (empty page).
        """
        params = {
            "category_id": category_id,
            "page": page,
            "size": 40,  # max items per page
        }
        logger.debug(f"[API] Products cat={category_id} page={page}")
        return self._get(PRODUCTS_BY_CAT_URL, params=params)

    def close(self):
        if self._session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
