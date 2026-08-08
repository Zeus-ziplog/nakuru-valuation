# Nakuru Land Valuation System

## How it works
1. The Python scraper runs automatically every Sunday at 2 AM via GitHub Actions.
2. It scrapes 6 real estate websites for Nakuru land listings.
3. It saves the data (price, size, location) to Supabase cloud database.
4. QGIS connects directly to Supabase to display the heatmap.
5. The mobile web page also reads from Supabase.

## For the CEO
- Open `Nakuru_Valuation.qgz` in QGIS.
- Right-click the layer and click "Refresh" to get the latest data.

## Setup for Developer
1. Create a Supabase project and enable PostGIS.
2. Create the `listings` table (see SQL in notes).
3. Add `SUPABASE_DB_URL` secret to GitHub repository.
4. Push code to GitHub.
