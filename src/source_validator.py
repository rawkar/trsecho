import requests
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def validate_source(url: str) -> bool:
    """
    Validate if a source URL is reachable.
    Returns True if reachable, False otherwise.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.head(url, headers=headers, timeout=15, allow_redirects=True)
        
        # Some servers don't support HEAD, try GET
        if response.status_code == 405 or response.status_code == 403:
            response = requests.get(url, headers=headers, timeout=15, stream=True)
            
        return response.status_code < 400
    except Exception as e:
        logger.warning(f"Validation failed for {url}: {e}")
        return False

def check_sources_health(config):
    """
    Check health of all configured sources and return a report.
    """
    report = {
        'rss': {},
        'scrape': {}
    }
    
    # Check RSS
    for feed in config.get('sources', {}).get('rss', []):
        url = feed.get('url')
        name = feed.get('name')
        if url:
            is_healthy = validate_source(url)
            report['rss'][name] = {'url': url, 'healthy': is_healthy}
            if not is_healthy:
                logger.warning(f"RSS Source unhealthy: {name} ({url})")

    # Check Scrape
    for site in config.get('sources', {}).get('scrape', []):
        url = site.get('url')
        name = site.get('name')
        if url:
            is_healthy = validate_source(url)
            report['scrape'][name] = {'url': url, 'healthy': is_healthy}
            if not is_healthy:
                logger.warning(f"Scrape Source unhealthy: {name} ({url})")
                
    return report
