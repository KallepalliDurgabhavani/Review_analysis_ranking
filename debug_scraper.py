"""
Run this on YOUR machine: python debug_scraper.py
It will print EXACTLY what HTML classes are available on the page
so we can fix the selectors precisely.
"""

import requests
from bs4 import BeautifulSoup
import json, re

# ─── PASTE YOUR PRODUCT URL HERE ───
TEST_URL = "https://dl.flipkart.com/s/lA8ckNuuuN"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

print("=" * 60)
print("🔍 PriceHawk Scraper Debugger")
print("=" * 60)

res = requests.get(TEST_URL, headers=headers, timeout=15)
print(f"✅ Status: {res.status_code}")
print(f"📄 Page size: {len(res.text):,} chars\n")

soup = BeautifulSoup(res.text, "html.parser")

# ── 1. JSON-LD (most reliable) ──
print("─" * 40)
print("1️⃣  JSON-LD Structured Data:")
scripts = soup.find_all("script", type="application/ld+json")
for i, s in enumerate(scripts):
    try:
        data = json.loads(s.string or "")
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") in ["Product", "ItemPage"]:
                print(f"  ✅ FOUND Product JSON-LD!")
                print(f"  📝 Name:  {item.get('name', 'N/A')}")
                print(f"  💰 Price: {item.get('offers', {}).get('price', 'N/A')}")
                print(f"  🖼️  Image: {str(item.get('image', 'N/A'))[:80]}")
                agg = item.get("aggregateRating", {})
                print(f"  ⭐ Rating:{agg.get('ratingValue', 'N/A')}")
    except:
        pass

# ── 2. Meta tags ──
print("\n─" * 40)
print("2️⃣  Meta Tags:")
og_title = soup.find("meta", {"property": "og:title"})
og_image = soup.find("meta", {"property": "og:image"})
og_price = soup.find("meta", {"property": "product:price:amount"})
print(f"  og:title  = {og_title.get('content', 'NOT FOUND') if og_title else '❌ NOT FOUND'}")
print(f"  og:image  = {str(og_image.get('content', 'NOT FOUND'))[:80] if og_image else '❌ NOT FOUND'}")
print(f"  og:price  = {og_price.get('content', 'NOT FOUND') if og_price else '❌ NOT FOUND'}")

# ── 3. Page title ──
print("\n─" * 40)
print("3️⃣  Page Title Tag:")
t = soup.find("title")
print(f"  <title> = {t.text.strip()[:100] if t else '❌ NOT FOUND'}")

# ── 4. Find ALL elements containing ₹ ──
print("\n─" * 40)
print("4️⃣  All elements with ₹ (price candidates):")
found_prices = []
for elem in soup.find_all(text=re.compile(r'₹\s*\d')):
    parent = elem.parent
    classes = parent.get("class", [])
    text = str(elem).strip()
    if len(text) < 30 and classes and text not in found_prices:
        found_prices.append(text)
        print(f"  Tag: <{parent.name}> | Class: {classes} | Text: {text}")

if not found_prices:
    print("  ❌ No ₹ prices found on page!")

# ── 5. Find h1 tags (title candidates) ──
print("\n─" * 40)
print("5️⃣  All <h1> and <h2> tags:")
for tag in soup.find_all(["h1", "h2"]):
    text = tag.get_text(strip=True)
    if text and len(text) > 5:
        print(f"  <{tag.name}> class={tag.get('class', [])} | {text[:80]}")

# ── 6. Find ALL span/div with class containing known patterns ──
print("\n─" * 40)
print("6️⃣  Possible title class names (long text divs/spans):")
for tag in soup.find_all(["span", "div"]):
    text = tag.get_text(strip=True)
    classes = tag.get("class", [])
    if classes and len(text) > 30 and len(text) < 300 and len(classes) == 1:
        print(f"  <{tag.name}> class={classes} | {text[:80]}")

# ── 7. Images ──
print("\n─" * 40)
print("7️⃣  Product images (rukminim CDN):")
for img in soup.find_all("img"):
    src = img.get("src", "")
    if "rukminim" in src or "fk-p-l5p" in src:
        print(f"  Class: {img.get('class', [])} | {src[:80]}")

# ── 8. Review containers ──
print("\n─" * 40)
print("8️⃣  Review containers (any div with review-like text):")
for div in soup.find_all("div"):
    text = div.get_text(strip=True)
    classes = div.get("class", [])
    # Look for divs that are likely review containers
    if classes and 50 < len(text) < 500:
        if any(word in text.lower() for word in ["product", "quality", "good", "bad", "recommend", "love", "hate", "camera", "battery", "screen"]):
            print(f"  Class: {classes} | {text[:100]}...")

# ── 9. Ratings ──
print("\n─" * 40)
print("9️⃣  Rating elements (numbers 1.0-5.0):")
for elem in soup.find_all(text=re.compile(r'^[1-5]\.\d$')):
    parent = elem.parent
    print(f"  <{parent.name}> class={parent.get('class', [])} | {str(elem).strip()}")

print("\n" + "=" * 60)
print("✅ Debug complete! Share the output above to fix selectors.")
print("=" * 60)
