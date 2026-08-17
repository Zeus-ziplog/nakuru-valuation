from geopy.geocoders import Nominatim
import time
import os
import re

geolocator_nominatim = Nominatim(user_agent="nakuru_valuation", timeout=15)

# ---- Manual mapping – now using substring matching (case-insensitive) ----
ESTATE_COORDS = {
    # Existing estates
    "nakuru grove gardens": (-0.2900, 36.0700),
    "nakuru opal estate": (-0.2850, 36.0750),
    "havanna": (-0.2950, 36.0800),
    "springfield": (-0.2800, 36.0650),
    "delight": (-0.2750, 36.0700),
    "hamptons": (-0.2700, 36.0600),
    "nakuru harmony gardens": (-0.2850, 36.0850),
    "nakuru greenlands": (-0.2820, 36.0720),
    "nakuru breeze": (-0.2780, 36.0680),
    "nakuru vantage gardens": (-0.2830, 36.0730),
    "gilgil": (-0.5000, 36.3300),
    "naivasha": (-0.7224, 36.4388),
    "molo": (-0.2500, 35.7333),
    "njoro": (-0.3333, 35.9333),
    "ngata": (-0.3457, 35.6946),
    "mimwaita": (-0.3400, 35.7000),

    # New additions for better accuracy
    "kinungi": (-0.3700, 36.1400),
    "eveready": (-0.2900, 36.0900),
    "garden estate": (-0.3000, 36.0800),
    "ihindu": (-0.8200, 36.5000),
    "nyamathi": (-0.7500, 36.4500),
    "sobea": (-0.3400, 35.7000),

    # Common areas from new scrapers (Kenya Property Centre, Property24, PigiaMe)
    "nakuru east": (-0.2875, 36.0707),
    "nakuru town": (-0.2803, 36.0712),
    "naivasha east": (-0.7300, 36.4500),
    "kinangop": (-0.7000, 36.4000),
    "lanet": (-0.2800, 36.0600),
    "milimani": (-0.2900, 36.0750),
    "nakuru west": (-0.2750, 36.0500),
    "kaptembwo": (-0.3100, 36.0400),
    "bondeni": (-0.2900, 36.0900),
    "rhoda": (-0.3000, 36.0700),
    "lakeview": (-0.3200, 36.0700),
}

# Generic words that should always fallback to Nakuru centre
GENERIC_WORDS = {
    "land", "plot", "prime", "residential", "farm", "garden",
    "half", "acre", "plots", "delight", "hamptons", "havanna", "springfield",
    "for sale", "property", "development", "commercial", "agricultural"
}

_cache = {}

NAKURU_CENTRE = (-0.2802724, 36.0712048)

# Tighter bounding box for Nakuru County (excludes Nairobi)
NAKURU_BBOX = {
    "min_lat": -1.0,   # Nairobi is ~-1.3, so exclude it
    "max_lat": 0.0,
    "min_lon": 35.0,
    "max_lon": 36.8,   # Nairobi is ~36.8, so cap slightly above
}

def get_coords(location_text):
    if not location_text:
        return None, None

    location_text = location_text.strip()
    lower = location_text.lower()

    # 0. If the location is a generic word, return Nakuru centre immediately
    if lower in GENERIC_WORDS:
        print(f"  📌 Generic word '{lower}' → Nakuru centre")
        _cache[lower] = NAKURU_CENTRE
        return NAKURU_CENTRE

    # 1. Manual mapping – substring match (case-insensitive)
    for estate, coords in ESTATE_COORDS.items():
        if estate in lower:
            print(f"  📌 Manual mapping: {estate} → {coords}")
            _cache[lower] = coords
            return coords

    # 2. Cache
    if lower in _cache:
        print(f"  🔄 Cache hit for '{location_text}'")
        return _cache[lower]

    # 3. Build smart queries (always with Nakuru, Kenya)
    queries = build_queries(location_text)

    for query in queries:
        try:
            print(f"  🌍 Nominatim: {query[:60]}...")
            loc = geolocator_nominatim.geocode(query)
            if loc:
                lat, lon = loc.latitude, loc.longitude
                # 4. Validate coordinates are inside Nakuru bounding box
                if is_in_nakuru(lat, lon):
                    result = (lat, lon)
                    _cache[lower] = result
                    print(f"    ✅ Found: {lat}, {lon}")
                    return result
                else:
                    print(f"    ⚠️ Coordinates outside Nakuru ({lat}, {lon}) – discarding")
            time.sleep(0.5)
        except Exception as e:
            print(f"    ⚠️ Nominatim error: {e}")
            continue

    # 5. Final fallback: Nakuru centre
    print(f"  ❌ No valid coordinates found – using Nakuru centre")
    _cache[lower] = NAKURU_CENTRE
    return NAKURU_CENTRE

def build_queries(location_text):
    """Generate a list of query strings, always including Nakuru, Kenya."""
    queries = []
    # 1. as-is
    queries.append(location_text)
    # 2. with Nakuru, Kenya (if not already)
    if "nakuru" not in location_text.lower():
        queries.append(f"{location_text}, Nakuru, Kenya")
    elif "kenya" not in location_text.lower():
        queries.append(f"{location_text}, Kenya")
    # 3. first part before comma + Nakuru, Kenya
    parts = location_text.split(',')
    if len(parts) >= 2 and parts[0].strip():
        queries.append(f"{parts[0].strip()}, Nakuru, Kenya")
    # 4. final fallback
    queries.append("Nakuru, Kenya")
    # Remove duplicates
    seen = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique

def is_in_nakuru(lat, lon):
    """Check if coordinates fall within Nakuru County bounding box."""
    return (NAKURU_BBOX["min_lat"] <= lat <= NAKURU_BBOX["max_lat"] and
            NAKURU_BBOX["min_lon"] <= lon <= NAKURU_BBOX["max_lon"])