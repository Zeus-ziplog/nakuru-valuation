import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_KEY in .env")
    exit(1)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

print("Fetching listings from Supabase...")
response = requests.get(
    f"{SUPABASE_URL}/rest/v1/listings?select=id,title,price,size_ha,location,latitude,longitude,source",
    headers=headers
)

if response.status_code != 200:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
    exit(1)

data = response.json()
print(f"✅ Fetched {len(data)} records")

geojson = {
    "type": "FeatureCollection",
    "features": []
}

for row in data:
    lat = row.get("latitude")
    lng = row.get("longitude")
    if lat and lng:
        try:
            lat = float(lat)
            lng = float(lng)
        except:
            continue
        geojson["features"].append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "properties": {
                "id": row.get("id"),
                "title": row.get("title"),
                "price": row.get("price"),
                "size_ha": row.get("size_ha"),
                "location": row.get("location"),
                "source": row.get("source")
            }
        })

with open("nakuru_plots.geojson", "w") as f:
    json.dump(geojson, f, indent=2)

print(f"✅ Saved nakuru_plots.geojson with {len(geojson['features'])} features")
