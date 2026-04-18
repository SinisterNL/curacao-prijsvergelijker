"""
centrum_monitor.py
Checks if Centrum Supermarket's Shopify store is back online.
Run manually or via GitHub Actions daily.
Exits with code 1 if online (triggers notification), 0 if still offline.
"""

import requests
import json
import os
from datetime import datetime

CHECK_URL   = "https://centrumsupermarket.com/products.json?limit=3"
STATUS_FILE = "centrum_status.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def check_centrum() -> dict:
    status = {
        "checked_at": datetime.now().isoformat(),
        "online": False,
        "product_count": 0,
        "message": ""
    }

    try:
        resp = requests.get(CHECK_URL, headers=HEADERS, timeout=15)

        if resp.status_code == 200:
            try:
                data = resp.json()
                products = data.get("products", [])
                if products:
                    status["online"]        = True
                    status["product_count"] = len(products)
                    status["message"]       = f"ONLINE — {len(products)} products found on first page"
                else:
                    status["message"] = "Responded but no products returned"
            except Exception:
                body = resp.text[:200]
                if "Unavailable" in body or "unavailable" in body:
                    status["message"] = "Store is unavailable (Shopify suspended)"
                else:
                    status["message"] = f"Unexpected response: {body}"
        else:
            status["message"] = f"HTTP {resp.status_code}"

    except requests.exceptions.RequestException as e:
        status["message"] = f"Connection error: {e}"

    return status

def load_previous() -> dict:
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"online": False}

def save_status(status: dict):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

if __name__ == "__main__":
    print(f"Checking Centrum Supermarket at {datetime.now().strftime('%H:%M:%S')}...")
    print(f"URL: {CHECK_URL}\n")

    previous = load_previous()
    current  = check_centrum()

    print(f"Status:  {'ONLINE' if current['online'] else 'OFFLINE'}")
    print(f"Message: {current['message']}")
    print(f"Time:    {current['checked_at']}")

    was_offline = not previous.get("online", False)
    is_online   = current["online"]

    if is_online and was_offline:
        print("\n" + "=" * 50)
        print("CENTRUM IS BACK ONLINE!")
        print("Run centrum_scraper.py to scrape their products.")
        print("=" * 50)

    save_status(current)

    # Exit code 1 signals GitHub Actions that centrum just came online
    # This can be used to trigger notifications
    exit(0 if not (is_online and was_offline) else 1)
