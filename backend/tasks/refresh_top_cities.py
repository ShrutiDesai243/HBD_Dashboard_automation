import logging
from celery_app import celery
from database.session import get_db_session
from sqlalchemy import text

@celery.task(name='tasks.refresh_top_cities.update_business_counts')
def update_business_counts():
    """
    Periodic task to refresh business_count in Top_cities_rank based on master_table.
    Maintains existing city ranks and only updates the live data counts.
    """
    logging.info("Starting refresh of Top_cities_rank business counts...")
    session = get_db_session()
    try:
        # Reset all current counts to 0
        session.execute(text("UPDATE Top_cities_rank SET business_count = 0"))
        
        # Calculate new counts from master_table and update Top_cities_rank
        update_query = text("""
            UPDATE Top_cities_rank tcr
            JOIN (
                SELECT city, COUNT(1) as cnt 
                FROM master_table 
                WHERE city IS NOT NULL AND city != ''
                GROUP BY city
            ) as mt ON LOWER(tcr.city_name) COLLATE utf8mb4_general_ci = LOWER(mt.city) COLLATE utf8mb4_general_ci
            SET tcr.business_count = mt.cnt
        """)
        session.execute(update_query)
        session.commit()
        logging.info("Successfully refreshed Top_cities_rank business counts.")
        return "Success"
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to refresh top cities rank: {e}")
        return str(e)
    finally:
        session.close()

if __name__ == '__main__':
    # For manual testing
    # Requires running from within the backend directory
    update_business_counts()
