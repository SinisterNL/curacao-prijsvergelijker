"""
prepare_data.py
Merges Goisco + Mangusa data and matches.json into one data.js for the frontend.
Run after scrapers and matcher: python prepare_data.py
"""

import json
import os
from datetime import datetime

OUTPUT_FILE  = "data.js"
MAX_NAME_LEN = 60

CATEGORY_MAP_GOISCO = {
    "Snacks & Sweets":           "Snacks",
    "Nutrition":                 "Gezondheid",
    "Beverages":                 "Dranken",
    "Body Care":                 "Verzorging",
    "Frozen Foods":              "Diepvries",
    "Alcohol & Tobacco":         "Alcohol",
    "Dairy & Eggs":              "Zuivel & Eieren",
    "Cleaning":                  "Schoonmaak",
    "Laundry":                   "Was & Schoonmaak",
    "Plastic & Foil Supplies":   "Huishouden",
    "Paper Supplies":            "Huishouden",
    "Meat, Chicken & Seafood":   "Vlees & Vis",
    "Fresh Fruits & Vegetables": "Groente & Fruit",
    "Bakery":                    "Brood & Bakkerij",
    "Condiments":                "Sauzen & Kruiden",
    "Breakfast & Spreads":       "Ontbijt",
    "Canned & Jarred Goods":     "Houdbaar",
    "Pasta, Rice & Grains":      "Pasta & Rijst",
    "Baby & Toddler":            "Baby",
    "Pet Supplies":              "Dieren",
    "Sports & Outdoors":         "Sport",
    "Electronics":               "Overig",
    "Home & Garden":             "Huishouden",
    "Clothing":                  "Overig",
    "Toys & Games":              "Overig",
    "Office Supplies":           "Overig",
}

def clean_name(name: str) -> str:
    name = name.strip()
    if len(name) > MAX_NAME_LEN:
        name = name[:MAX_NAME_LEN - 3] + "..."
    return name

def process():
    print(f"Running prepare_data.py at {datetime.now().strftime('%H:%M:%S')}\n")

    # ── Load raw data ──────────────────────────────────
    print("Loading Goisco products...")
    with open("goisco_products.json", encoding="utf-8") as f:
        goisco_raw = json.load(f)

    print("Loading Mangusa products...")
    with open("mangusa_products.json", encoding="utf-8") as f:
        mangusa_raw = json.load(f)

    # Index by ID for fast lookup
    goisco_by_id  = {p["id"]: p for p in goisco_raw}
    mangusa_by_id = {p["id"]: p for p in mangusa_raw}

    # ── Load matches ───────────────────────────────────
    matches = []
    if os.path.exists("matches.json"):
        print("Loading matches...")
        with open("matches.json", encoding="utf-8") as f:
            matches = json.load(f)
        print(f"  {len(matches)} matched product pairs\n")
    else:
        print("  matches.json not found — skipping comparison cards\n")

    # Track which IDs are already in a comparison card
    matched_goisco_ids  = {m["goisco_id"] for m in matches}
    matched_mangusa_ids = {m["mangusa_id"] for m in matches}

    products = []

    # ── 1. Comparison cards (matched products) ─────────
    for m in matches:
        g = goisco_by_id.get(m["goisco_id"])
        mn = mangusa_by_id.get(m["mangusa_id"])
        if not g or not mn:
            continue

        g_price  = m["goisco_price"]
        mn_price = m["mangusa_price"]
        cheaper  = m["cheaper"]
        saving   = m["saving"]

        # Use the better/cleaner name (longer = more info)
        name = g["name"] if len(g["name"]) >= len(mn["name"]) else mn["name"]

        raw_cat = g.get("product_type", "")
        cat = CATEGORY_MAP_GOISCO.get(raw_cat, mn.get("category", "Overig"))

        products.append({
            "id":           f"match_{g['id']}_{mn['id']}",
            "name":         clean_name(name),
            "cat":          cat,
            "type":         "comparison",
            "goisco_price": g_price,
            "mangusa_price":mn_price,
            "cheaper":      cheaper,
            "saving":       saving,
            "img":          g.get("image_url") or mn.get("image_url", ""),
            "score":        m["score"],
        })

    print(f"Comparison cards: {len(products)}")

    # ── 2. Goisco-only products ────────────────────────
    goisco_only = 0
    for p in goisco_raw:
        if p["id"] in matched_goisco_ids:
            continue
        if not p.get("available") or p.get("price_ang", 0) <= 0:
            continue
        raw_cat = p.get("product_type", "")
        cat = CATEGORY_MAP_GOISCO.get(raw_cat, raw_cat or "Overig")
        products.append({
            "id":      f"g_{p['id']}",
            "name":    clean_name(p["name"]),
            "vendor":  p.get("vendor", ""),
            "cat":     cat,
            "type":    "single",
            "store":   "goisco",
            "price":   p["price_ang"],
            "sale":    p.get("on_sale", False),
            "compare": p.get("compare_price_ang"),
            "img":     p.get("image_url", ""),
        })
        goisco_only += 1

    print(f"Goisco only:      {goisco_only}")

    # ── 3. Mangusa-only products ───────────────────────
    mangusa_only = 0
    for p in mangusa_raw:
        if p["id"] in matched_mangusa_ids:
            continue
        if not p.get("in_stock") or p.get("price_ang", 0) <= 0:
            continue
        products.append({
            "id":      f"m_{p['id']}",
            "name":    clean_name(p["name"]),
            "vendor":  "",
            "cat":     p.get("category", "Overig"),
            "type":    "single",
            "store":   "mangusa",
            "price":   p["price_ang"],
            "sale":    p.get("on_sale", False),
            "compare": p.get("regular_price") if p.get("on_sale") else None,
            "img":     p.get("image_url", ""),
        })
        mangusa_only += 1

    print(f"Mangusa only:     {mangusa_only}")

    # Sort: comparison cards first, then by category and name
    products.sort(key=lambda x: (
        0 if x["type"] == "comparison" else 1,
        x.get("cat", ""),
        x.get("name", "")
    ))

    # ── Write data.js ──────────────────────────────────
    total = len(products)
    js  = f"// Auto-generated by prepare_data.py — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    js += f"// {len(matches)} comparisons | {goisco_only} Goisco-only | {mangusa_only} Mangusa-only | {total} total\n"
    js += "const PRODUCTS = " + json.dumps(products, ensure_ascii=False, indent=2) + ";\n"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(js)

    print(f"\n{'='*45}")
    print("PREPARE SUMMARY")
    print(f"{'='*45}")
    print(f"  Comparisons:  {len(matches)}")
    print(f"  Goisco only:  {goisco_only}")
    print(f"  Mangusa only: {mangusa_only}")
    print(f"  TOTAL:        {total}")
    print(f"\n  Written to: {OUTPUT_FILE}")
    print(f"{'='*45}")

if __name__ == "__main__":
    process()
