import requests
import json
import time
from geocoder import get_coords

def insert_listings(data_list, supabase_url, supabase_key):
    """
    Inserts or updates listings into Supabase.
    - Skips if a record with same source, price, size_ha already exists and has location_edited = true.
    - Otherwise, geocodes the location and inserts/updates with latitude/longitude.
    - Retries on connection errors.
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
    updated_count = 0
    skipped_edited = 0
    total_attempted = 0

    print(f"\n📊 Attempting to process {len(data_list)} listings...")
    print("-" * 50)

    for item in data_list:
        total_attempted += 1

        if not item.get('price') or not item.get('size_ha') or not item.get('location'):
            print(f"⏭️ Skipping {total_attempted}: Missing required fields")
            continue

        location = item['location']
        print(f"\n📍 {total_attempted}/{len(data_list)}: {location}")

        # ---- Check for existing record ----
        record_id = None
        query_url = f"{supabase_url}/rest/v1/listings?source=eq.{item['source']}&price=eq.{item['price']}&size_ha=eq.{item['size_ha']}&select=id,location_edited"
        try:
            resp = requests.get(query_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                existing = resp.json()
                if existing:
                    if existing[0].get('location_edited', False):
                        print(f"  ⏭️ Skipping – manually edited (location_edited=true)")
                        skipped_edited += 1
                        continue
                    else:
                        record_id = existing[0]['id']
        except Exception as e:
            print(f"  ⚠️ Error checking existing record: {e}")

        # ---- Geocode ----
        time.sleep(1.5)  # respect rate limits
        lat, lon = get_coords(location)

        if not lat or not lon:
            print(f"  ❌ Could not geocode: {location}")
            continue

        # Prepare payload
        record_data = {
            "source": item['source'],
            "price": float(item['price']),
            "size_ha": float(item['size_ha']),
            "latitude": lat,
            "longitude": lon,
            "geom": f"POINT({lon} {lat})",
            "title": item.get('title'),
            "raw_text": item.get('raw_text'),
            "location": location
        }

        # ---- Insert or Update with retry ----
        max_retries = 3
        success = False
        for attempt in range(max_retries):
            try:
                if record_id:
                    url = f"{supabase_url}/rest/v1/listings?id=eq.{record_id}"
                    response = requests.patch(url, headers=headers, json=record_data, timeout=30)
                    if response.status_code in [200, 201, 204]:
                        updated_count += 1
                        print(f"  ✅ Updated successfully (ID: {record_id})")
                        success = True
                        break
                    else:
                        print(f"  ❌ Update failed (attempt {attempt+1}): {response.status_code} - {response.text[:100]}")
                else:
                    url = f"{supabase_url}/rest/v1/listings"
                    response = requests.post(url, headers=headers, json=record_data, timeout=30)
                    if response.status_code in [200, 201, 204]:
                        inserted_count += 1
                        print(f"  ✅ Inserted successfully!")
                        success = True
                        break
                    else:
                        print(f"  ❌ Insert failed (attempt {attempt+1}): {response.status_code} - {response.text[:100]}")
            except Exception as e:
                print(f"  ⚠️ Error (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1, 2, 4 seconds
                    print(f"  Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  ❌ Failed after {max_retries} attempts")

    print("\n" + "=" * 50)
    print(f"📊 Summary:")
    print(f"   ✅ Inserted: {inserted_count}")
    print(f"   🔄 Updated: {updated_count}")
    print(f"   ⏭️ Skipped (manually edited): {skipped_edited}")
    print(f"   ❌ Failed / no coords: {total_attempted - inserted_count - updated_count - skipped_edited}")
    print("=" * 50)

    return inserted_count + updated_count