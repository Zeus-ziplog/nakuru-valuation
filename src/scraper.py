import requests
from bs4 import BeautifulSoup
import re
import time
import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from db_utils import insert_listings

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

def clean_location(raw_text):
    """
    Extract the core estate/area name from raw text.
    Removes price, size, filler words, phase suffixes, and roman numerals.
    """
    if not raw_text:
        return "Nakuru"

    clean = ' '.join(raw_text.split())
    clean = re.sub(r'(FOR|Sale|KSh|PID\s*:\s*\S+|\d+\.?\d*\s*(ha|acre|acres|plot|land|residential))', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'[|,;–-]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    clean = re.sub(r'\s*(Phase|Annex|Pahse|Phases?)\s*[IVXLCDM\d]+$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*[IVXLCDM]+\s*$', '', clean)

    words = clean.split()
    if len(words) >= 2:
        if words[0].lower() == 'nakuru' and len(words) >= 3:
            return ' '.join(words[:3]).title()
        elif words[0].lower() == 'nakuru':
            return ' '.join(words[:2]).title()
        meaningful = []
        for w in words:
            if w.isalpha() and len(w) > 2:
                meaningful.append(w)
            if len(meaningful) == 3:
                break
        if meaningful:
            return ' '.join(meaningful).title()

    for w in words:
        if w.isalpha() and len(w) > 2:
            return w.title()

    return clean[:60].strip()

def is_nakuru_location(text):
    """Check if the text mentions Nakuru or nearby towns, ignore Nairobi."""
    if not text:
        return False
    text = text.lower()
    # List of acceptable areas
    nakuru_keywords = [
        "nakuru", "naivasha", "gilgil", "molo", "njoro", "kinangop",
        "kaptembwo", "bondeni", "rhoda", "lakeview", "lanet", "milimani",
        "ngata", "mimwaita", "eveready", "kinungi", "garden estate",
        "nakuru east", "nakuru west", "nakuru town"
    ]
    # If any keyword is found, it's Nakuru
    for kw in nakuru_keywords:
        if kw in text:
            return True
    # Reject Nairobi, Westlands, etc.
    nairobi_keywords = ["nairobi", "westlands", "lavington", "peponi", "loresho", "kilimani", "kileleshwa", "parklands"]
    for kw in nairobi_keywords:
        if kw in text:
            return False
    # If no keyword, assume it might be Nakuru (fallback)
    return True

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
            if not is_nakuru_location(raw_text):
                continue
            location = clean_location(raw_text)
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

# ---- Site 2: Jiji (with fallback) ----
def scrape_jiji():
    print("Scraping Jiji (using browser)...")
    listings = []
    html = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://jiji.co.ke/nakuru/land-and-plots-for-sale", timeout=90000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            try:
                page.wait_for_selector('a.b-list-advert-base, .advert-list-item, .qa-advert-title', timeout=10000)
            except:
                pass
            html = page.content()
            browser.close()
    except Exception as e:
        print(f"Playwright failed: {e}, falling back to requests...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get("https://jiji.co.ke/nakuru/land-and-plots-for-sale", headers=headers, timeout=30)
            if response.status_code == 200:
                html = response.text
                print("Fallback succeeded.")
            else:
                print(f"Fallback failed with status {response.status_code}")
                return []
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            return []

    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
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
        if not price_el or not title_el:
            continue

        price = extract_price(price_el.text)
        raw_text = title_el.text.strip()
        if not is_nakuru_location(raw_text):
            continue
        location = clean_location(raw_text)
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
            if not price_el or not title_el:
                continue
            price = extract_price(price_el.text)
            raw_text = title_el.text.strip()
            if not is_nakuru_location(raw_text):
                continue
            location = clean_location(raw_text)
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
            if not is_nakuru_location(raw_text):
                continue
            location = clean_location(raw_text)

            size_ha = None
            desc_el = title_col.select_one('.hr-property-hero p')
            if desc_el:
                size_ha = extract_size(desc_el.text.strip())
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

# ---- Site 5: AdvancedValuers ----
def scrape_advancedvaluers():
    print("Scraping AdvancedValuers (using browser)...")
    listings = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://advancedvaluers.co.ke/properties/land/nakuru/", timeout=90000, wait_until="networkidle")
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
            if not is_nakuru_location(raw_text):
                continue
            location = clean_location(raw_text)

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
            if not is_nakuru_location(raw_text):
                continue
            location = clean_location(raw_text)

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

# ===========================
# NEW SITES – WITH PLAYWRIGHT
# ===========================

# ---- Site 7: PigiaMe ----
def scrape_pigiame():
    print("Scraping PigiaMe...")
    url = "https://www.pigiame.co.ke/land-for-sale/nakuru"
    try:
        response = requests.get(url, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        listings = []
        cards = soup.select('div.listing-card')
        for card in cards:
            link = card.select_one('a.listing-card__inner')
            if not link:
                continue

            title_el = card.select_one('.listing-card__header__title')
            if not title_el:
                continue
            raw_text = title_el.text.strip()
            if not is_nakuru_location(raw_text):
                continue

            price_el = card.select_one('.listing-card__price__value')
            if not price_el:
                continue
            price = extract_price(price_el.text)

            location_el = card.select_one('.listing-card__header__location')
            location = location_el.text.strip() if location_el else "Nakuru"

            size_ha = extract_size(raw_text)
            if not size_ha:
                continue

            location = clean_location(location) or clean_location(raw_text)

            if price and size_ha:
                listings.append({
                    'source': 'pigiame',
                    'price': price,
                    'raw_text': raw_text,
                    'title': raw_text,
                    'location': location,
                    'size_ha': size_ha,
                })
                print(f"  ✓ {raw_text[:40]}... - KSh {price} - {size_ha}ha")

        print(f"PigiaMe found {len(listings)} valid listings")
        return listings
    except Exception as e:
        print(f"Error scraping PigiaMe: {e}")
        return []

# ---- Site 8: Kenya Property Centre (NOW WITH PLAYWRIGHT) ----
def scrape_kenyapropertycentre():
    print("Scraping Kenya Property Centre (using browser)...")
    listings = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://www.kenyapropertycentre.com/properties/for-sale/nakuru/land", timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(5000)
            try:
                page.wait_for_selector('article.rounded-xl.bg-card.shadow-sm', timeout=15000)
            except:
                pass
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select('article.rounded-xl.bg-card.shadow-sm')
        for card in cards:
            title_tag = card.select_one('h3.mt-1\\.5.line-clamp-2.text-xl.font-semibold.text-foreground-strong')
            if not title_tag:
                continue
            raw_text = title_tag.get_text(strip=True)
            # Check if Nakuru-related
            if not is_nakuru_location(raw_text):
                continue

            price_tag = card.select_one('span.text-\\[1\\.375rem\\].font-bold.leading-tight')
            if not price_tag:
                continue
            price = extract_price(price_tag.get_text(strip=True))

            loc_tag = card.select_one('span.truncate')
            location = loc_tag.get_text(strip=True) if loc_tag else "Nakuru"

            size_ha = extract_size(raw_text)
            if not size_ha:
                desc_tag = card.select_one('p.mt-1.line-clamp-2.text-\\[0\\.8125rem\\].text-foreground-muted')
                if desc_tag:
                    size_ha = extract_size(desc_tag.get_text(strip=True))
            if not size_ha:
                continue

            location = clean_location(location) or clean_location(raw_text)

            if price and size_ha:
                listings.append({
                    'source': 'kenyapropertycentre',
                    'price': price,
                    'raw_text': raw_text,
                    'title': raw_text,
                    'location': location,
                    'size_ha': size_ha,
                })
                print(f"  ✓ {raw_text[:40]}... - KSh {price} - {size_ha}ha")

        print(f"Kenya Property Centre found {len(listings)} valid listings")
        return listings
    except Exception as e:
        print(f"Error scraping Kenya Property Centre: {e}")
        return []

# ---- Site 9: Property24 Kenya (NOW WITH PLAYWRIGHT & ROBUST SELECTORS) ----
def scrape_property24():
    print("Scraping Property24 Kenya (using browser)...")
    listings = []
    html = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page.goto("https://www.property24.co.ke/property-for-sale-in-nakuru-p96", timeout=60000, wait_until="load")
            page.wait_for_timeout(5000)
            try:
                page.wait_for_selector('div.p24_regularTile, div.p24_listingTile, div.js_listingTile', timeout=15000)
            except:
                print("⚠️ Timed out waiting for listing tiles – continuing anyway")
            html = page.content()
            browser.close()

        # DEBUG: Save HTML for inspection if needed
        # with open("property24_debug.html", "w", encoding="utf-8") as f:
        #     f.write(html)

        soup = BeautifulSoup(html, 'html.parser')
        # Try multiple selectors
        cards = soup.select('div.p24_regularTile, div.p24_listingTile, div.js_listingTile, div[data-listing-number], div.developmentTileContainer')
        if not cards:
            # Fallback: look for any div with 'listing' in class
            cards = soup.select('div[class*="listing"]')
        print(f"Found {len(cards)} potential cards on Property24")

        for card in cards:
            is_development = 'developmentTileContainer' in card.get('class', [])

            # Title – try multiple sources
            title_meta = card.select_one('meta[itemprop="name"]')
            if title_meta:
                raw_text = title_meta.get('content', '').strip()
            else:
                title_elem = card.select_one('.p24_title a, .p24_listingSummary .p24_bold, .p24_title')
                raw_text = title_elem.get_text(strip=True) if title_elem else None
            if not raw_text:
                continue

            # Filter out Nairobi
            if not is_nakuru_location(raw_text):
                continue

            # Price
            if is_development:
                price_elem = card.select_one('.p24_price')
                price_text = price_elem.get_text(strip=True) if price_elem else None
            else:
                price_elem = card.select_one('.p24_price span, .p24_price')
                price_text = price_elem.get_text(strip=True) if price_elem else None
            if not price_text:
                continue
            price = extract_price(price_text)

            # Location
            if is_development:
                loc_elem = card.select_one('.p24_address')
                location = loc_elem.get_text(strip=True) if loc_elem else "Nakuru"
            else:
                loc_elem = card.select_one('.p24_listingSummary .p24_bold, .p24_location, .p24_address')
                location = loc_elem.get_text(strip=True) if loc_elem else "Nakuru"

            # Size – try Erf/Floor size or raw_text
            size_ha = extract_size(raw_text)
            if not is_development:
                erf_elem = card.select_one('li.p24_size[title="Erf Size"] span, .p24_size[title="Erf Size"] span')
                if erf_elem:
                    size_ha = extract_size(erf_elem.get_text(strip=True))
                if not size_ha:
                    floor_elem = card.select_one('li.p24_size[title="Floor Size"] span, .p24_size[title="Floor Size"] span')
                    if floor_elem:
                        size_ha = extract_size(floor_elem.get_text(strip=True))
            if not size_ha:
                size_ha = extract_size(raw_text)

            if not size_ha:
                continue

            location = clean_location(location) or clean_location(raw_text)

            if price and size_ha:
                listings.append({
                    'source': 'property24',
                    'price': price,
                    'raw_text': raw_text,
                    'title': raw_text,
                    'location': location,
                    'size_ha': size_ha,
                })
                print(f"  ✓ {raw_text[:40]}... - KSh {price} - {size_ha}ha")

        print(f"Property24 found {len(listings)} valid listings")
        return listings
    except Exception as e:
        print(f"Error scraping Property24: {e}")
        return []

# ---- MASTER FUNCTION ----
def run_all_scrapers():
    print("=" * 40)
    print("Starting Nakuru Land Scraper...")
    print("=" * 40)

    all_data = []
    # Existing sites
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
    time.sleep(2)

    # New sites
    all_data.extend(scrape_pigiame())
    time.sleep(2)
    all_data.extend(scrape_kenyapropertycentre())
    time.sleep(2)
    all_data.extend(scrape_property24())

    print(f"Total raw listings scraped: {len(all_data)}")
    return all_data

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