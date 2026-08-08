import requests
from bs4 import BeautifulSoup
import re
import time
import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

def extract_size(text):
    if not text:
        return None
    text = text.lower().strip()

    if '1/8' in text or 'eighth' in text:
        return 0.0506
    if '1/4' in text or 'quarter' in text:
        return 0.1012
    if '1/2' in text or 'half' in text:
        return 0.2023
    if '3/4' in text or 'three-quarter' in text:
        return 0.3035

    acre_match = re.search(r'(\d+\.?\d*)\s*acre', text)
    if acre_match:
        return float(acre_match.group(1)) * 0.4047

    ha_match = re.search(r'(\d+\.?\d*)\s*ha', text)
    if ha_match:
        return float(ha_match.group(1))

    sqm_match = re.search(r'(\d+\.?\d*)\s*sq\s*m', text)
    if sqm_match:
        return float(sqm_match.group(1)) / 10000

    dims = re.search(r'(\d+)\s*[x×]\s*(\d+)', text)
    if dims:
        w = float(dims.group(1))
        h = float(dims.group(2))
        sqm = w * h * 0.0929
        if 300 < sqm < 600:
            return 0.0506
        elif 600 < sqm < 1200:
            return 0.1012

    return None

def extract_price(text):
    if not text:
        return None
    cleaned = re.sub(r'[^0-9.]', '', text)
    try:
        return float(cleaned)
    except:
        return None

# ---- Site 1: BuyRentKenya ----
def scrape_buyrentkenya():
    print("Scraping BuyRentKenya...")
    url = "https://www.buyrentkenya.com/land-for-sale/nakuru"
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        listings = []
        cards = soup.select('.listing-card')
        if not cards:
            cards = soup.select('.card')
        for card in cards:
            price_el = card.select_one('div.flex.items-center.justify-center.text-xl.font-bold.leading-7.text-grey-900')
            if not price_el:
                price_el = card.select_one('[class*="price"]')
            if not price_el:
                continue
            title_el = card.select_one('h2.font-semibold.md\\:hidden')
            if not title_el:
                title_el = card.select_one('span.text-title.relative.top-\\[2px\\].hidden.text-lg.font-semibold.leading-6.md\\:inline')
            if not title_el:
                title_el = card.select_one('h2, h3, [class*="title"]')
            if not title_el:
                continue
            raw_text = title_el.text.strip()
            location_el = card.select_one('p.w-full.truncate.font-normal.capitalize')
            location = location_el.text.strip() if location_el else "Nakuru"
            size_el = card.select_one('span[data-cy="card-area_value"]')
            size_text = size_el.text.strip() if size_el else raw_text
            price = extract_price(price_el.text)
            size_ha = extract_size(size_text)
            if price and size_ha:
                listings.append({
                    'source': 'buyrentkenya',
                    'price': price,
                    'raw_text': raw_text,
                    'title': raw_text,
                    'location': location,
                    'size_ha': size_ha
                })
        print(f"BuyRentKenya found {len(listings)} valid listings")
        return listings
    except Exception as e:
        print(f"Error scraping BuyRentKenya: {e}")
        return []

# ---- Site 2: Jiji (FIXED) ----
def scrape_jiji():
    print("Scraping Jiji (using browser)...")
    listings = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # Try with longer timeout and different wait strategy
            page.goto("https://jiji.co.ke/nakuru/land-and-plots-for-sale", timeout=60000)
            # Wait for any content to load
            page.wait_for_timeout(5000)
            # Try different selectors
            try:
                page.wait_for_selector('a.b-list-advert-base, .advert-list-item, .qa-advert-title, .b-advert', timeout=10000)
            except:
                page.wait_for_timeout(3000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'html.parser')
        
        # Try multiple selectors
        items = soup.select('a.b-list-advert-base.qa-advert-list-item')
        if not items:
            items = soup.select('.advert-list-item')
        if not items:
            items = soup.select('[class*="advert"]')
        if not items:
            items = soup.select('a[href*="/nakuru/"]')
        
        print(f"Found {len(items)} items on Jiji")
        
        for item in items:
            price_el = item.select_one('div.qa-advert-price, .advert-price, [class*="price"]')
            title_el = item.select_one('div.qa-advert-title, .advert-title, [class*="title"]')
            location_el = item.select_one('span.b-list-advert__region__text, .advert-region, [class*="location"]')
            
            if not price_el or not title_el:
                continue
            
            price = extract_price(price_el.text)
            raw_text = title_el.text.strip()
            location = location_el.text.strip() if location_el else "Nakuru"
            size_ha = extract_size(raw_text)
            
            if price and size_ha:
                listings.append({
                    'source': 'jiji',
                    'price': price,
                    'raw_text': raw_text,
                    'title': raw_text,
                    'location': location,
                    'size_ha': size_ha
                })
        print(f"Jiji found {len(listings)} valid listings")
        return listings
    except Exception as e:
        print(f"Error scraping Jiji: {e}")
        return []

# ---- Site 3: PropertyPro ----
def scrape_propertypro():
    print("Scraping PropertyPro...")
    url = "https://www.propertypro.co.ke/property-for-sale/land/in/nakuru"
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        listings = []
        items = soup.select('.property-listing-grid')
        if not items:
            items = soup.select('.property-item')
        if not items:
            items = soup.select('[class*="property"]')
        for item in items:
            price_el = item.select_one('.pl-price h3, .property-price, [class*="price"]')
            title_el = item.select_one('.pl-title h3 a, .property-title a, [class*="title"]')
            location_el = item.select_one('.pl-title p, .property-location, [class*="location"]')
            if not price_el or not title_el:
                continue
            price = extract_price(price_el.text)
            raw_text = title_el.text.strip()
            location = location_el.text.strip() if location_el else "Nakuru"
            size_ha = extract_size(raw_text)
            if price and size_ha:
                listings.append({
                    'source': 'propertypro',
                    'price': price,
                    'raw_text': raw_text,
                    'title': raw_text,
                    'location': location,
                    'size_ha': size_ha
                })
        print(f"PropertyPro found {len(listings)} valid listings")
        return listings
    except Exception as e:
        print(f"Error scraping PropertyPro: {e}")
        return []

# ---- Site 4: UsernameProperties ----
def scrape_usernameproperties():
    print("Scraping UsernameProperties...")
    url = "https://usernameproperties.com/plots-land/land-and-plots-for-sale-nakuru-2"
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, timeout=15, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        listings = []
        
        items = soup.select('.hr-property-items')
        if not items:
            items = soup.select('[class*="property-items"]')
        
        print(f"Found {len(items)} property containers on UsernameProperties")
        
        for container in items:
            title_col = container.select_one('.col-md-6._pty_list_2')
            if not title_col:
                title_col = container.select_one('.hr-property-info.hr_pty_info')
            if not title_col:
                continue
            
            title_el = title_col.select_one('.hr-property-hero h2 a')
            if not title_el:
                title_el = title_col.select_one('.hr-property-hero a')
            if not title_el:
                title_el = title_col.select_one('h2 a')
            
            price_col = container.select_one('.col-md-6.actual-cost._pty_cst_1')
            if not price_col:
                price_col = container.select_one('.hr-property-cost .col-md-6')
            if not price_col:
                price_col = container.select_one('.actual-cost')
            
            price_el = None
            if price_col:
                price_el = price_col.select_one('.property-price_ribon')
                if not price_el:
                    price_el = price_col.select_one('[class*="price"]')
            
            if not title_el or not price_el:
                continue
            
            price = extract_price(price_el.text)
            raw_text = title_el.text.strip()
            
            location = "Nakuru"
            desc_el = title_col.select_one('.hr-property-hero p')
            size_ha = None
            if desc_el:
                desc_text = desc_el.text.strip()
                if 'Nakuru' in desc_text:
                    location = "Nakuru"
                size_ha = extract_size(desc_text)
            
            if not size_ha:
                size_ha = extract_size(raw_text)
            
            if not size_ha and price_col:
                size_ha = extract_size(price_col.text)
            
            if price and size_ha:
                listings.append({
                    'source': 'usernameproperties',
                    'price': price,
                    'raw_text': raw_text,
                    'title': raw_text,
                    'location': location,
                    'size_ha': size_ha
                })
                print(f"  ✓ {raw_text[:40]}... - KSh {price} - {size_ha}ha")
        
        print(f"UsernameProperties found {len(listings)} valid listings")
        return listings
    except Exception as e:
        print(f"Error scraping UsernameProperties: {e}")
        return []

# ---- Site 5: AdvancedValuers (FIXED) ----
def scrape_advancedvaluers():
    print("Scraping AdvancedValuers (using browser)...")
    listings = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # Longer timeout and wait for network idle
            page.goto("https://advancedvaluers.co.ke/properties/land/nakuru/", timeout=90000, wait_until="networkidle")
            # Wait for content
            page.wait_for_timeout(5000)
            try:
                page.wait_for_selector('.mh-grid, article, .mh-estate-vertical', timeout=15000)
            except:
                pass
            html = page.content()
            browser.close()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        items = soup.select('.mh-grid__1of2')
        if not items:
            items = soup.select('.mh-estate-vertical')
        if not items:
            items = soup.select('.mh-grid article')
        if not items:
            items = soup.select('article[class*="estate"]')
        
        print(f"Found {len(items)} property cards on AdvancedValuers")
        
        for item in items:
            title_el = item.select_one('.mh-estate-vertical__heading a')
            if not title_el:
                title_el = item.select_one('h3 a')
            if not title_el:
                title_el = item.select_one('.entry-title a')
            
            price_el = item.select_one('.mh-estate-vertical__primary')
            if not price_el:
                price_el = item.select_one('.mh-estate__details__price')
            if not price_el:
                price_el = item.select_one('[class*="price"]')
            
            if not title_el or not price_el:
                continue
            
            price = extract_price(price_el.text)
            raw_text = title_el.text.strip()
            
            size_ha = None
            attr_items = item.select('.mh-estate__list__element')
            for attr in attr_items:
                strong = attr.select_one('strong')
                if strong and 'Property size' in strong.text:
                    size_text = attr.text.replace('Property size:', '').strip()
                    size_ha = extract_size(size_text)
                    break
            
            if not size_ha:
                size_ha = extract_size(raw_text)
            
            location = "Nakuru"
            
            if price and size_ha:
                listings.append({
                    'source': 'advancedvaluers',
                    'price': price,
                    'raw_text': raw_text,
                    'title': raw_text,
                    'location': location,
                    'size_ha': size_ha
                })
                print(f"  ✓ {raw_text[:40]}... - KSh {price} - {size_ha}ha")
        
        print(f"AdvancedValuers found {len(listings)} valid listings")
        return listings
    except Exception as e:
        print(f"Error scraping AdvancedValuers: {e}")
        return []

# ---- Site 6: AMGRealtors ----
def scrape_amgrealtors():
    print("Scraping AMGRealtors (using browser)...")
    listings = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://amgrealtors.com/locations/properties-for-sale-in-nakuru", timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(3000)
            try:
                page.wait_for_selector('.grid .flex.flex-col.h-full, .max-w-md, .price-section', timeout=15000)
            except:
                pass
            html = page.content()
            browser.close()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        items = soup.select('.grid .flex.flex-col.h-full')
        if not items:
            items = soup.select('.max-w-md .h-full')
        if not items:
            items = soup.select('.max-w-md')
        if not items:
            items = soup.select('[class*="property-card"]')
        
        print(f"Found {len(items)} property cards on AMGRealtors")
        
        for item in items:
            title_el = item.select_one('h3.font-ubuntu-bold.text-xl')
            if not title_el:
                title_el = item.select_one('h3')
            if not title_el:
                title_el = item.select_one('[class*="title"]')
            
            if not title_el:
                continue
            
            raw_text = title_el.text.strip()
            
            location_el = item.select_one('.text-gray-400 .font-bold.truncate, .text-gray-400 span')
            location = "Nakuru"
            if location_el:
                location = location_el.text.strip()
            
            size_ha = None
            price = None
            
            price_section = item.select_one('.price-section table tbody')
            if price_section:
                rows = price_section.select('tr')
                for row in rows:
                    cells = row.select('td')
                    if len(cells) >= 3:
                        size_text = cells[0].text.strip()
                        cash_price_text = cells[1].text.strip()
                        
                        if not size_ha:
                            size_ha = extract_size(size_text)
                        if not price:
                            price = extract_price(cash_price_text)
            
            if not price:
                price_el = item.select_one('.price-section .font-montserrat-medium, [class*="price"]')
                if price_el:
                    price = extract_price(price_el.text)
            
            if not size_ha:
                size_ha = extract_size(raw_text)
            
            if price and size_ha:
                listings.append({
                    'source': 'amgrealtors',
                    'price': price,
                    'raw_text': raw_text,
                    'title': raw_text,
                    'location': location,
                    'size_ha': size_ha
                })
                print(f"  ✓ {raw_text[:40]}... - KSh {price} - {size_ha}ha")
        
        print(f"AMGRealtors found {len(listings)} valid listings")
        return listings
    except Exception as e:
        print(f"Error scraping AMGRealtors: {e}")
        return []

# ---- MASTER FUNCTION ----
def run_all_scrapers():
    print("=" * 40)
    print("Starting Nakuru Land Scraper...")
    print("=" * 40)

    all_data = []
    all_data.extend(scrape_buyrentkenya())
    time.sleep(2)
    all_data.extend(scrape_jiji())
    time.sleep(2)
    all_data.extend(scrape_propertypro())
    time.sleep(2)
    all_data.extend(scrape_usernameproperties())
    time.sleep(2)
    all_data.extend(scrape_advancedvaluers())
    time.sleep(2)
    all_data.extend(scrape_amgrealtors())

    print(f"Total raw listings scraped: {len(all_data)}")
    return all_data

# ---- INSERT INTO DATABASE ----
def insert_listings(data, supabase_url, supabase_key):
    """Insert listings into Supabase"""
    if not data:
        print("No data to insert")
        return
    
    try:
        from supabase import create_client, Client
        supabase: Client = create_client(supabase_url, supabase_key)
        
        inserted = 0
        skipped = 0
        
        for listing in data:
            existing = supabase.table('listings').select('id').eq('source', listing['source']).eq('price', listing['price']).eq('size_ha', listing['size_ha']).execute()
            
            if not existing.data:
                data = {
                    'source': listing['source'],
                    'price': listing['price'],
                    'size_ha': listing['size_ha'],
                    'title': listing['title'],
                    'raw_text': listing['raw_text'],
                    'location': listing['location'],
                    'latitude': None,
                    'longitude': None,
                }
                supabase.table('listings').insert(data).execute()
                inserted += 1
                print(f"  ✅ Inserted: {listing['title'][:40]}... - KSh {listing['price']} - {listing['size_ha']}ha")
            else:
                skipped += 1
        
        print(f"\n📊 Summary: {inserted} inserted, {skipped} skipped")
    except Exception as e:
        print(f"Error saving to database: {e}")

# ---- MAIN ----
if __name__ == "__main__":
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL or SUPABASE_KEY not found in .env file!")
    else:
        print("🔗 Found Supabase credentials. Running scrapers...")
        data = run_all_scrapers()

        if data:
            insert_listings(data, supabase_url, supabase_key)
            print(f"✅ Done! Processed {len(data)} listings.")
        else:
            print("⚠️ No data scraped.")