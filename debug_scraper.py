
import logging
from src.scraper import scrape_site
import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_scraper():
    config = {
        'app': {'max_article_age_days': 5, 'min_content_length': 10},
        'blocklist': {'titles': [], 'urls': []}
    }
    
    # Svensk Scenkonst
    # Create a dummy config for context
    config = {
        'app': {
            'max_article_age_days': 30, # Generous for testing
            'min_content_length': 10
        },
        'blocklist': {'titles': [], 'urls': []}
    }

    sites = [
        {
            'name': 'Svensk Scenkonst',
            'url': 'https://www.svenskscenkonst.se/aktuellt/nyheter/',
            'selector': 'a' # Testing generic selector
        },
        {
            'name': 'PTK Nyheter',
            'url': 'https://www.ptk.se/nyheter-och-press/nyheter/',
            'selector': 'a'
        },
        {
            'name': 'Arbetsgivaralliansen',
            'url': 'https://www.arbetsgivaralliansen.se/nyheter/',
            'selector': 'a'
        }
    ]
    
    for site in sites:
        print(f"\n--- Testing Scraper logic for {site['name']} ---")
        try:
            articles = scrape_site(site, config)
            print(f"✅ Collected {len(articles)} articles!")
            for a in articles[:3]:
                print(f" - [{a.published_date.date()}] {a.title} ({a.url})")
                
            if len(articles) == 0:
                print("❌ Still 0 articles. Check debug logs above.")
        except Exception as e:
            print(f"Error scraping {site['name']}: {e}")

if __name__ == "__main__":
    debug_scraper()
