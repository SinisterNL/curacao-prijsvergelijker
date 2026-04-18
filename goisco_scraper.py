"""
Goisco Supermarket Scraper
Uses Goisco's public Shopify products.json API — no login required.
Run: python goisco_scraper.py
Output: goisco_products.json + goisco_products.csv
"""

import requests
import json
import csv
import time
from datetime import datetime

BASE_URL = "https://goisco.com/products.json"
LIMIT = 250  # Max per page Shopify allows
OUTPUT_JSON = "goisco_products.json"
OUTPUT_CSV = "goisco_products.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_page(page: int) -> list:
    """Fetch one page of products from Shopify API."""
    params = {"limit": LIMIT, "page": page}
    try:
        response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("products", [])
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Page {page}: {e}")
        return []


def parse_product(raw: dict) -> dict:
    """Extract the fields we care about from a raw Shopify product."""
    variant = raw["variants"][0] if raw.get("variants") else {}

    price_str = variant.get("price", "0") or "0"
    compare_str = variant.get("compare_at_price") or None

    try:
        price = float(price_str)
    except ValueError:
        price = 0.0

    compare_price = None
    if compare_str:
        try:
            compare_price = float(compare_str)
        except ValueError:
            pass

    image_url = None
    if raw.get("images"):
        image_url = raw["images"][0].get("src")

    return {
        "id": raw.get("id"),
        "name": raw.get("title", "").strip(),
        "vendor": raw.get("vendor", "").strip(),
        "category": raw.get("product_type", "").strip(),
        "tags": raw.get("tags", []),
        "price_ang": round(price, 2),
        "compare_price_ang": round(compare_price, 2) if compare_price else None,
        "on_sale": compare_price is not None and compare_price > price,
        "sku": variant.get("sku", ""),
        "barcode": variant.get("barcode", ""),
        "unit_info": variant.get("title", ""),
        "available": variant.get("available", False),
        "image_url": image_url,
        "store": "goisco",
        "scraped_at": datetime.now().isoformat(),
    }


def scrape_all() -> list:
    """Loop through all pages until empty."""
    all_products = []
    page = 1

    print(f"Starting Goisco scrape at {datetime.now().strftime('%H:%M:%S')}")
    print(f"Endpoint: {BASE_URL}\n")

    while True:
        print(f"  Fetching page {page}...", end=" ")
        raw_products = fetch_page(page)

        if not raw_products:
            print("empty — done.")
            break

        parsed = [parse_product(p) for p in raw_products]
        all_products.extend(parsed)
        print(f"{len(raw_products)} products (total: {len(all_products)})")

        if len(raw_products) < LIMIT:
            # Last page
            break

        page += 1
        time.sleep(0.5)  # Be polite, don't hammer the server

    return all_products


def save_json(products: list):
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print(f"\nJSON saved: {OUTPUT_JSON} ({len(products)} products)")


def save_csv(products: list):
    if not products:
        return
    fields = list(products[0].keys())
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in products:
            row = p.copy()
            row["tags"] = ", ".join(row["tags"]) if isinstance(row["tags"], list) else row["tags"]
            writer.writerow(row)
    print(f"CSV saved:  {OUTPUT_CSV}")


def print_summary(products: list):
    if not products:
        print("No products found.")
        return

    prices = [p["price_ang"] for p in products if p["price_ang"] > 0]
    on_sale = [p for p in products if p["on_sale"]]
    unavailable = [p for p in products if not p["available"]]

    categories = {}
    for p in products:
        cat = p["category"] or "Uncategorized"
        categories[cat] = categories.get(cat, 0) + 1

    print("\n" + "=" * 45)
    print("SCRAPE SUMMARY")
    print("=" * 45)
    print(f"Total products:    {len(products)}")
    print(f"On sale:           {len(on_sale)}")
    print(f"Out of stock:      {len(unavailable)}")
    if prices:
        print(f"Price range:       ANG {min(prices):.2f} – ANG {max(prices):.2f}")
        print(f"Average price:     ANG {sum(prices)/len(prices):.2f}")
    print(f"\nTop categories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:10]:
        print(f"  {cat:<30} {count}")
    print("=" * 45)


if __name__ == "__main__":
    products = scrape_all()
    if products:
        save_json(products)
        save_csv(products)
        print_summary(products)
    else:
        print("No products scraped. Check your internet connection.")
