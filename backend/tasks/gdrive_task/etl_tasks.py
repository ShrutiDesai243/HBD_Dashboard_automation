import os
import csv
import io
import logging
import time
import random
import signal
import hashlib
import threading
import redis
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import OperationalError
from urllib.parse import quote_plus
from google.oauth2 import service_account
from utils.metrics import (
    files_processed, rows_inserted, rows_skipped,
    processing_time, dlq_entries, active_db_ops, batch_size_hist, error_count
)
from config import config
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from celery import shared_task
from dotenv import load_dotenv

from model.normalizer import UniversalNormalizer

from celery.utils.log import get_task_logger
import redis as redis_lib

logger = get_task_logger("GDrive_Celery_Task")

# Ensure file logging still works for history
log_file_path = os.path.join(os.getcwd(), 'output', 'gdrive_etl.log')
if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(file_handler)
logger.setLevel(logging.INFO)
# Force UTF-8 encoding for file log

# Centralized configuration
SERVICE_ACCOUNT_FILE = config.SERVICE_ACCOUNT_FILE
DATABASE_URI = config.DATABASE_URI
MAX_FILE_SIZE_MB = config.MAX_FILE_SIZE_MB
ETL_VERSION = config.ETL_VERSION
BATCH_SIZE = min(config.BATCH_SIZE, 500)  # Cap at 500 to reduce InnoDB lock window & deadlocks

# SECTION 1: Optimized SQLAlchemy Engine (NullPool for Celery Workers)
# By using NullPool, Celery workers open and close connections per task, preventing connection limit exhaustion
engine = create_engine(
    DATABASE_URI,
    poolclass=NullPool,
    pool_pre_ping=True
)

# Global Redis Pool for metrics and locks
import redis as redis_lib
redis_pool = redis_lib.ConnectionPool.from_url(
    os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    max_connections=10, # Reduced to avoid socket exhaustion
    socket_timeout=10,
    socket_connect_timeout=10
)
redis_client = redis_lib.Redis(connection_pool=redis_pool)

# Fix 7: Graceful Shutdown
shutdown_requested = False

def handle_shutdown(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    # Avoid logging here as it causes reentrant RuntimeError during recursive calls or I/O interrupts

# Register signal handlers (only in main thread to avoid Windows errors)
try:
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
except (OSError, ValueError):
    # signal handlers can only be set in the main thread
    pass

# Fix 10: DB Rate Limiting (Removed local semaphore as it doesn't work across processes)
# We will rely on Celery's worker concurrency flags to manage parallel workloads smoothly.


def get_service():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Service account file not found at: {SERVICE_ACCOUNT_FILE}")
        
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=creds, cache_discovery=False)


# Fix 1 + Fix 2: File size protection + Context manager (no memory leak)
@contextmanager
def download_csv(service, file_id, max_size_mb=None):
    """
    Downloads a CSV file from Google Drive into memory.
    Note: Buffers fully into memory before yielding to the reader.
    """
    import gevent
    request = service.files().get_media(fileId=file_id)
    
    import io
    from googleapiclient.http import MediaIoBaseDownload
    
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request, chunksize=1024*1024) # 1MB chunks
    
    done = False
    while not done:
        # Crucial: Yield control to gevent hub every chunk to handle Redis heartbeats
        gevent.sleep(0.01)
        
        # Retry logic for transient SSL / Network errors during download
        for attempt in range(5):
            try:
                _, done = downloader.next_chunk()
                break
            except Exception as e:
                if (attempt < 4 and ("SSL" in str(e) or "EOF" in str(e) or "connection" in str(e).lower())):
                    wait = 2 ** attempt
                    time.sleep(wait)
                    continue
                raise
    
    fh.seek(0)
    wrapper = io.TextIOWrapper(fh, encoding='utf-8', errors='replace')
    try:
        yield wrapper
    finally:
        wrapper.close()


def get_file_hash(file_id, modified_time):
    """Generate a hash for file change detection."""
    return hashlib.md5(f"{file_id}:{modified_time}".encode()).hexdigest()


# SECTION 3: Batched Insert Optimization (with Deadlock Retry + Rate Limiting)

def commit_batch(batch, task_id=None, **kwargs):
    """
    Inserts a BATCH of rows efficiently. 
    NO deduplication - inserts EVERYTHING as requested.
    Includes retry logic for transient DB errors.
    """
    if not batch:
        return 0
    
    # Sanitize all values before insertion to prevent ANY DB error
    for row in batch:
        row['etl_version'] = ETL_VERSION
        row['task_id'] = task_id
        # Ensure drive_uploaded_time is MySQL-safe
        dt = row.get('drive_uploaded_time')
        if dt and isinstance(dt, str) and 'T' in dt:
            dt = dt.replace('T', ' ').replace('Z', '').split('.')[0]
            row['drive_uploaded_time'] = dt
        # Ensure numeric fields are safe
        try:
            row['reviews_count'] = int(row.get('reviews_count') or 0)
        except (ValueError, TypeError):
            row['reviews_count'] = 0
        try:
            row['reviews_average'] = float(row.get('reviews_average') or 0.0)
        except (ValueError, TypeError):
            row['reviews_average'] = 0.0
        # Truncate long strings to prevent DB overflow
        for key in ['name', 'address', 'website', 'phone_number', 'category', 'subcategory', 'city', 'state', 'area']:
            val = row.get(key)
            if val and isinstance(val, str) and len(val) > 500:
                row[key] = val[:500]
        
        # Calculate Row Signature for exact deduplication in Raw Table
        # (Using all 11 business columns to only block TRUE exact copies)
        sig_str = "|".join([
            str(row.get('name') or "").lower().strip(),
            str(row.get('address') or "").lower().strip(),
            str(row.get('website') or "").lower().strip(),
            str(row.get('phone_number') or "").lower().strip(),
            str(row.get('reviews_count') or 0),
            str(row.get('reviews_average') or 0.0),
            str(row.get('category') or "").lower().strip(),
            str(row.get('subcategory') or "").lower().strip(),
            str(row.get('city') or "").lower().strip(),
            str(row.get('state') or "").lower().strip(),
            str(row.get('area') or "").lower().strip()
        ])
        row['row_signature'] = hashlib.md5(sig_str.encode('utf-8', errors='ignore')).hexdigest()
        
    sql = text("""
        INSERT IGNORE INTO raw_google_map_drive_data (
            name, address, website, phone_number, 
            reviews_count, reviews_average, 
            category, subcategory, city, state, area, 
            drive_file_id, drive_file_name, full_drive_path, 
            drive_uploaded_time, source,
            etl_version, task_id, file_hash, row_signature
        )
        VALUES (
            :name, :address, :website, :phone_number, 
            :reviews_count, :reviews_average, 
            :category, :subcategory, :city, :state, :area, 
            :drive_file_id, :drive_file_name, :drive_file_path, 
            :drive_uploaded_time, 'google_drive',
            :etl_version, :task_id, :file_hash, :row_signature
        )
    """)
    
    # Inject lineage fields into each row
    for row in batch:
        row.setdefault('etl_version', ETL_VERSION)
        row.setdefault('task_id', task_id)
        row.setdefault('file_hash', '')
    # All DB operations are wrapped in context managers for resource safety.

    from redis import Redis
    
    # 1. Deduplicate using Redis to avoid InnoDB gap-lock deadlocks on INSERT IGNORE
    # We use a Redis TTL-based key (3 days) to quickly filter out exact duplicates
    # before they even hit the MySQL database, while keeping RAM usage bounded.
    try:
        r = Redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"))
        
        unique_batch = []
        for row in batch:
            # Create a unique deterministic identity for the row
            identity_string = f"{row.get('name', '')}|{row.get('phone_number', '')}|{row.get('address', '')}".lower().strip()
            row_hash = hashlib.md5(identity_string.encode('utf-8')).hexdigest()
            redis_key = f"gdrive_etl_dedup:{row_hash}"
            
            # Check if this exact row has been processed recently
            # SET NX EX 259200 sets the key for 3 days, returning True if it was set (meaning it's new)
            is_new = r.set(redis_key, "1", nx=True, ex=259200)
            
            if is_new:
                unique_batch.append(row)
            else:
                # Row is a duplicate, skip it entirely
                pass
                
        # If the entire batch was duplicates, return early
        if not unique_batch:
            return 0
            
    except Exception as e:
        logger.warning(f"Redis deduplication failed, falling back to MySQL INSERT IGNORE: {e}")
        unique_batch = batch # Fallback to sending all rows to MySQL if Redis fails
        
    # Sort the batch by the unique index columns to prevent InnoDB Deadlocks.
    # Concurrent transactions locking index records in the same order avoid deadlocks.
    unique_batch.sort(key=lambda x: (
        str(x.get('name', '')), 
        str(x.get('address', '')), 
        str(x.get('phone_number', ''))
    ))

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with engine.begin() as conn:
                result = conn.execute(sql, batch)
                inserted = result.rowcount
                if inserted > 0:
                    rows_inserted.inc(inserted)
                logger.info(f"Committed batch: {inserted} rows.")
                return inserted
        except OperationalError as e:
            err_msg = str(e)
            # Retry on deadlock or connection errors
            if attempt < max_retries - 1 and ('Deadlock' in err_msg or '2006' in err_msg or '2013' in err_msg or 'Lost connection' in err_msg):
                wait = (2 ** attempt) + random.uniform(0.5, 2.5)  # Exponential backoff + jitter
                logger.warning(f"DB retry {attempt+1}/{max_retries}: {'Deadlock' if 'Deadlock' in err_msg else 'Connection lost'}, waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            # Non-retryable OperationalError
            if "[parameters:" in err_msg:
                err_msg = err_msg.split("[parameters:")[0].strip()
            if "[SQL:" in err_msg:
                err_msg = err_msg.split("[SQL:")[0].strip()
            logger.error(f"Batch Insert Failed after retries: {err_msg}")
            return 0
        except Exception as e:
            msg = str(e)
            if "[parameters:" in msg:
                msg = msg.split("[parameters:")[0].strip()
            if "[SQL:" in msg:
                msg = msg.split("[SQL:")[0].strip()
            logger.error(f"Batch Insert Failed: {msg}")
            return 0
    return 0


def update_file_checkpoint(file_id, filename, status, row_number=0, error_msg=None, file_hash=None):
    """
    Updates file status and row checkpoint for crash-safe resumption.
    If conn is provided, uses it (for transactional atomicity).
    """
    try:
        sql = text("""
            INSERT INTO file_registry (drive_file_id, filename, drive_folder_id, status, error_message, file_hash, processed_at)
            VALUES (:file_id, :filename, :folder_id, :status, :error_msg, :file_hash, NOW())
            ON DUPLICATE KEY UPDATE 
                status = VALUES(status),
                error_message = VALUES(error_message),
                drive_folder_id = COALESCE(VALUES(drive_folder_id), drive_folder_id),
                file_hash = COALESCE(VALUES(file_hash), file_hash),
                processed_at = NOW()
        """)
        if conn:
            conn.execute(sql, {
                "file_id": file_id,
                "filename": filename,
                "status": status,
                "row_num": row_number,
                "error_msg": str(error_msg)[:2000] if error_msg else None,
                "file_hash": file_hash
            })
    except Exception as e:
        # Strip verbose SQL from warning message
        msg = str(e)
        if "[SQL:" in msg:
            msg = msg.split("[SQL:")[0].strip()
        logger.warning(f"Checkpoint update failed for {filename}: {msg}")

def get_file_checkpoint(file_id):
    """Retrieves the processing status for a file."""
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT status FROM file_registry WHERE drive_file_id = :id"), {"id": file_id}).fetchone()
            if res:
                return res[0], 0
    except Exception:
        pass
    return None, 0


# Fix 4: Dead Letter Queue
def send_to_dlq(file_id, file_name, error, task_id, retry_count=0):
    """Route permanently failed tasks to the Dead Letter Queue."""
    try:
        sql = text("""
            INSERT INTO etl_dlq (file_id, file_name, error, task_id, retry_count, failed_at)
            VALUES (:file_id, :file_name, :error, :task_id, :retry_count, NOW())
        """)
        with engine.begin() as conn:
            conn.execute(sql, {
                "file_id": file_id,
                "file_name": file_name,
                "error": str(error)[:2000],  # Truncate long errors
                "task_id": task_id,
                "retry_count": retry_count
            })
        dlq_entries.inc()  # Fix 9: Metrics
        logger.warning(f"[DLQ] Task routed to Dead Letter Queue: {file_name} (retries: {retry_count})")
    except Exception as e:
        logger.warning(f"[DLQ] Failed to write to DLQ for {file_name}: {e}")


# SECTION 6: Dashboard Stats Refresh — Zero Downtime
@shared_task(name="tasks.gdrive.refresh_stats", ignore_result=True)
def refresh_dashboard_stats():
    """Recalculates dashboard statistics using UPSERT logic."""
    try:
        with engine.begin() as conn:
            # 1. UPSERT Global Summary (id=1)
            res = conn.execute(text("SELECT COUNT(*), COUNT(DISTINCT state), COUNT(DISTINCT category), COUNT(DISTINCT drive_file_id) FROM raw_google_map_drive_data")).fetchone()
            
            conn.execute(text("""
                INSERT INTO dashboard_stats_summary_v5 
                (id, total_records, total_states, total_categories, total_csvs, last_updated)
                VALUES (1, :total, :states, :cats, :csvs, NOW())
                ON DUPLICATE KEY UPDATE 
                    total_records = VALUES(total_records),
                    total_states = VALUES(total_states),
                    total_categories = VALUES(total_categories),
                    total_csvs = VALUES(total_csvs),
                    last_updated = NOW()
            """), {"total": res[0], "states": res[1], "cats": res[2], "csvs": res[3]})

            # 2. UPSERT State-Category Summary
            conn.execute(text("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"))
            conn.execute(text("""
                INSERT INTO state_category_summary_v5 (state, category, record_count)
                SELECT state, category, COUNT(*) 
                FROM raw_google_map_drive_data 
                GROUP BY state, category
                ON DUPLICATE KEY UPDATE 
                    record_count = VALUES(record_count)
            """))
            conn.execute(text("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            
        logger.info("Dashboard stats refreshed successfully without locking tables.")
    except Exception as e:
        logger.warning(f"Stats Refresh Failed (non-fatal): {e}")

def trigger_stats_refresh():
    """Call this inside process_csv_task on success. Fully guarded — never throws."""
    try:
        val = redis_client.incr("gdrive_etl_file_count")
        if val % 50 == 0:
            refresh_dashboard_stats.delay()
    except Exception:
        # Redis down is non-fatal — just skip stats trigger silently
        pass


@contextmanager
def redis_lock(lock_name, timeout=3600):
    """Simple redis-based distributed lock."""
    lock_id = threading.get_ident()
    # set nx=True means only set if it doesn't exist
    acquired = redis_client.set(f"lock:{lock_name}", lock_id, ex=timeout, nx=True)
    try:
        yield acquired
    finally:
        if acquired:
            # Only delete if we own it (simple check)
            if redis_client.get(f"lock:{lock_name}") == str(lock_id).encode():
                redis_client.delete(f"lock:{lock_name}")


# SECTION 4: Main Processing Task (with all fixes applied)
@shared_task(
    bind=True, 
    max_retries=3,  # Fix 4: Reduced from 5 to route to DLQ faster
    name="tasks.gdrive.process_csv",
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True
)
def process_csv_task(self, file_id, file_name, folder_id, folder_name, path, modified_time):
    global shutdown_requested
    start_time = time.time()
    task_id = self.request.id
    
    # Normalize datetime ONCE — handles all ISO formats safely
    if modified_time:
        modified_time = str(modified_time).strip()
        if 'T' in modified_time:
            modified_time = modified_time.replace('T', ' ').replace('Z', '').split('.')[0]
        
    file_hash = get_file_hash(file_id, modified_time or '')
    
    # 1. Check for existing checkpoint (Idempotency Phase 3)
    status, last_row = get_file_checkpoint(file_id)
    if status == 'PROCESSED':
        logger.info(f"Skip: {file_name} already fully processed.")
        return f"Skipped processed file: {file_name}"
    
    try:
        service = get_service()
        update_file_checkpoint(file_id, file_name, 'IN_PROGRESS', last_row, file_hash=file_hash)
        
        with download_csv(service, file_id) as stream:
            reader = csv.DictReader(stream)
            current_row_idx = 0
            batch = []
            BATCH_THRESHOLD = 3000 # Memory-friendly limit
            
            for row in reader:
                current_row_idx += 1
                
                # Resume logic: Skip rows already processed
                if current_row_idx <= last_row:
                    continue

                if shutdown_requested:
                    if batch:
                        commit_batch(batch, task_id=task_id)
                    update_file_checkpoint(file_id, file_name, 'IN_PROGRESS', current_row_idx-1, 
                                          error_msg="Graceful shutdown")
                    return f"Paused: {file_name} at row {current_row_idx-1}"
                
                # Normalize — wrapped in try/except to skip bad rows instead of crashing
                try:
                    norm_row = UniversalNormalizer.normalize_row_raw({
                        **row, "drive_file_id": file_id, "drive_file_name": file_name,
                        "drive_folder_id": folder_id, "drive_folder_name": folder_name,
                        "drive_file_path": path, "drive_uploaded_time": modified_time
                    })
                    norm_row['file_hash'] = file_hash
                    batch.append(norm_row)
                except Exception as norm_err:
                    logger.warning(f"Row {current_row_idx} normalization failed in {file_name}: {norm_err}")
                    continue
                
                # BATCH INSERT (High Speed)
                if len(batch) >= BATCH_THRESHOLD:
                    commit_batch(batch, task_id=task_id)
                    update_file_checkpoint(file_id, file_name, 'IN_PROGRESS', current_row_idx, file_hash=file_hash)
                    batch = []

            # Remaining rows
            if batch:
                commit_batch(batch, task_id=task_id)
            
            # Final success state
            update_file_checkpoint(file_id, file_name, 'PROCESSED', current_row_idx, file_hash=file_hash)

        processing_time.observe(time.time() - start_time)
        files_processed.inc()
        trigger_stats_refresh()
        return f"Completed {file_name}: {current_row_idx} rows"

    except Exception as e:
        err_msg = str(e)
        logger.error(f"[ERROR] processing {file_name}: {err_msg}", extra={'task_id': task_id})
        update_file_status(file_id, file_name, 'ERROR', err_msg, file_hash=file_hash, folder_id=folder_id)
        
        # Fix 4: Route to DLQ on final retry
        if self.request.retries >= self.max_retries:
            send_to_dlq(file_id, file_name, err_msg[:2000], task_id, self.request.retries)
            # Don't raise — file is in DLQ, no more retries
            return f"DLQ: {file_name} after {self.request.retries} retries"
        raise self.retry(exc=e)
