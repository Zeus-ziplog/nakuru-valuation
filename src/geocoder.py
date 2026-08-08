from geopy.geocoders import Nominatim
import time
import re

geolocator = Nominatim(user_agent="nakuru_valuation", timeout=15)

def get_coords(location_text):
    """
    Convert a text location (e.g., 'Milimani, Nakuru') to Lat/Long.
    Returns (latitude, longitude) or (None, None) if not found.
    """
    if not location_text:
        return None, None
    
    try:
        location_text = location_text.strip()
        
        # If the text is too long, try to extract a shorter version
        if len(location_text) > 100:
            parts = location_text.split(',')
            if len(parts) >= 2:
                location_text = f"{parts[0].strip()}, {parts[-1].strip()}"
            else:
                location_text = parts[0].strip() if parts else location_text
        
        # Add "Nakuru, Kenya" if not already in the text
        if "Nakuru" not in location_text:
            location_text = f"{location_text}, Nakuru, Kenya"
        elif "Kenya" not in location_text:
            location_text = f"{location_text}, Kenya"
        
        print(f"  Geocoding: {location_text[:80]}...")
        
        loc = geolocator.geocode(location_text)
        
        if loc:
            print(f"  ✅ Found: {loc.latitude}, {loc.longitude}")
            return loc.latitude, loc.longitude
        else:
            # Try a simpler query
            if "Nakuru" in location_text:
                simple_query = location_text.split(',')[0].strip()
                if simple_query:
                    print(f"  Retrying with: {simple_query}")
                    loc = geolocator.geocode(f"{simple_query}, Nakuru, Kenya")
                    if loc:
                        print(f"  ✅ Found: {loc.latitude}, {loc.longitude}")
                        return loc.latitude, loc.longitude
            
            print(f"  ❌ No coordinates found for: {location_text[:50]}")
            return None, None
            
    except Exception as e:
        print(f"  ❌ Geocoding error: {e}")
        return None, None