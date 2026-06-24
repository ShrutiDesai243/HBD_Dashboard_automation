from playwright.sync_api import sync_playwright
import time

def test_google_maps():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.google.com/maps/search/plumber+in+ahmedabad?hl=en")
        
        try:
            page.wait_for_selector('div[role="feed"]', timeout=15000)
            
            # Scroll a few times
            for _ in range(3):
                page.mouse.wheel(0, 5000)
                page.wait_for_timeout(1000)
                
            # Find all links
            links = page.locator('a[href*="/maps/place/"]').all()
            print(f"Found {len(links)} links")
            
            for link in links[:5]:
                href = link.get_attribute('href')
                name = link.get_attribute('aria-label')
                print(f"Name: {name}")
                print(f"URL: {href}")
                print("-" * 20)
                
        except Exception as e:
            print("Error:", e)
        finally:
            browser.close()

if __name__ == "__main__":
    test_google_maps()
