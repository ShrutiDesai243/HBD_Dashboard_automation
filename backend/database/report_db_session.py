"""
Separate database session for the remote report database (genuinedashboardtest).
This keeps the report DB connection isolated from the main application DB.
Handles connection failures gracefully with retry logic.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import OperationalError
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

# Remote Report Database credentials
REPORT_DB_HOST = os.getenv('REPORT_DB_HOST', '77.42.78.20')
REPORT_DB_USER = os.getenv('REPORT_DB_USER', 'mukesh')
REPORT_DB_PASSWORD = os.getenv('REPORT_DB_PASSWORD', 'xVUHAaORqSxG0oYPtMJm')
REPORT_DB_NAME = os.getenv('REPORT_DB_NAME', 'genuinedashboardtest')
REPORT_DB_PORT = os.getenv('REPORT_DB_PORT', '3306')

REPORT_DATABASE_URL = (
    f"mysql+pymysql://{REPORT_DB_USER}:{urllib.parse.quote_plus(REPORT_DB_PASSWORD or '')}"
    f"@{REPORT_DB_HOST}:{REPORT_DB_PORT}/{REPORT_DB_NAME}"
)

print(f"[Report DB] HOST: {REPORT_DB_HOST} USER: {REPORT_DB_USER} DB: {REPORT_DB_NAME}")

# Separate engine for the report database — with shorter timeouts for faster failure
report_engine = create_engine(
    REPORT_DATABASE_URL,
    echo=False,
    future=True,
    pool_size=5,
    max_overflow=3,
    pool_timeout=2,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={
        'connect_timeout': 2,
        'read_timeout': 10,
        'write_timeout': 10,
    }
)

# Session Factory
ReportSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=report_engine)

# Scoped session (thread-safe)
report_db_session = scoped_session(ReportSessionLocal)


def get_report_db_session():
    """
    Returns a new database session for the remote report database.
    Must close() manually after use in Flask routes.
    """
    return ReportSessionLocal()


def test_report_db_connection():
    """
    Test connectivity to the report database.
    Returns (True, info_dict) on success, (False, error_string) on failure.
    """
    try:
        session = get_report_db_session()
        session.execute(text("SELECT 1"))
        
        # Get table list
        tables_result = session.execute(text("SHOW TABLES")).fetchall()
        tables = [row[0] for row in tables_result]
        
        session.close()
        return True, {
            "host": REPORT_DB_HOST,
            "database": REPORT_DB_NAME,
            "tables": tables,
            "status": "connected"
        }
    except Exception as e:
        return False, str(e)
