import requests
import feedparser

def debug_feed(url):
    print(f"\n--- Debugging {url} ---")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        content = response.text
        print(f"Content Start: {content[:200]}")
        
        # Parse it
        feed = feedparser.parse(content)
        if feed.bozo:
            print(f"Feedparser Error: {feed.bozo_exception}")
        else:
            print("Feedparser: OK")

    except Exception as e:
        print(f"Request failed: {e}")

urls = [
    "https://www.publikt.se/rss",
    "https://www.svensktnaringsliv.se/rss/",
    "https://www.av.se/rss/nyheter/",
    "https://skr.se/skr/tjanster/rss.rss.html"
]

for url in urls:
    debug_feed(url)
