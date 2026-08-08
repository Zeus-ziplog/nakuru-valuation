import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def debug_usernameproperties():
    print("=" * 50)
    print("Debugging UsernameProperties...")
    url = "https://usernameproperties.com/plots-land/land-and-plots-for-sale-nakuru-2"
    response = requests.get(url, timeout=15, verify=False)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    print("\n--- Page Title ---")
    print(soup.title.string if soup.title else "No title")
    
    selectors = [
        '.usr-others-wrap',
        '.col-md-3',
        '.owl-item .item',
        '.property-item',
        '.idx-property-items',
        '.listing-item',
        '.card',
        '.property'
    ]
    
    print("\n--- Testing Selectors ---")
    for selector in selectors:
        items = soup.select(selector)
        print(f"  {selector}: {len(items)} items")
    
    print("\n--- Price Elements ---")
    price_selectors = ['.property-price_ribon', '.pl-price h3', '.price', '.usr-others-offer h4', '[class*="price"]']
    for sel in price_selectors:
        els = soup.select(sel)
        if els:
            print(f"  {sel}: {len(els)} found - first: {els[0].text[:50]}")
    
    print("\n--- Title Elements ---")
    title_selectors = ['.others-item-title a', 'h3 a', '.idx-property-title h3 a', '.property-title a']
    for sel in title_selectors:
        els = soup.select(sel)
        if els:
            print(f"  {sel}: {len(els)} found - first: {els[0].text[:50]}")
    
    print("\n--- Looking for property cards manually ---")
    for div in soup.find_all('div', class_=True):
        classes = ' '.join(div.get('class', []))
        if 'property' in classes.lower() or 'listing' in classes.lower() or 'item' in classes.lower():
            print(f"  Found div with classes: {classes}")
            title = div.find('a', class_=lambda x: x and ('title' in x.lower() if x else False))
            price = div.find(class_=lambda x: x and ('price' in x.lower() if x else False))
            if title and price:
                print(f"    -> Has title: {title.text[:30]}... and price: {price.text[:30]}")

def debug_advancedvaluers():
    print("\n" + "=" * 50)
    print("Debugging AdvancedValuers...")
    url = "https://advancedvaluers.co.ke/properties/land/nakuru/"
    response = requests.get(url, timeout=15)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    print("\n--- Page Title ---")
    print(soup.title.string if soup.title else "No title")
    
    selectors = [
        'article.mh-estate-vertical',
        '.mh-grid__1of2 article',
        '.mh-grid__1of3',
        '.property-item',
        '.mh-estate-vertical',
        '.mh-grid',
        '[class*="estate"]',
        '[class*="property"]'
    ]
    
    print("\n--- Testing Selectors ---")
    for selector in selectors:
        items = soup.select(selector)
        print(f"  {selector}: {len(items)} items")
    
    print("\n--- Looking for specific elements ---")
    titles = soup.select('.mh-estate-vertical__heading a, h3 a')
    print(f"  Titles found: {len(titles)}")
    if titles:
        print(f"    First: {titles[0].text[:50]}")
    
    prices = soup.select('.mh-estate-vertical__primary, .property-price, [class*="price"]')
    print(f"  Prices found: {len(prices)}")
    if prices:
        print(f"    First: {prices[0].text[:50]}")
    
    print("\n--- First 2000 chars of body ---")
    body = soup.find('body')
    if body:
        print(str(body)[:2000])

if __name__ == "__main__":
    debug_usernameproperties()
    debug_advancedvaluers()
