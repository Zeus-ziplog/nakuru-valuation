import requests
import json
import time
from geocoder import get_coords

def insert_listings(data_list, supabase_url, supabase_key):
    """
    Inserts listings into Supabase using the REST API.
    """
    if not data_list:
        print("No data to insert.")
        return 0

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    inserted_count = 0
    total_attempted = 0
    
    print(f"\n📊 Attempting to insert {len(data_list)} listings...")
    print("-" * 50)

    for item in data_list:
        total_attempted += 1
        
        if not item.get('price') or not item.get('size_ha') or not item.get('location'):
            print(f"⏭️ Skipping {total_attempted}: Missing required fields")
            continue

        location = item['location']
        print(f"\n📍 {total_attempted}/{len(data_list)}: {location}")
        
        # Add a small delay to avoid rate limiting (1 second between requests)
        time.sleep(1.5)
        
        lat, lon = get_coords(location)
        
        if lat and lon:
            record = {
                "source": item['source'],
                "price": float(item['price']),
                "size_ha": float(item['size_ha']),
                "latitude": lat,
                "longitude": lon,
                "geom": f"POINT({lon} {lat})"
            }

            url = f"{supabase_url}/rest/v1/listings"
            try:
                response = requests.post(url, headers=headers, json=record, timeout=30)
                if response.status_code in [200, 201, 204]:
                    inserted_count += 1
                    print(f"  ✅ Inserted successfully!")
                else:
                    print(f"  ❌ Failed: {response.status_code} - {response.text[:100]}")
            except Exception as e:
                print(f"  ❌ Error: {e}")
        else:
            print(f"  ❌ Could not geocode: {location}")

    print("\n" + "=" * 50)
    print(f"📊 Summary: {inserted_count}/{total_attempted} listings inserted successfully.")
    print("=" * 50)
    
    return inserted_count