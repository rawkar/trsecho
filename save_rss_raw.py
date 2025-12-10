import requests

urls = {
    "publikt": "https://www.publikt.se/rss",
    "svensktnaringsliv": "https://www.svensktnaringsliv.se/rss/",
    "arbetsmiljoverket": "https://www.av.se/rss/nyheter/",
    "skr": "https://skr.se/skr/tjanster/rss.rss.html"
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

for name, url in urls.items():
    print(f"Fetching {name}...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        filename = f"debug_{name}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"Saved {filename} ({len(response.text)} chars)")
    except Exception as e:
        print(f"Failed {name}: {e}")
