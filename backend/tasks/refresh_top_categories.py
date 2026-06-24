import logging
from celery_app import celery
from database.session import get_db_session
from sqlalchemy import text

@celery.task(name='tasks.refresh_top_categories.update_category_counts')
def update_category_counts():
    """
    Periodic task to refresh business_count in Top_categories_rank based on master_table.
    Maintains existing category ranks and only updates the live data counts.
    """
    logging.info("Starting refresh of Top_categories_rank business counts...")
    session = get_db_session()
    try:
        # Reset all current counts to 0
        session.execute(text("UPDATE Top_categories_rank SET business_count = 0"))
        
        # Calculate new counts from master_table and update Top_categories_rank
        update_query = text("""
            UPDATE Top_categories_rank tcr
            JOIN (
                SELECT business_category, COUNT(1) as cnt 
                FROM master_table 
                WHERE business_category IS NOT NULL AND business_category != ''
                GROUP BY business_category
            ) as mt ON LOWER(tcr.category_name) COLLATE utf8mb4_general_ci = LOWER(mt.business_category) COLLATE utf8mb4_general_ci
            SET tcr.business_count = mt.cnt
        """)
        session.execute(update_query)
        session.commit()
        logging.info("Successfully refreshed Top_categories_rank business counts.")
        return "Success"
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to refresh top categories rank: {e}")
        return str(e)
    finally:
        session.close()

if __name__ == '__main__':
    # For manual testing
    # Requires running from within the backend directory
    update_category_counts()
