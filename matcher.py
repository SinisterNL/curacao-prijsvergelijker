"""
matcher.py
Matches products between Goisco and Mangusa by normalized name similarity.
Run: python matcher.py
Output: matches.json
"""

import json
import re
import unicodedata
from difflib import SequenceMatcher

GOISCO_FILE  = "goisco_products.json"
MANGUSA_FILE = "mangusa_products.json"
OUTPUT_FILE  = "matches.json"

THRESHOLD    = 0.82   # Minimum similarity score (0-1)
MAX_PRICE_DIFF = 5.0  # Ignore matches where prices differ by more than ANG 5x

# ── Normalization ─────────────────────────────────────
UNIT_MAP = {
    r'\bltrs?\b':   'l',
    r'\bliters?\b': 'l',
    r'\blitre?s?\b':'l',
    r'\bml\b':      'ml',
    r'\bozs?\b':    'oz',
    r'\bfl\.?\s*oz\b': 'floz',
    r'\blbs?\b':    'lb',
    r'\bpounds?\b': 'lb',
    r'\bkgs?\b':    'kg',
    r'\bkilos?\b':  'kg',
    r'\bgrs?\b':    'g',
    r'\bgrams?\b':  'g',
    r'\bpcs?\b':    'pc',
    r'\bpieces?\b': 'pc',
    r'\bpacks?\b':  'pk',
    r'\bpkgs?\b':   'pk',
    r'\bct\b':      'ct',
    r'\bcount\b':   'ct',
}

BRAND_FIXES = {
    'coca cola':    'cocacola',
    'coca-cola':    'cocacola',
    'pepsi cola':   'pepsicola',
    'pepsi-cola':   'pepsicola',
    '7up':          '7up',
    '7 up':         '7up',
    'mc donalds':   'mcdonalds',
    "mcdonald's":   'mcdonalds',
}

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'with', 'for',
    'new', 'original', 'classic', 'natural', 'regular',
    'size', 'value', 'pack', 'set', 'box', 'bag', 'bottle',
    'can', 'jar', 'tube', 'bar', 'piece', 'pieces',
}

def remove_accents(text: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def normalize(name: str) -> str:
    if not name:
        return ""

    n = name.lower()
    n = remove_accents(n)

    # Apply brand fixes
    for raw, fixed in BRAND_FIXES.items():
        n = n.replace(raw, fixed)

    # Normalize units
    for pattern, replacement in UNIT_MAP.items():
        n = re.sub(pattern, replacement, n)

    # Remove special chars except digits and letters
    n = re.sub(r'[^\w\s]', ' ', n)

    # Collapse whitespace
    n = re.sub(r'\s+', ' ', n).strip()

    # Remove stopwords
    tokens = [t for t in n.split() if t not in STOPWORDS]
    n = ' '.join(tokens)

    return n

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def price_ratio(p1: float, p2: float) -> float:
    if p1 <= 0 or p2 <= 0:
        return 999
    return max(p1, p2) / min(p1, p2)

# ── Load data ─────────────────────────────────────────
def load_products(filename: str, price_field: str, available_field: str) -> list:
    with open(filename, encoding='utf-8') as f:
        raw = json.load(f)
    out = []
    for p in raw:
        price = p.get(price_field, 0) or 0
        if price <= 0 or price > 10000:
            continue
        available = p.get(available_field, True)
        if not available:
            continue
        out.append({
            'id':    p.get('id'),
            'name':  p.get('name', '').strip(),
            'norm':  normalize(p.get('name', '')),
            'price': price,
            'cat':   p.get('product_type') or p.get('category', ''),
            'img':   (p.get('images') or [{}])[0].get('src', '') if isinstance(p.get('images'), list) else p.get('image_url', ''),
            'store': p.get('store', ''),
        })
    return out

# ── Matching ──────────────────────────────────────────
def find_matches(goisco: list, mangusa: list) -> list:
    matches = []
    total   = len(goisco)

    print(f"Matching {total} Goisco products against {len(mangusa)} Mangusa products...")
    print("This may take a few minutes.\n")

    # Build Mangusa index by first token for speed
    mangusa_index = {}
    for m in mangusa:
        tokens = m['norm'].split()
        if tokens:
            key = tokens[0]
            mangusa_index.setdefault(key, []).append(m)

    for i, g in enumerate(goisco):
        if i % 100 == 0:
            print(f"  Progress: {i}/{total} ({100*i//total}%)")

        g_tokens = g['norm'].split()
        if not g_tokens:
            continue

        # Get candidates: same first token OR second token
        candidates = set()
        for token in g_tokens[:2]:
            for m in mangusa_index.get(token, []):
                candidates.add(id(m))

        best_score = 0
        best_match = None

        for m in mangusa:
            if id(m) not in candidates and len(candidates) > 0:
                continue  # Skip non-candidates for speed

            score = similarity(g['norm'], m['norm'])
            if score > best_score:
                best_score = score
                best_match = m

        if best_match and best_score >= THRESHOLD:
            # Extra check: price ratio shouldn't be insane
            ratio = price_ratio(g['price'], best_match['price'])
            if ratio <= MAX_PRICE_DIFF:
                matches.append({
                    'goisco_id':    g['id'],
                    'goisco_name':  g['name'],
                    'goisco_price': g['price'],
                    'mangusa_id':   best_match['id'],
                    'mangusa_name': best_match['name'],
                    'mangusa_price':best_match['price'],
                    'score':        round(best_score, 3),
                    'cheaper':      'goisco' if g['price'] < best_match['price'] else 'mangusa' if best_match['price'] < g['price'] else 'equal',
                    'saving':       round(abs(g['price'] - best_match['price']), 2),
                })

    return sorted(matches, key=lambda x: -x['score'])

def print_summary(matches: list):
    if not matches:
        print("No matches found.")
        return

    goisco_cheaper  = sum(1 for m in matches if m['cheaper'] == 'goisco')
    mangusa_cheaper = sum(1 for m in matches if m['cheaper'] == 'mangusa')
    equal           = sum(1 for m in matches if m['cheaper'] == 'equal')
    avg_saving      = sum(m['saving'] for m in matches) / len(matches)
    max_saving      = max(m['saving'] for m in matches)

    print("\n" + "=" * 50)
    print("MATCH SUMMARY")
    print("=" * 50)
    print(f"Total matches:       {len(matches)}")
    print(f"Goisco cheaper:      {goisco_cheaper}")
    print(f"Mangusa cheaper:     {mangusa_cheaper}")
    print(f"Same price:          {equal}")
    print(f"Average saving:      ANG {avg_saving:.2f}")
    print(f"Max saving:          ANG {max_saving:.2f}")
    print(f"\nTop 10 best matches:")
    for m in matches[:10]:
        print(f"  [{m['score']:.2f}] {m['goisco_name'][:35]:<35} G:{m['goisco_price']:.2f} | M:{m['mangusa_price']:.2f} | save ANG {m['saving']:.2f}")
    print("=" * 50)

if __name__ == "__main__":
    print("Loading products...")
    goisco  = load_products(GOISCO_FILE,  'price_ang', 'available')
    mangusa = load_products(MANGUSA_FILE, 'price_ang', 'in_stock')
    print(f"  Goisco:  {len(goisco)} products")
    print(f"  Mangusa: {len(mangusa)} products\n")

    matches = find_matches(goisco, mangusa)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(matches)} matches to {OUTPUT_FILE}")
    print_summary(matches)
