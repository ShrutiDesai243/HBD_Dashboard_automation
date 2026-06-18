import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def run():
    print("Launching Playwright (HEADED)...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        url = "https://dir.indiamart.com/search.mp?ss=angular+contact+bearing"
        print(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            print("Page loaded. Waiting 5 seconds for rendering...")
            await page.wait_for_timeout(5000)
            print("Final Title:", await page.title())
            
            # Save screenshot for debug
            screenshot_path = os.path.join(os.path.dirname(__file__), "indiamart_debug.png")
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

            # Print first 2000 chars of page HTML
            content = await page.content()
            print("HTML length:", len(content))
            with open("indiamart_sample.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("HTML sample written to indiamart_sample.html")

        except Exception as e:
            print(f"Error occurred: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
