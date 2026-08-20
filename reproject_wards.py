import geopandas as gpd

# Read the UTM GeoJSON
gdf = gpd.read_file('public/nakuru_wards.geojson')

# Reproject to WGS84 (EPSG:4326) – lat/lon
gdf_wgs84 = gdf.to_crs(epsg=4326)

# Save back to the same file (or a new one)
gdf_wgs84.to_file('public/nakuru_wards.geojson', driver='GeoJSON')

print("✅ Reprojected to WGS84 – now Leaflet can display it.")