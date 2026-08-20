from geopy.geocoders import Nominatim
import time
import os
import re
import json

# ---- Manual mapping – expanded with all known places ----
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

    # Towns / sub-counties
    "gilgil": (-0.5000, 36.3300),
    "naivasha": (-0.7224, 36.4388),
    "molo": (-0.2500, 35.7333),
    "njoro": (-0.3333, 35.9333),
    "ngata": (-0.3457, 35.6946),
    "mimwaita": (-0.3400, 35.7000),
    "kinungi": (-0.3700, 36.1400),
    "eveready": (-0.2900, 36.0900),
    "garden estate": (-0.3000, 36.0800),
    "ihindu": (-0.8200, 36.5000),
    "nyamathi": (-0.7500, 36.4500),
    "sobea": (-0.3400, 35.7000),
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

    # Common towns / sub-counties (from KMHFR & admin areas)
    "longonot": (-0.8600, 36.4600),
    "subukia": (-0.1800, 36.2300),
    "rongai": (-0.2300, 36.1300),
    "elementaita": (-0.5200, 36.2600),
    "keringet": (-0.3800, 35.5500),
    "bahati": (-0.1800, 36.1200),
    "dundori": (-0.2500, 36.1700),
    "kabazi": (-0.1500, 36.1500),
    "solai": (-0.1900, 36.1600),
    "elburgon": (-0.3500, 35.7000),
    "turi": (-0.3700, 35.6800),
    "kuresoi": (-0.2700, 35.6700),
    "olenguruone": (-0.3400, 35.5500),
    "kiamaina": (-0.2600, 36.1100),
    "barut": (-0.3100, 36.0500),
    "mwariki": (-0.2900, 36.0400),
    "free area": (-0.2800, 36.0500),
    "kaptembwa": (-0.3000, 36.0400),
    "mau narok": (-0.3300, 35.9300),
    "mai mahiu": (-0.8900, 36.4800),
    "sachangwan": (-0.2700, 35.7300),
    "mogotio": (-0.2800, 35.8000),
    "maiela": (-0.7800, 36.4700),
    "karagita": (-0.7400, 36.4500),
    "mirera": (-0.7200, 36.4400),
    "olkaria": (-0.7800, 36.5000),
    "hells gate": (-0.8000, 36.4800),
    "mbaruk": (-0.4800, 36.3000),
    "kikopey": (-0.4500, 36.2800),

    # ---- NEW: extra places from scraper log ----
    "mwiciringiri": (-0.2200, 36.2000),   # approximate (near Subukia)
    "moi south": (-0.7300, 36.4500),      # Naivasha area
    "kiborojo": (-0.1900, 36.2400),       # near Subukia
    "pramukh towers": (-0.2803, 36.0712), # Nakuru town
    "regus village market": (-0.2803, 36.0712), # Nakuru town
    "westlands nairobi": None,            # explicitly exclude (will be filtered out)
}

# ---- Generic words that fallback to Nakuru centre ----
GENERIC_WORDS = {
    "land", "plot", "prime", "residential", "farm", "garden",
    "half", "acre", "plots", "delight", "hamptons", "havanna", "springfield",
    "for sale", "property", "development", "commercial", "agricultural"
}

NAKURU_CENTRE = (-0.2802724, 36.0712048)

NAKURU_BBOX = {
    "min_lat": -1.0,
    "max_lat": 0.0,
    "min_lon": 35.0,
    "max_lon": 36.8,
}

_cache = {}
geolocator_nominatim = Nominatim(user_agent="nakuru_valuation", timeout=15)

# ---- Load ward centroids ----
ward_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'public', 'nakuru_wards.geojson')
WARD_CENTROIDS = {}
WARD_NAMES = []
if os.path.exists(ward_file):
    try:
        with open(ward_file, 'r') as f:
            data = json.load(f)
        for feature in data['features']:
            name = feature['properties'].get('NAME', '').lower()
            coords = feature['geometry']['coordinates']
            if feature['geometry']['type'] == 'MultiPolygon':
                all_polygons = []
                for poly in coords:
                    all_polygons.extend(poly[0])
            else:
                all_polygons = coords[0]
            lats = [p[1] for p in all_polygons]
            lons = [p[0] for p in all_polygons]
            centroid_lat = sum(lats) / len(lats)
            centroid_lon = sum(lons) / len(lons)
            WARD_CENTROIDS[name] = (centroid_lat, centroid_lon)
            WARD_NAMES.append(name)
        print(f"Loaded {len(WARD_CENTROIDS)} ward centroids.")
    except Exception as e:
        print(f"Could not load ward centroids: {e}")
else:
    print("Ward GeoJSON not found – ward fallback disabled.")

# ---- Load sub-county centroids ----
sub_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'public', 'nakuru_subcounties.geojson')
SUB_CENTROIDS = {}
SUB_NAMES = []
if os.path.exists(sub_file):
    try:
        with open(sub_file, 'r') as f:
            data = json.load(f)
        for feature in data['features']:
            name = feature['properties'].get('NAME', '').lower()
            coords = feature['geometry']['coordinates']
            if feature['geometry']['type'] == 'MultiPolygon':
                all_polygons = []
                for poly in coords:
                    all_polygons.extend(poly[0])
            else:
                all_polygons = coords[0]
            lats = [p[1] for p in all_polygons]
            lons = [p[0] for p in all_polygons]
            centroid_lat = sum(lats) / len(lats)
            centroid_lon = sum(lons) / len(lons)
            SUB_CENTROIDS[name] = (centroid_lat, centroid_lon)
            SUB_NAMES.append(name)
        print(f"Loaded {len(SUB_CENTROIDS)} sub-county centroids.")
    except Exception as e:
        print(f"Could not load sub-county centroids: {e}")
else:
    print("Sub-county GeoJSON not found – sub-county fallback disabled.")

def geocode_location(query):
    """
    Geocode with fallback chain:
    1. Manual mapping (ESTATE_COORDS) – substring match
    2. Cache
    3. Nominatim (with smart queries)
    4. Ward centroid (if ward name in query)
    5. Sub-county centroid (if sub-county name in query)
    6. Nakuru centre
    """
    if not query:
        return None, None

    query = query.strip()
    lower = query.lower()

    # 0. Check if the query contains a known non-Nakuru location (e.g., Westlands, Nairobi)
    for key in ESTATE_COORDS:
        if key in lower and ESTATE_COORDS[key] is None:
            print(f"  🚫 Excluding non-Nakuru location: '{query}'")
            return None, None

    # 1. Generic words → Nakuru centre
    if lower in GENERIC_WORDS:
        print(f"  📌 Generic word '{lower}' → Nakuru centre")
        _cache[lower] = NAKURU_CENTRE
        return NAKURU_CENTRE

    # 2. Manual mapping (substring match)
    for estate, coords in ESTATE_COORDS.items():
        if coords is not None and estate in lower:
            print(f"  📌 Manual mapping: {estate} → {coords}")
            _cache[lower] = coords
            return coords

    # 3. Cache
    if lower in _cache:
        print(f"  🔄 Cache hit for '{query}'")
        return _cache[lower]

    # 4. Nominatim
    queries = build_queries(query)
    for q in queries:
        try:
            print(f"  🌍 Nominatim: {q[:60]}...")
            loc = geolocator_nominatim.geocode(q)
            if loc:
                lat, lon = loc.latitude, loc.longitude
                if is_in_nakuru(lat, lon):
                    result = (lat, lon)
                    _cache[lower] = result
                    print(f"    ✅ Found: {lat}, {lon}")
                    return result
                else:
                    print(f"    ⚠️ Outside Nakuru ({lat}, {lon}) – discarding")
            time.sleep(0.5)
        except Exception as e:
            print(f"    ⚠️ Nominatim error: {e}")
            continue

    # 5. Ward centroid fallback
    for ward_name in WARD_NAMES:
        if ward_name in lower:
            lat, lng = WARD_CENTROIDS[ward_name]
            _cache[lower] = (lat, lng)
            print(f"  📌 Ward fallback: '{query}' → {ward_name} ({lat}, {lng})")
            return lat, lng

    # 6. Sub-county centroid fallback
    for sub_name in SUB_NAMES:
        if sub_name in lower:
            lat, lng = SUB_CENTROIDS[sub_name]
            _cache[lower] = (lat, lng)
            print(f"  📌 Sub-county fallback: '{query}' → {sub_name} ({lat}, {lng})")
            return lat, lng

    # 7. Ultimate fallback: Nakuru centre
    print(f"  ❌ No match – using Nakuru centre for: {query}")
    _cache[lower] = NAKURU_CENTRE
    return NAKURU_CENTRE

def build_queries(location_text):
    queries = []
    queries.append(location_text)
    if "nakuru" not in location_text.lower():
        queries.append(f"{location_text}, Nakuru, Kenya")
    elif "kenya" not in location_text.lower():
        queries.append(f"{location_text}, Kenya")
    parts = location_text.split(',')
    if len(parts) >= 2 and parts[0].strip():
        queries.append(f"{parts[0].strip()}, Nakuru, Kenya")
    queries.append("Nakuru, Kenya")
    seen = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique

def is_in_nakuru(lat, lon):
    return (NAKURU_BBOX["min_lat"] <= lat <= NAKURU_BBOX["max_lat"] and
            NAKURU_BBOX["min_lon"] <= lon <= NAKURU_BBOX["max_lon"])

# ---- Alias for backward compatibility ----
get_coords = geocode_location