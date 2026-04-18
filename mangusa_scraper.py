"""
Mangusa Hypermarket Scraper
Uses Mangusa's public WooCommerce Store API — no login required.
Run: python mangusa_scraper.py
Output: mangusa_products.json
"""

import requests
import json
import time
from datetime import datetime

BASE_URL    = "https://www.mangusahypermarket.com/wp-json/wc/store/v1/products"
PER_PAGE    = 100
OUTPUT_FILE = "mangusa_products.json"
MAX_PRICE   = 10000.0  # Anything above ANG 10,000 is corrupt data

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Keyword-based matching — checks if keyword appears anywhere in category name
CATEGORY_KEYWORDS = {
    "meat":         "Vlees & Vis",
    "poultry":      "Vlees & Vis",
    "fish":         "Vlees & Vis",
    "pork":         "Vlees & Vis",
    "seafood":      "Vlees & Vis",
    "karni":        "Vlees & Vis",
    "piska":        "Vlees & Vis",
    "salad":        "Groente & Fruit",
    "vegetable":    "Groente & Fruit",
    "fruit":        "Groente & Fruit",
    "herb":         "Groente & Fruit",
    "baker":        "Brood & Bakkerij",
    "bread":        "Brood & Bakkerij",
    "panaderia":    "Brood & Bakkerij",
    "deli":         "Vleeswaren",
    "beleg":        "Vleeswaren",
    "dairy":        "Zuivel & Eieren",
    "lechi":        "Zuivel & Eieren",
    "egg":          "Zuivel & Eieren",
    "cheese":       "Zuivel & Eieren",
    "frozen":       "Diepvries",
    "konhela":      "Diepvries",
    "beverage":     "Dranken",
    "bibida":       "Dranken",
    "juice":        "Dranken",
    "djus":         "Dranken",
    "water":        "Dranken",
    "soda":         "Dranken",
    "canned":       "Houdbaar",
    "lata":         "Houdbaar",
    "condiment":    "Sauzen & Kruiden",
    "sauce":        "Sauzen & Kruiden",
    "oil":          "Sauzen & Kruiden",
    "spice":        "Sauzen & Kruiden",
    "grain":        "Pasta & Rijst",
    "pasta":        "Pasta & Rijst",
    "rice":         "Pasta & Rijst",
    "arros":        "Pasta & Rijst",
    "breakfast":    "Ontbijt",
    "cereal":       "Ontbijt",
    "desayuno":     "Ontbijt",
    "snack":        "Snacks",
    "candy":        "Snacks",
    "sweet":        "Snacks",
    "chocolate":    "Snacks",
    "cookie":       "Snacks",
    "chip":         "Snacks",
    "cleaning":     "Schoonmaak",
    "limpiesa":     "Schoonmaak",
    "laundry":      "Was & Schoonmaak",
    "ropa":         "Was & Schoonmaak",
    "personal care":"Verzorging",
    "kuido":        "Verzorging",
    "hair":         "Verzorging",
    "kabei":        "Verzorging",
    "skin":         "Verzorging",
    "body":         "Verzorging",
    "oral":         "Verzorging",
    "medical":      "Gezondheid",
    "botika":       "Gezondheid",
    "vitamin":      "Gezondheid",
    "baby":         "Baby",
    "bebe":         "Baby",
    "infant":       "Baby",
    "pet":          "Dieren",
    "animal":       "Dieren",
    "alcohol":      "Alcohol",
    "alkohol":      "Alcohol",
    "wine":         "Alcohol",
    "beer":         "Alcohol",
    "spirit":       "Alcohol",
    "household":    "Huishouden",
    "kitchen":      "Huishouden",
    "paper":        "Huishouden",
    "plastic":      "Huishouden",
    "office":       "Huishouden",
    "school":       "Huishouden",
    "kas":          "Huishouden",
}

def map_category(categories: list) -> str:
    """Match category using keywords against all category names."""
    for cat in categories:
        name = cat.get("name", "").lower()
        for keyword, mapped in CATEGORY_KEYWORDS.items():
            if keyword in name:
                return mapped
    if categories:
        raw = categories[0].get("name", "Overig")
        return raw.split("/")[0].strip()
    return "Overig"

def parse_product(raw: dict):
    """Extract fields. Returns None for corrupt/invalid prices."""
    prices  = raw.get("prices", {})
    minor   = int(prices.get("currency_minor_unit", 2))
    divisor = 10 ** minor

    def to_float(val):
        try:
            return round(int(val) / divisor, 2)
        except (TypeError, ValueError):
            return 0.0

    price         = to_float(prices.get("price"))
    regular_price = to_float(prices.get("regular_price"))
    sale_price    = to_float(prices.get("sale_price"))
    on_sale       = raw.get("on_sale", False)

    # Filter out corrupt/zero prices
    if price <= 0 or price > MAX_PRICE:
        return None

    images     = raw.get("images", [])
    image_url  = images[0].get("src") if images else None
    categories = raw.get("categories", [])

    return {
        "id":           raw.get("id"),
        "name":         raw.get("name", "").strip(),
        "sku":          raw.get("sku", ""),
        "category":     map_category(categories),
        "price_ang":    price,
        "regular_price":regular_price,
        "sale_price":   sale_price if on_sale else None,
        "on_sale":      on_sale,
        "in_stock":     raw.get("is_in_stock", False),
        "image_url":    image_url,
        "store":        "mangusa",
        "scraped_at":   datetime.now().isoformat(),
    }

def fetch_page(page: int):
    """Fetch one page. Returns (products, total_pages)."""
    params = {"per_page": PER_PAGE, "page": page}
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        return resp.json(), total_pages
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Page {page}: {e}")
        return [], 1

def scrape_all() -> list:
    print(f"Starting Mangusa scrape at {datetime.now().strftime('%H:%M:%S')}")
    print(f"Endpoint: {BASE_URL}\n")

    first_page, total_pages = fetch_page(1)
    if not first_page:
        print("No products found on page 1.")
        return []

    all_products = [p for p in (parse_product(r) for r in first_page) if p]
    skipped = len(first_page) - len(all_products)
    print(f"  Page 1/{total_pages}: {len(first_page)} raw, {len(all_products)} valid (skipped {skipped})")

    for page in range(2, total_pages + 1):
        raw_list, _ = fetch_page(page)
        if not raw_list:
            print(f"  Page {page}: empty — stopping.")
            break
        parsed = [p for p in (parse_product(r) for r in raw_list) if p]
        skipped = len(raw_list) - len(parsed)
        all_products.extend(parsed)
        print(f"  Page {page}/{total_pages}: {len(raw_list)} raw, {len(parsed)} valid (skipped {skipped}) — total: {len(all_products)}")
        time.sleep(0.5)

    return all_products

def save_json(products: list):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print(f"\nJSON saved: {OUTPUT_FILE} ({len(products)} products)")

def print_summary(products: list):
    if not products:
        print("No products found.")
        return

    in_stock = [p for p in products if p["in_stock"]]
    on_sale  = [p for p in products if p["on_sale"]]
    prices   = [p["price_ang"] for p in products if p["price_ang"] > 0]

    cats = {}
    for p in products:
        c = p["category"]
        cats[c] = cats.get(c, 0) + 1

    print("\n" + "=" * 45)
    print("SCRAPE SUMMARY — MANGUSA")
    print("=" * 45)
    print(f"Total products:    {len(products)}")
    print(f"In stock:          {len(in_stock)}")
    print(f"On sale:           {len(on_sale)}")
    if prices:
        print(f"Price range:       ANG {min(prices):.2f} – ANG {max(prices):.2f}")
        print(f"Average price:     ANG {sum(prices)/len(prices):.2f}")
    print(f"\nTop categories:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cat:<28} {count}")
    print("=" * 45)

if __name__ == "__main__":
    products = scrape_all()
    if products:
        save_json(products)
        print_summary(products)
    else:
        print("No products scraped.")
