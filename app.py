"""
🦅 PRICEHAWK PRO - FLASK API BACKEND v3.0
Precisely tuned scrapers using confirmed working HTML selectors
Run: python api_server.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime, timezone
import hashlib

app = Flask(__name__)
CORS(app)

# ─── Supabase (optional) ────────────────────────────────────────────────────
SUPABASE_URL = "https://bjptvkqptlqsvknjjylj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJqcHR2a3FwdGxxc3ZrbmpqeWxqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAyNzM4NTksImV4cCI6MjA4NTg0OTg1OX0.NL6N6KwpbjpJSBYPgqbZ9BC29_d9Hpn0IWJvaFZIPH8"

try:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase connected")
except:
    supabase = None
    print("⚠️  Supabase not available - running without DB")


# ════════════════════════════════════════════════════════════════════════════
# URL HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _clean_url(url: str) -> str:
    """
    Strip all tracking/query params, keep only the canonical product URL.
    Flipkart item IDs are mixed-case: itmb07d67f995271 (lower) or MOBH4DQ (upper).
    """
    fk_match = re.match(r"(https://(?:www|m)\.flipkart\.com/[^?#]+/p/[a-zA-Z0-9]+)", url)
    if fk_match:
        return fk_match.group(1)

    az_match = re.match(r"(https://www\.amazon\.[a-z.]+/[^?#]*/dp/[A-Z0-9]{10})", url)
    if az_match:
        return az_match.group(1)

    return url


# ════════════════════════════════════════════════════════════════════════════
# PAGE FETCHERS
# Flipkart  → Playwright (Chromium) — Flipkart blocks all plain HTTP clients
# Amazon    → requests + BeautifulSoup — works perfectly, no Playwright needed
# ════════════════════════════════════════════════════════════════════════════

def _fetch_flipkart_playwright(url: str) -> str | None:
    """
    Flipkart returns 403 for every plain HTTP request regardless of headers.
    Playwright launches a real headless Chromium so the TLS fingerprint,
    JS execution, and cookie handling are identical to a real browser visit.
    BeautifulSoup then parses the fully-rendered HTML tags normally.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    clean = _clean_url(url)
    print(f"  → URL: {clean}")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                extra_http_headers={"Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8"},
            )
            # Hide the webdriver flag so Flipkart's JS bot-check passes
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = context.new_page()
            print("  → Launching Chromium for Flipkart…")
            page.goto(clean, wait_until="networkidle", timeout=45_000)
            # Wait for the price element — confirms the product page fully loaded
            try:
                page.wait_for_selector("div.Nx9bqj, div._30jeq3, div._16Jk6d", timeout=10_000)
            except PWTimeout:
                pass  # grab HTML anyway
            html = page.content()
            browser.close()

        if html and len(html) > 10_000:
            print(f"  ✅ Flipkart rendered ({len(html):,} chars)")
            return html
        print(f"  ❌ Flipkart page too small — likely blocked")
        return None

    except PWTimeout:
        print("  ❌ Playwright timeout on Flipkart")
        return None
    except Exception as exc:
        print(f"  ❌ Playwright error: {exc}")
        return None


def _fetch_amazon_requests(url: str) -> str | None:
    """
    Amazon India works fine with plain requests — no Playwright needed.
    Use realistic Chrome headers + homepage cookie seed + 2 retries.
    """
    clean = _clean_url(url)
    print(f"  → URL: {clean}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

    for attempt in range(2):
        try:
            session = requests.Session()
            session.headers.update(headers)
            # Seed session with homepage cookies
            try:
                session.get("https://www.amazon.in", timeout=10)
            except Exception:
                pass
            time.sleep(2)
            resp = session.get(clean, timeout=20, allow_redirects=True)
            print(f"  → HTTP {resp.status_code} (attempt {attempt + 1})")
            if resp.status_code == 200 and len(resp.text) > 10_000:
                print(f"  ✅ Amazon fetched ({len(resp.text):,} chars)")
                return resp.text
        except Exception as exc:
            print(f"  → Amazon request error (attempt {attempt + 1}): {exc}")
        time.sleep(3)

    print("  ❌ All Amazon attempts failed")
    return None


def fetch_page(url: str, platform: str) -> str | None:
    """Route each platform to its proven fetcher."""
    if platform == "flipkart":
        return _fetch_flipkart_playwright(url)
    else:
        return _fetch_amazon_requests(url)


# ════════════════════════════════════════════════════════════════════════════
# FLIPKART EXTRACTOR
# ════════════════════════════════════════════════════════════════════════════

def extract_flipkart(html: str) -> dict:
    """
    Extract all product data from a Flipkart product page.

    Working selector priority (confirmed):
    TITLE     : JSON-LD @type=Product -> name
                meta[property=og:title]  (strip trailing "- Buy ... | Flipkart")
                h1 span class B_NuCI
                title tag

    PRICE     : JSON-LD -> offers.price / offers.lowPrice
                div.Nx9bqj (current selling price)
                div._30jeq3 (older class)
                regex over raw HTML

    IMAGE     : JSON-LD -> image (list or str)
                meta[property=og:image]
                img src containing rukminim (Flipkart CDN)

    RATING    : JSON-LD -> aggregateRating.ratingValue
                div._3LWZlK or div.XQDdHH (star-badge divs)

    SPECS     : Full-text regex across entire HTML body
    CAT-RATINGS: div class _2x1Yo4 or regex fallback
    REVIEWS   : div class t-ZTKy containers; fallback keyword-match divs
    """
    soup = BeautifulSoup(html, "html.parser")
    data: dict = {"platform": "flipkart"}

    # ── 1. JSON-LD (most reliable when present) ──────────────────────────────
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string or ""
            if not raw.strip():
                continue
            blob = json.loads(raw)
            items = blob if isinstance(blob, list) else [blob]

            for item in items:
                if item.get("@type") != "Product":
                    continue

                if not data.get("title") and item.get("name"):
                    data["title"] = item["name"].strip()

                offers = item.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if not data.get("price"):
                    for price_key in ("price", "lowPrice"):
                        if offers.get(price_key):
                            try:
                                data["price"] = f"₹{int(float(offers[price_key])):,}"
                            except (ValueError, TypeError):
                                pass
                            break

                if not data.get("image"):
                    img = item.get("image")
                    if isinstance(img, list) and img:
                        data["image"] = img[0]
                    elif isinstance(img, str) and img:
                        data["image"] = img

                agg = item.get("aggregateRating", {})
                if not data.get("rating") and agg.get("ratingValue"):
                    try:
                        data["rating"] = round(float(agg["ratingValue"]), 1)
                    except (ValueError, TypeError):
                        pass

                brand = item.get("brand", {})
                if not data.get("brand"):
                    if isinstance(brand, dict):
                        data["brand"] = brand.get("name")
                    elif isinstance(brand, str):
                        data["brand"] = brand
        except (json.JSONDecodeError, Exception):
            continue

    # ── 2. Title fallbacks ────────────────────────────────────────────────────
    if not data.get("title"):
        og = soup.find("meta", {"property": "og:title"})
        if og and og.get("content"):
            title = og["content"]
            # Strip "- Buy … | Flipkart" noise
            title = re.sub(
                r"\s*[-|]\s*(Buy|Online|Price|Flipkart|Best).*$", "", title, flags=re.I
            ).strip()
            data["title"] = title

    if not data.get("title"):
        # h1 with class B_NuCI (Flipkart's main title span)
        h1 = soup.find("span", class_="B_NuCI")
        if h1:
            data["title"] = h1.get_text(strip=True)

    if not data.get("title"):
        tt = soup.find("title")
        if tt:
            data["title"] = re.sub(r"\s*[-|].*$", "", tt.get_text(), flags=re.I).strip()

    # ── 3. Price fallbacks ────────────────────────────────────────────────────
    if not data.get("price"):
        for cls in ("Nx9bqj", "_30jeq3", "_16Jk6d"):
            el = soup.find("div", class_=cls) or soup.find("span", class_=cls)
            if el:
                raw_price = el.get_text(strip=True).replace("₹", "").replace(",", "")
                try:
                    val = int(float(raw_price))
                    if 500 <= val <= 1_000_000:
                        data["price"] = f"₹{val:,}"
                        break
                except (ValueError, TypeError):
                    pass

    if not data.get("price"):
        # Fallback: regex scan entire HTML
        for m in re.finditer(r"₹\s*([\d,]+)", html):
            try:
                val = int(m.group(1).replace(",", ""))
                if 1_000 <= val <= 1_000_000:
                    data["price"] = f"₹{val:,}"
                    break
            except ValueError:
                pass

    # ── 4. Image fallbacks ────────────────────────────────────────────────────
    if not data.get("image"):
        og_img = soup.find("meta", {"property": "og:image"})
        if og_img and og_img.get("content"):
            data["image"] = og_img["content"]

    if not data.get("image"):
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "rukminim" in src or "fkimg" in src:
                data["image"] = src.split("?")[0]
                break

    # ── 5. Rating fallback ────────────────────────────────────────────────────
    if not data.get("rating"):
        for cls in ("_3LWZlK", "XQDdHH", "_1lRcqv"):
            el = soup.find("div", class_=cls) or soup.find("span", class_=cls)
            if el:
                try:
                    val = float(el.get_text(strip=True))
                    if 1.0 <= val <= 5.0:
                        data["rating"] = val
                        break
                except (ValueError, TypeError):
                    pass

    # ── 6. Specifications (full-HTML regex) ───────────────────────────────────
    # These regexes work because Flipkart embeds spec text directly in HTML.
    spec_patterns = {
        "ram":       r"(\d+\s*GB)\s+RAM",
        "storage":   r"(\d+\s*GB)\s+(?:ROM|Storage|Internal\s+Storage)",
        "processor": r"((?:Snapdragon|Dimensity|MediaTek|Exynos|Apple\s+A\d+\w*|Helio|Bionic|Kirin)[\w\s\d\+\-]+?)(?=\s*(?:Processor|Chipset|SoC|,|<|\n|RAM))",
        "camera":    r"(\d+\s*MP(?:\s+[\w\s]+)?(?:Primary|Main|Rear)\s*Camera|\d+\s*MP\s*(?:Rear|Front|Back)\s*Camera|\d+\s*MP\s*Camera)",
        "battery":   r"(\d{3,5}\s*mAh)",
        "display":   r"(\d{1,2}\.?\d*\s*inch|\d{3,4}\s*x\s*\d{3,4}\s*px|Full\s*HD\+?|AMOLED|Super\s*AMOLED|IPS\s*LCD|OLED)",
    }

    for field, pattern in spec_patterns.items():
        if not data.get(field):
            m = re.search(pattern, html, re.I)
            if m:
                data[field] = m.group(1).strip()[:60]

    # ── 7. Category Ratings ───────────────────────────────────────────────────
    # Flipkart shows category-wise ratings as divs like "Camera 4.2" or in JSON
    categories: dict = {}

    # Try structured extraction first
    for row in soup.find_all("div", class_=re.compile(r"_2x1Yo4|_3eDEzL|_3GUdgS")):
        text = row.get_text(" ", strip=True)
        for cat in ("Camera", "Battery", "Display", "Performance", "Design", "Value for Money"):
            m = re.search(rf"{cat}\s+([\d.]+)", text, re.I)
            if m:
                try:
                    categories[cat] = float(m.group(1))
                except ValueError:
                    pass

    # Generic fallback regex over full HTML
    if not categories:
        for cat in ("Camera", "Battery", "Display", "Performance", "Design"):
            m = re.search(rf"(?<!\w){cat}\s+([\d]\.[0-9])", html, re.I)
            if m:
                try:
                    val = float(m.group(1))
                    if 1.0 <= val <= 5.0:
                        categories[cat] = val
                except ValueError:
                    pass

    if categories:
        data["category_ratings"] = categories

    # ── 8. Reviews ────────────────────────────────────────────────────────────
    reviews: list = []

    # Primary: look for Flipkart's known review container classes
    # Class "t-ZTKy" wraps each individual review card
    review_cards = (
        soup.find_all("div", class_="t-ZTKy")
        or soup.find_all("div", attrs={"data-review-id": True})
        or []
    )

    for card in review_cards[:10]:
        try:
            # Rating: span/div with single digit 1-5
            rating_el = (
                card.find("div", class_="_11pzQk")
                or card.find("span", class_="_2_R_DZ")
                or card.find(string=re.compile(r"^[1-5]$"))
            )
            rating = 5
            if rating_el:
                try:
                    rating = int(str(rating_el if isinstance(rating_el, str)
                                     else rating_el.get_text(strip=True))[0])
                    if not 1 <= rating <= 5:
                        rating = 5
                except (ValueError, TypeError, IndexError):
                    rating = 5

            # Review body text
            body_el = (
                card.find("div", class_="row")
                or card.find("div", attrs={"class": re.compile(r"_6K-7Co|qwjRop")})
            )
            if not body_el:
                body_el = card

            text = body_el.get_text(" ", strip=True)
            text = re.sub(r"\s{2,}", " ", text).strip()

            # Skip very short or very long strings, or strings that are pure noise
            if 40 <= len(text) <= 600 and text not in [r["text"] for r in reviews]:
                reviews.append({"rating": rating, "text": text[:400]})
        except Exception:
            continue

    # Fallback: keyword-matched divs (original approach, works reliably)
    if len(reviews) < 3:
        REVIEW_KEYWORDS = {
            "camera", "battery", "display", "screen", "phone", "product",
            "quality", "good", "excellent", "best", "build", "performance",
            "fast", "value", "money", "happy", "satisfied",
        }
        for div in soup.find_all("div"):
            if len(reviews) >= 10:
                break
            text = div.get_text(" ", strip=True)
            if not (50 <= len(text) <= 800):
                continue
            words = set(text.lower().split())
            if len(words & REVIEW_KEYWORDS) < 2:
                continue
            if text in [r["text"] for r in reviews]:
                continue
            # Guess rating from first number 1-5
            m_r = re.search(r"\b([1-5])\b", text[:50])
            rating = int(m_r.group(1)) if m_r else 4
            cleaned = re.sub(
                r"(Certified Buyer|Verified (Buyer|Purchase)|\d+\s+\w+\s+ago)", "", text
            )
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if len(cleaned) >= 40:
                reviews.append({"rating": rating, "text": cleaned[:400]})

    data["reviews"] = reviews[:10]
    return data


# ════════════════════════════════════════════════════════════════════════════
# AMAZON EXTRACTOR
# ════════════════════════════════════════════════════════════════════════════

def extract_amazon(html: str) -> dict:
    """
    Extract all product data from an Amazon India product page.

    Working selector priority (confirmed for amazon.in):
    TITLE     : #productTitle span (most reliable, always present)
                #title span
                meta[name=title]
                title tag

    PRICE     : span.a-price-whole  (current price, digits only)
                .a-offscreen        (machine-readable "Rs.X,XXX" inside aria)
                span.priceToPay     (Deal / Lightning price)
                #priceblock_ourprice (older pages)

    IMAGE     : #landingImage[data-old-hires] (full-res)
                #landingImage[src]
                #imgTagWrapperId img
                JSON blob "hiRes" key in page scripts

    RATING    : span.a-icon-alt first occurrence "4.3 out of 5 stars"
                #acrPopover[title]

    BRAND     : #bylineInfo "Visit the BRAND Store" / "Brand: BRAND"
                a#brand

    SPECS     : #feature-bullets li span.a-list-item
                #productDetails_techSpec_section_1 td
                #prodDetails td
                regex fallback

    CAT-RATINGS: [data-hook=cr-summarization-attribute] rows
                 JSON "featureName"/"mean" blob fallback

    REVIEWS   : [data-hook=review]
                  .review-rating span.a-icon-alt
                  [data-hook=review-title] span
                  [data-hook=review-body] span
    """
    soup = BeautifulSoup(html, "html.parser")
    data: dict = {"platform": "amazon"}

    # ── 1. Title ─────────────────────────────────────────────────────────────
    for sel in ("#productTitle", "#title"):
        el = soup.select_one(sel)
        if el:
            data["title"] = el.get_text(strip=True)
            break

    if not data.get("title"):
        meta_title = soup.find("meta", {"name": "title"})
        if meta_title:
            data["title"] = meta_title.get("content", "").strip()

    if not data.get("title"):
        tt = soup.find("title")
        if tt:
            data["title"] = re.sub(r"\s*[-|:]\s*(Amazon\.in|Buy).*$", "", tt.get_text(), flags=re.I).strip()

    # ── 2. Price ─────────────────────────────────────────────────────────────
    def _parse_price(raw: str) -> str | None:
        digits = raw.replace("₹", "").replace(",", "").replace(".", "").strip()
        try:
            val = int(digits)
            if 100 <= val <= 2_000_000:
                return f"₹{val:,}"
        except (ValueError, TypeError):
            pass
        return None

    # span.a-price-whole gives plain digits like "18999"
    whole = soup.select_one("span.a-price-whole")
    if whole:
        raw = whole.get_text(strip=True).replace(".", "").replace(",", "")
        p = _parse_price(raw)
        if p:
            data["price"] = p

    # .a-offscreen gives full "₹18,999" – useful if whole is absent
    if not data.get("price"):
        for el in soup.select(".a-offscreen"):
            p = _parse_price(el.get_text(strip=True))
            if p:
                data["price"] = p
                break

    # priceToPay (Deal/Lightning)
    if not data.get("price"):
        el = soup.select_one("span.priceToPay span.a-price-whole")
        if el:
            p = _parse_price(el.get_text(strip=True))
            if p:
                data["price"] = p

    # Older selectors
    if not data.get("price"):
        for sel in ("#priceblock_ourprice", "#priceblock_dealprice", "#priceblock_saleprice"):
            el = soup.select_one(sel)
            if el:
                p = _parse_price(el.get_text(strip=True))
                if p:
                    data["price"] = p
                    break

    # ── 3. Image ─────────────────────────────────────────────────────────────
    img_el = soup.select_one("#landingImage")
    if img_el:
        src = img_el.get("data-old-hires") or img_el.get("src", "")
        if src and src.startswith("http"):
            data["image"] = src

    if not data.get("image"):
        for sel in ("#imgTagWrapperId img", "#main-image", "#imgBlkFront"):
            el = soup.select_one(sel)
            if el:
                src = el.get("data-old-hires") or el.get("src", "")
                if src and src.startswith("http"):
                    data["image"] = src
                    break

    # Amazon embeds hires image URLs in a JSON blob inside a script tag
    if not data.get("image"):
        m = re.search(r'"hiRes"\s*:\s*"(https://[^"]+\.jpg[^"]*)"', html)
        if m:
            data["image"] = m.group(1)

    # ── 4. Rating ─────────────────────────────────────────────────────────────
    # "4.3 out of 5 stars"
    for el in soup.select("span.a-icon-alt"):
        m = re.match(r"([\d.]+)\s+out of\s+5", el.get_text(strip=True))
        if m:
            try:
                val = float(m.group(1))
                if 1.0 <= val <= 5.0:
                    data["rating"] = val
                    break
            except ValueError:
                pass

    if not data.get("rating"):
        pop = soup.select_one("#acrPopover")
        if pop:
            m = re.search(r"([\d.]+)\s+out of\s+5", pop.get("title", ""))
            if m:
                try:
                    data["rating"] = float(m.group(1))
                except ValueError:
                    pass

    # ── 5. Brand ─────────────────────────────────────────────────────────────
    byline = soup.select_one("#bylineInfo")
    if byline:
        text = byline.get_text(strip=True)
        # "Visit the SAMSUNG Store" or "Brand: Samsung"
        m = re.search(r"(?:Visit the\s+|Brand:\s*)([A-Z][\w\s&]+?)(?:\s+Store|$)", text)
        if m:
            data["brand"] = m.group(1).strip()
        else:
            data["brand"] = text.strip()[:40]

    if not data.get("brand"):
        brand_el = soup.select_one("a#brand, #brand")
        if brand_el:
            data["brand"] = brand_el.get_text(strip=True)

    # ── 6. Specifications ─────────────────────────────────────────────────────
    # Collect all spec text from feature bullets + tech details tables
    spec_chunks: list[str] = []

    for li in soup.select("#feature-bullets li span.a-list-item"):
        spec_chunks.append(li.get_text(" ", strip=True))

    for td in soup.select(
        "#productDetails_techSpec_section_1 td, "
        "#prodDetails td, "
        "#productDetails_db_sections td, "
        "table.a-bordered td"
    ):
        spec_chunks.append(td.get_text(" ", strip=True))

    spec_text = " ".join(spec_chunks) + " " + " ".join(
        [li.get_text(" ", strip=True) for li in soup.select("#detailBullets_feature_div li")]
    )

    spec_patterns = {
        "ram":       r"(\d+\s*GB)\s+RAM",
        "storage":   r"(\d+\s*GB)\s+(?:ROM|Storage|Internal\s+Storage|Flash)",
        "processor": r"((?:Snapdragon|Dimensity|MediaTek|Exynos|Apple\s+A\d+\w*|Helio|Bionic|Kirin)[\w\s\d\+\-]+?)(?=\s*(?:Processor|Chipset|SoC|,|$|\n))",
        "camera":    r"(\d+\s*MP(?:\s+[\w\s]+)?(?:Primary|Main|Rear)?\s*Camera|\d+\s*MP\s*(?:Rear|Front|Back)\s*Camera)",
        "battery":   r"(\d{3,5}\s*mAh)",
        "display":   r"(\d{1,2}\.?\d*\s*inch(?:es)?|Full\s*HD\+?|AMOLED|Super\s*AMOLED|IPS\s*LCD|OLED)",
    }

    for field, pattern in spec_patterns.items():
        if not data.get(field):
            # Try spec_text first, fall back to full HTML
            for haystack in (spec_text, html):
                m = re.search(pattern, haystack, re.I)
                if m:
                    data[field] = m.group(1).strip()[:60]
                    break

    # ── 7. Category Ratings ───────────────────────────────────────────────────
    categories: dict = {}

    # Amazon's "star histogram" shows per-feature ratings in cr-summarization rows
    for row in soup.select("[data-hook='cr-summarization-attribute']"):
        name_el = row.select_one(".a-size-base")
        score_el = row.select_one(".a-icon-alt, .cr-widget-histogram span")
        if name_el and score_el:
            m = re.search(r"([\d.]+)", score_el.get_text())
            if m:
                try:
                    categories[name_el.get_text(strip=True)] = float(m.group(1))
                except ValueError:
                    pass

    # Regex fallback over full HTML
    if not categories:
        for m in re.finditer(r'"featureName"\s*:\s*"([^"]+)".*?"mean"\s*:\s*([\d.]+)', html):
            try:
                categories[m.group(1)] = float(m.group(2))
            except ValueError:
                pass

    if categories:
        data["category_ratings"] = {k: v for k, v in list(categories.items())[:6]}

    # ── 8. Reviews ────────────────────────────────────────────────────────────
    reviews: list = []

    for card in soup.select("[data-hook='review']")[:10]:
        try:
            # Rating: "4.0 out of 5 stars"
            rating_el = card.select_one(".review-rating span.a-icon-alt")
            if not rating_el:
                rating_el = card.select_one("span.a-icon-alt")
            rating = 5
            if rating_el:
                m = re.match(r"([\d.]+)", rating_el.get_text(strip=True))
                if m:
                    try:
                        rating = int(float(m.group(1)))
                    except ValueError:
                        pass

            # Review title
            title_el = card.select_one("[data-hook='review-title'] span:not(.a-icon-alt)")
            title_text = title_el.get_text(strip=True) if title_el else ""

            # Review body
            body_el = (
                card.select_one("[data-hook='review-body'] span")
                or card.select_one(".review-text-content span")
                or card.select_one("[data-hook='review-collapsed'] span")
            )
            body_text = body_el.get_text(" ", strip=True) if body_el else ""

            # Combine title + body
            full_text = f"{title_text} — {body_text}".strip(" —").strip()
            full_text = re.sub(r"\s+", " ", full_text)

            if len(full_text) >= 30 and full_text not in [r["text"] for r in reviews]:
                reviews.append({"rating": rating, "text": full_text[:400]})
        except Exception:
            continue

    # Fallback: review-text-content (older page layouts)
    if len(reviews) < 3:
        for el in soup.select(".review-text-content")[:10]:
            text = el.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) >= 40 and text not in [r["text"] for r in reviews]:
                reviews.append({"rating": 4, "text": text[:400]})

    data["reviews"] = reviews[:10]
    return data


# ════════════════════════════════════════════════════════════════════════════
# AI SCORING
# ════════════════════════════════════════════════════════════════════════════

def calculate_ai_recommendation(data: dict) -> dict:
    """
    Score a product 0-100 across four dimensions and produce a verdict.

    Breakdown:
      Rating score   :  0–40  (based on numerical star rating)
      Sentiment score:  0–30  (positive-review ratio from scraped reviews)
      Category score :  0–20  (average category-wise rating)
      Specs score    :  0–10  (completeness of specification fields)
    """
    score = 0.0
    reasons: list[str] = []
    breakdown = {
        "rating_score": 0,
        "sentiment_score": 0,
        "category_score": 0,
        "specs_score": 0,
    }

    # ── Rating (40 pts) ───────────────────────────────────────────────────────
    rating = data.get("rating")
    if rating:
        if rating >= 4.5:
            rs = 40
            reasons.append(f"Exceptional {rating}/5 customer rating")
        elif rating >= 4.0:
            rs = 33
            reasons.append(f"Excellent {rating}/5 customer rating")
        elif rating >= 3.5:
            rs = 25
            reasons.append(f"Good {rating}/5 customer rating")
        elif rating >= 3.0:
            rs = 16
            reasons.append(f"Average {rating}/5 customer rating")
        else:
            rs = 8
            reasons.append(f"Low {rating}/5 customer rating")
        score += rs
        breakdown["rating_score"] = rs

    # ── Sentiment (30 pts) ────────────────────────────────────────────────────
    reviews = data.get("reviews", [])
    if len(reviews) >= 2:
        positive = sum(1 for r in reviews if r.get("rating", 0) >= 4)
        ratio = positive / len(reviews)
        if ratio >= 0.9:
            ss = 30
            reasons.append(f"{round(ratio * 100)}% of reviews are positive")
        elif ratio >= 0.75:
            ss = 24
            reasons.append(f"{round(ratio * 100)}% positive review sentiment")
        elif ratio >= 0.6:
            ss = 17
            reasons.append(f"{round(ratio * 100)}% positive review sentiment")
        else:
            ss = 8
            reasons.append("Mixed or mostly negative reviews")
        score += ss
        breakdown["sentiment_score"] = ss

    # ── Category Ratings (20 pts) ─────────────────────────────────────────────
    cat_ratings = data.get("category_ratings", {})
    if cat_ratings:
        avg = sum(cat_ratings.values()) / len(cat_ratings)
        cs = round((avg / 5.0) * 20, 1)
        score += cs
        breakdown["category_score"] = cs
        stars = [cat for cat, v in cat_ratings.items() if v >= 4.5]
        if stars:
            reasons.append(f"Outstanding {', '.join(stars[:2])} performance")

    # ── Specs completeness (10 pts) ───────────────────────────────────────────
    spec_fields = ["ram", "storage", "processor", "camera", "battery", "display"]
    present = sum(1 for f in spec_fields if data.get(f))
    sps = round((present / len(spec_fields)) * 10, 1)
    score += sps
    breakdown["specs_score"] = sps
    if present >= 5:
        reasons.append(f"Detailed specifications available ({present}/{len(spec_fields)})")
    elif present >= 3:
        reasons.append(f"Partial specs available ({present}/{len(spec_fields)})")

    # ── Finalise ─────────────────────────────────────────────────────────────
    final = min(100, max(0, round(score)))

    if final >= 85:
        verdict = "🟢 Highly Recommended"
    elif final >= 72:
        verdict = "🟢 Recommended"
    elif final >= 58:
        verdict = "🟡 Worth Considering"
    elif final >= 42:
        verdict = "🟡 Proceed with Caution"
    else:
        verdict = "🔴 Not Recommended"

    return {
        "ai_score": final,
        "ai_verdict": verdict,
        "ai_reasons": reasons[:5],
        "ai_breakdown": breakdown,
    }


# ════════════════════════════════════════════════════════════════════════════
# DATABASE HELPER
# ════════════════════════════════════════════════════════════════════════════

def save_to_supabase(data: dict, url: str, comparison_id: str | None = None) -> str | None:
    if not supabase:
        return None
    try:
        product_id = hashlib.md5(url.encode()).hexdigest()[:20]

        # Only include columns that exist in the Supabase products table.
        # If you want to store 'display', run this SQL in Supabase first:
        #   ALTER TABLE products ADD COLUMN display TEXT;
        product_data = {
            "id": product_id,
            "comparison_id": comparison_id,
            "platform": data.get("platform"),
            "url": url,
            "title": data.get("title"),
            "price": data.get("price"),
            "brand": data.get("brand"),
            "image": data.get("image"),
            "rating": data.get("rating"),
            "ram": data.get("ram"),
            "storage": data.get("storage"),
            "processor": data.get("processor"),
            "camera": data.get("camera"),
            "battery": data.get("battery"),
            # "display": data.get("display"),  # Uncomment after: ALTER TABLE products ADD COLUMN display TEXT;
            "category_ratings": json.dumps(data.get("category_ratings", {})),
            "ai_score": data.get("ai_score"),
            "ai_verdict": data.get("ai_verdict"),
            "ai_reasons": json.dumps(data.get("ai_reasons", [])),
            "ai_breakdown": json.dumps(data.get("ai_breakdown", {})),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        supabase.table("products").upsert(product_data, on_conflict="id").execute()

        for rev in data.get("reviews", [])[:10]:
            supabase.table("reviews").insert({
                "product_id": product_id,
                "rating": rev.get("rating"),
                "text": rev.get("text"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()

        return product_id
    except Exception as exc:
        print(f"  ❌ DB error: {exc}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# API ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return jsonify({
        "name": "🦅 PriceHawk Pro API",
        "status": "running",
        "version": "3.0",
        "endpoints": {
            "GET /api/compare": "?flipkart_url=...&amazon_url=...",
            "GET /api/dashboard": "Returns saved products",
        },
    })


@app.route("/api/dashboard")
def dashboard():
    if not supabase:
        return jsonify({"error": "Database not configured"}), 500
    try:
        result = (
            supabase.table("products")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        for product in result.data:
            for field in ("category_ratings", "ai_reasons", "ai_breakdown"):
                raw = product.get(field)
                if raw:
                    try:
                        product[field] = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        product[field] = {} if field != "ai_reasons" else []
        return jsonify({"status": "success", "products": result.data, "count": len(result.data)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/compare", methods=["GET"])
def compare_products():
    """
    Main comparison endpoint.
    Query params:
        flipkart_url  – Flipkart product page URL (optional)
        amazon_url    – Amazon India product page URL (optional)
    At least one must be provided.
    """
    flipkart_url = request.args.get("flipkart_url", "").strip()
    amazon_url   = request.args.get("amazon_url", "").strip()

    if not flipkart_url and not amazon_url:
        return jsonify({"error": "Please provide at least one product URL"}), 400

    print(f"\n{'═'*70}")
    print(f"🦅  NEW COMPARISON")
    if flipkart_url:
        print(f"  Flipkart : {flipkart_url[:80]}")
    if amazon_url:
        print(f"  Amazon   : {amazon_url[:80]}")
    print(f"{'═'*70}")

    comparison_id = hashlib.md5(
        f"{flipkart_url}{amazon_url}{time.time()}".encode()
    ).hexdigest()[:20]

    results: dict = {
        "flipkart": None,
        "amazon": None,
        "winner": None,
        "price_difference": None,
        "status": "success",
    }

    # ── Flipkart ──────────────────────────────────────────────────────────────
    if flipkart_url:
        print("\n📱 Fetching Flipkart…")
        html = fetch_page(flipkart_url, "flipkart")
        if html:
            fk = extract_flipkart(html)
            if fk.get("title") or fk.get("price"):
                fk.update(calculate_ai_recommendation(fk))
                fk["url"] = flipkart_url
                results["flipkart"] = fk
                save_to_supabase(fk, flipkart_url, comparison_id)
                print(f"  Title    : {fk.get('title', 'N/A')[:60]}")
                print(f"  Price    : {fk.get('price', 'N/A')}")
                print(f"  Rating   : {fk.get('rating', 'N/A')}")
                print(f"  AI Score : {fk.get('ai_score')}/100")
                print(f"  Reviews  : {len(fk.get('reviews', []))}")
            else:
                print("  ⚠️  No usable data extracted from Flipkart page.")
        else:
            print("  ❌  Failed to fetch Flipkart page.")

    # ── Amazon ────────────────────────────────────────────────────────────────
    if amazon_url:
        time.sleep(2)
        print("\n📦 Fetching Amazon…")
        html = fetch_page(amazon_url, "amazon")
        if html:
            az = extract_amazon(html)
            if az.get("title") or az.get("price"):
                az.update(calculate_ai_recommendation(az))
                az["url"] = amazon_url
                results["amazon"] = az
                save_to_supabase(az, amazon_url, comparison_id)
                print(f"  Title    : {az.get('title', 'N/A')[:60]}")
                print(f"  Price    : {az.get('price', 'N/A')}")
                print(f"  Rating   : {az.get('rating', 'N/A')}")
                print(f"  AI Score : {az.get('ai_score')}/100")
                print(f"  Reviews  : {len(az.get('reviews', []))}")
            else:
                print("  ⚠️  No usable data extracted from Amazon page.")
        else:
            print("  ❌  Failed to fetch Amazon page.")

    # ── Winner ────────────────────────────────────────────────────────────────
    if results["flipkart"] and results["amazon"]:
        f_score = results["flipkart"].get("ai_score", 0)
        a_score = results["amazon"].get("ai_score", 0)

        if abs(f_score - a_score) < 3:
            results["winner"] = "tie"
        elif f_score > a_score:
            results["winner"] = "flipkart"
        else:
            results["winner"] = "amazon"

        print(f"\n  🏆 Winner : {results['winner'].upper()}")

        # Price delta
        try:
            f_val = float(results["flipkart"]["price"].replace("₹", "").replace(",", ""))
            a_val = float(results["amazon"]["price"].replace("₹", "").replace(",", ""))
            diff = abs(f_val - a_val)
            cheaper = "flipkart" if f_val < a_val else "amazon"
            results["price_difference"] = {
                "amount": round(diff, 2),
                "cheaper_on": cheaper,
                "percentage": round((diff / max(f_val, a_val)) * 100, 1),
            }
            print(f"  💰 ₹{diff:,.0f} cheaper on {cheaper}")
        except Exception:
            pass

    elif results["flipkart"]:
        results["winner"] = "flipkart"
    elif results["amazon"]:
        results["winner"] = "amazon"

    print(f"\n{'═'*70}\n")
    return jsonify(results)


# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═" * 70)
    print("🦅  PRICEHAWK PRO  —  API SERVER v3.0")
    print("═" * 70)
    print("  Server  : http://127.0.0.1:5000")
    print("  CORS    : enabled for all origins")
    print(f"  DB      : {'Supabase connected' if supabase else 'not configured'}")
    print("═" * 70 + "\n")
    app.run(debug=True, port=5000, host="0.0.0.0")