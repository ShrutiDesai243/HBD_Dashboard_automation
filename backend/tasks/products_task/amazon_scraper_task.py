from celery import shared_task
from services.scrapers.amazon_service import scrape_amazon_search

@shared_task(name="tasks.products.scrape_amazon", ignore_result=True)
def run_amazon_scraper(search_term, pages=1):
    """
    Celery task wrapper for Amazon live scraping.
    """
    scrape_amazon_search(search_term, pages)
    
    # Automatically trigger category sync & auto-mapping for Amazon in background
    try:
        from app import app
        from services.category_sync_service import auto_sync_platform
        with app.app_context():
            auto_sync_platform('Amazon')
    except Exception as sync_err:
        print(f"[CategoryAutoSync] Error running sync for Amazon after scraper: {sync_err}")
