import requests
from bs4 import BeautifulSoup
import logging
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import parser as date_parser
from .models import Article

logger = logging.getLogger(__name__)

def extract_date(soup: BeautifulSoup, url: str) -> Optional[datetime]:
    """
    Attempt to extract publication date from HTML metadata.
    """
    # 1. JSON-LD (often most reliable)
    import json
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0]
            if 'datePublished' in data:
                return date_parser.parse(data['datePublished'])
        except:
            pass

    # 2. Meta tags
    meta_dates = [
        ('article:published_time', 'content'),
        ('date', 'content'),
        ('DC.date.issued', 'content'),
        ('pubdate', 'content'),
        ('og:published_time', 'content'),
        ('time', 'datetime') # <time datetime="...">
    ]
    
    for tag, attr in meta_dates:
        element = soup.find('meta', {tag: True}) or soup.find(tag)
        if element and element.has_attr(attr):
            try:
                return date_parser.parse(element[attr])
            except:
                continue
                
    # 3. URL regex (e.g. /2025/11/28/...)
    import re
    match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except:
            pass
            
    return None

def is_valid_deep_link(url: str) -> bool:
    """
    Check if a URL is valid for deep scraping.
    Strictly filters out non-http(s), mailto, tel, javascript, and internal anchors.
    """
    if not url:
        return False
        
    url_lower = url.lower()
    
    # Must start with http or https
    if not (url_lower.startswith('http://') or url_lower.startswith('https://')):
        return False
        
    # Explicitly block invalid schemes
    if any(url_lower.startswith(scheme) for scheme in ['mailto:', 'tel:', 'javascript:', 'data:', 'file:']):
        return False
        
    # Block anchors and query-only URLs (unless full URL)
    if url.startswith('#') or url.startswith('?'):
        return False
        
    return True

def is_relevant_path(url: str, source_url: str) -> bool:
    """
    Check if the URL path suggests it's a news article or relevant page.
    Prevents crawling into deep static sections like /medlem/, /om-oss/, etc.
    """
    from urllib.parse import urlparse
    
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    
    # 1. Block known irrelevant paths
    blocked_paths = [
        '/medlem', '/om-oss', '/om-forbundet', '/om-scen-film', '/kontakt', '/integritet', 
        '/cookies', '/tillganglighet', '/logga-in', '/mina-sidor', 
        '/faktabanken', '/upphovsratt', '/yrkesavdelningar', '/kurser',
        '/kalender', '/pressrum', '/press', '/media', '/kollektivavtal',
        '/medlemsformaner', '/stipendier', '/sok-stipendium', '/om-oss'
    ]
    
    if any(path.startswith(bp) for bp in blocked_paths):
        return False
        
    # 2. Prefer paths that look like news
    # (This is a heuristic, we don't strictly enforce it yet to avoid missing things, 
    # but we could use it to prioritize)
    
    return True

def scrape_web(config) -> List[Article]:
    """Scrape articles from configured websites with strict filtering and optimization."""
    articles = []
    sites = config.get('sources', {}).get('scrape', [])
    
    if not sites:
        logger.warning("No scrape sources configured.")
        return []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    max_age_days = config.get('app', {}).get('max_article_age_days', 2)
    min_content_length = config.get('app', {}).get('min_content_length', 300)
    cutoff_date = datetime.now().astimezone() - timedelta(days=max_age_days)

    for site_config in sites:
        url = site_config.get('url')
        source_name = site_config.get('name', 'Unknown')
        selector = site_config.get('selector', 'a')
        
        if not url:
            continue
            
        logger.info(f"Scraping website: {source_name} ({url})")
        
        # Circuit breaker for timeouts
        consecutive_timeouts = 0
        MAX_TIMEOUTS = 3
        
        try:
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
            session.mount('http://', HTTPAdapter(max_retries=retries))
            session.mount('https://', HTTPAdapter(max_retries=retries))


            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            elements = soup.select(selector)
            
            count = 0
            for element in elements:
                if count >= 5: 
                    break
                
                if consecutive_timeouts >= MAX_TIMEOUTS:
                    logger.warning(f"Skipping remaining links for {source_name} due to too many timeouts.")
                    break

                if element.name == 'a':
                    link_tag = element
                else:
                    link_tag = element.find('a')
                
                if not link_tag:
                    continue
                    
                href = link_tag.get('href')
                if not href:
                    continue
                    
                # Normalize URL
                if href.startswith('/'):
                    from urllib.parse import urljoin
                    full_url = urljoin(url, href)
                else:
                    full_url = href
                
                # 1. Strict URL Validation
                if not is_valid_deep_link(full_url):
                    continue
                    
                # 2. Path Relevance Check
                if not is_relevant_path(full_url, url):
                    # logger.debug(f"Skipping irrelevant path: {full_url}")
                    continue

                title = link_tag.get_text(strip=True)
                if not title or len(title) < 15:
                    continue
                
                # Check blocklist (basic pre-check)
                blocklist = config.get('blocklist', {})
                if any(term in title.lower() for term in blocklist.get('titles', [])):
                    continue
                    
                # --- DEEP SCRAPE FOR VALIDATION ---
                try:
                    article_resp = requests.get(full_url, headers=headers, timeout=5)
                    article_resp.raise_for_status() # Ensure we catch 404s etc
                    
                    # Reset timeout counter on success
                    consecutive_timeouts = 0
                    
                    article_soup = BeautifulSoup(article_resp.content, 'html.parser')
                    
                    # 1. Extract Date
                    pub_date = extract_date(article_soup, full_url)
                    
                    if not pub_date:
                        logger.debug(f"Skipping {title}: No date found.")
                        continue
                        
                    # Ensure timezone awareness
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.astimezone()
                        
                    if pub_date < cutoff_date:
                        logger.debug(f"Skipping {title}: Too old ({pub_date})")
                        continue
                        
                    # 2. Extract Content (Body Text)
                    # Remove scripts, styles, navs
                    for script in article_soup(["script", "style", "nav", "header", "footer"]):
                        script.decompose()
                        
                    paragraphs = article_soup.find_all('p')
                    body_text = " ".join([p.get_text(strip=True) for p in paragraphs])
                    
                    if len(body_text) < min_content_length:
                        logger.debug(f"Skipping {title}: Content too thin ({len(body_text)} chars)")
                        continue
                        
                    article = Article(
                        title=title,
                        url=full_url,
                        source=source_name,
                        published_date=pub_date,
                        summary=body_text[:200] + "...", # Use start of body as summary
                        content_type="article",
                        body_text=body_text
                    )
                    articles.append(article)
                    count += 1
                
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    consecutive_timeouts += 1
                    logger.warning(f"Timeout/Connection error deep scraping {full_url} ({consecutive_timeouts}/{MAX_TIMEOUTS})")
                    continue
                except requests.exceptions.RequestException as e:
                    # Log as info/debug to reduce noise for expected 404s or connection errors on bad links
                    logger.debug(f"Failed to deep scrape {full_url}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error deep scraping {full_url}: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"Failed to scrape {source_name}: {e}")
            
    logger.info(f"Collected {len(articles)} valid articles from web scraping.")
    return articles
