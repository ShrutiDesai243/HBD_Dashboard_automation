from bs4 import BeautifulSoup
import re

with open("indiamart_sample.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

print("--- Inspecting titles in loaded HTML ---")
titles = []
for tag in soup.find_all(class_=re.compile("product-title|title|name|prd-name|card-title|pnm|pname"), limit=50):
    titles.append(tag.get_text(strip=True))

if not titles:
    # Let's search for any occurrence of "Bearing" (case-insensitive) in any tags
    for tag in soup.find_all(True):
        if tag.name not in ['script', 'style'] and tag.string and 'bearing' in tag.string.lower():
            titles.append(f"{tag.name}: {tag.string.strip()}")

print(f"Total matching elements: {len(titles)}")
for t in titles[:20]:
    print(" -", t)
