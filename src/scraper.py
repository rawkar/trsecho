import requests
from bs4 import BeautifulSoup
import logging
import re
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import parser as date_parser
from .models import Article
import concurrent.futures

logger = logging.getLogger(__name__)

SKIP_TITLES = [
    'logga', 'logo', 'meny', 'menu', 'kalender', 'evenemang',
    'kurser', 'aktiviteter', 'om oss', 'kontakt', 'kontakta oss',
    'prenumerera', 'nyhetsbrev', 'cookie', 'integritetspolicy',
    'press', 'pressrum', 'pressbild', 'ladda ner', 'download',
    'sök', 'search', 'facebook', 'twitter', 'linkedin', 'instagram'
]


def parse_swedish_date(text: str) -> Optional[datetime]:
    """Parse common Swedish date formats e.g., '28 november 2024'"""
    months = {
        'januari': 1, 'februari': 2, 'mars': 3, 'april': 4, 'maj': 5, 'juni': 6,
        'juli': 7, 'augusti': 8, 'september': 9, 'oktober': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'dec': 12
    }
    
    text = text.lower().strip()
    # Regex for "D Month YYYY"
    # match 1 or 2 digits, space, word, space, 4 digits
    match = re.search(r'(\d{1,2})\s+([a-zåäö]+)\s+(\d{4})', text)
    if match:
        day = int(match.group(1))
        month_str = match.group(2)
        year = int(match.group(3))
        
        if month_str in months:
            try:
                return datetime(year, months[month_str], day)
            except:
                pass
    return None

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
            
    # 4. Text search in common classes (Deep Scrape fallback)
    # Look for elements with class/id containing 'date', 'time', 'publicerad'
    date_candidates = soup.find_all(class_=re.compile(r'date|time|publish|meta', re.I))
    for candidate in date_candidates[:5]: # Check first 5 matches
        text = candidate.get_text(strip=True)
        # Try finding YYYY-MM-DD
        match_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
        if match_iso:
            try:
                return datetime(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3)))
            except:
                pass
        
        # Try Swedish format
        sw_date = parse_swedish_date(text)
        if sw_date:
            return sw_date

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

def is_valid_article_title(title: str, description: str = None) -> bool:
    """Check if title looks like a real article"""
    if not title or len(title) < 20: # Increased min length
        return False
        
    title_lower = title.lower()
    if any(skip in title_lower for skip in SKIP_TITLES):
        return False
        
    return True

def scrape_site(site_config, config) -> List[Article]:
    """Scrape a single site."""
    articles = []
    url = site_config.get('url')
    source_name = site_config.get('name', 'Unknown')
    selector = site_config.get('selector', 'a')
    
    if not url:
        return []
        
    logger.info(f"Scraping website: {source_name} ({url})")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    max_age_days = config.get('app', {}).get('max_article_age_days', 2)
    min_content_length = config.get('app', {}).get('min_content_length', 300)
    cutoff_date = datetime.now().astimezone() - timedelta(days=max_age_days)
    
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
        
        logger.debug(f"{source_name}: Found {len(elements)} elements with selector '{selector}'")
        if len(elements) == 0:
             # Preview HTML to see why selector failed
             clean_html = str(soup)[:500].replace('\n', ' ').replace('\r', '')
             logger.debug(f"{source_name}: HTML Preview: {clean_html}...")
        
        count = 0
        
        # Determine strictness based on site
        # Some sites need strictly news selectors, others general 'a'
        
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
                continue

            title = link_tag.get_text(strip=True)
            if not is_valid_article_title(title):
                continue
            
            # Check blocklist (basic pre-check)
            blocklist = config.get('blocklist', {})
            if any(term in title.lower() for term in blocklist.get('titles', [])):
                continue
                
            # --- DEEP SCRAPE FOR VALIDATION ---
            try:
                article_resp = requests.get(full_url, headers=headers, timeout=10) # Reduced timeout
                article_resp.raise_for_status()
                
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
                    summary=body_text[:200] + "...", 
                    content_type="article",
                    body_text=body_text
                )
                articles.append(article)
                count += 1
            
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                consecutive_timeouts += 1
                logger.warning(f"Timeout/Connection error deep scraping {full_url} ({consecutive_timeouts}/{MAX_TIMEOUTS})")
                continue
            except Exception as e:
                # logger.debug(f"Failed to deep scrape {full_url}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Failed to scrape {source_name}: {e}")
        
    return articles

import concurrent.futures
import time
import threading

def scrape_site_with_timeout(site_config, config, timeout=30) -> List[Article]:
    """Wrapper to enforce hard timeout on site scraping."""
    result = []
    error = None
    
    def target():
        nonlocal result, error
        try:
            result = scrape_site(site_config, config)
        except Exception as e:
            error = e

    # Create and start thread
    t = threading.Thread(target=target)
    t.start()
    
    # Wait for completion or timeout
    t.join(timeout=timeout)
    
    if t.is_alive():
        logger.warning(f"⏱️ {site_config.get('name')}: Timeout after {timeout}s - aborting")
        return []
        
    if error:
        raise error
        
    return result

def scrape_web(config) -> List[Article]:
    """Scrape articles from configured websites with robust parallel execution."""
    all_articles = []
    sites = config.get('sources', {}).get('scrape', [])
    
    # Filter enabled sites
    active_sites = [s for s in sites if s.get('enabled', True) is not False]
    
    if not active_sites:
        logger.warning("No scrape sources configured or enabled.")
        return []
        
    logger.info(f"Starting parallel scraping for {len(active_sites)} sites...")
    
    stats = {
        'success': 0,
        'failed': 0,
        'timeout': 0,
        'details': []
    }
    
    start_time_total = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit jobs
        future_to_site = {
            executor.submit(scrape_site_with_timeout, site, config, timeout=45): site 
            for site in active_sites
        }
        
        # Wait for all with a global timeout (slightly larger than per-site * workers/concurrency)
        # But per-site timeout should handle individual hangs.
        # Global timeout is a safety net.
        done, pending = concurrent.futures.wait(
            future_to_site.keys(),
            timeout=180, # 3 minutes total safety net
            return_when=concurrent.futures.ALL_COMPLETED
        )
        
        # Process completed
        for future in done:
            site = future_to_site[future]
            site_name = site.get('name', 'Unknown')
            t0 = time.time() # We don't have exact start time of thread here easily without passing it, but we can measure future processing? No.
            # actually we want execution time. scrape_site should log/return it? 
            # Simplified: just handle results.
            
            try:
                articles = future.result()
                if articles:
                    all_articles.extend(articles)
                    stats['success'] += 1
                    stats['details'].append(f"✅ {site_name}: {len(articles)} arts")
                else:
                    # Empty result could be timeout (logged in wrapper) or just no news
                    # We assume success if no exception raised, even if 0 articles
                    stats['success'] += 1
                    stats['details'].append(f"✅ {site_name}: 0 arts")
                    
            except Exception as e:
                stats['failed'] += 1
                logger.error(f"❌ {site_name}: Failed - {e}")
                stats['details'].append(f"❌ {site_name}: Error")

        # Process pending (Global Timeout)
        for future in pending:
            site = future_to_site[future]
            site_name = site.get('name', 'Unknown')
            logger.warning(f"⏱️ {site_name}: Global scraper timeout - cancelled")
            stats['timeout'] += 1
            stats['details'].append(f"⏱️ {site_name}: Timeout")
            future.cancel()
            
    total_time = time.time() - start_time_total
    
    # Log Summary
    separator = "═" * 60
    logger.info(separator)
    logger.info(f"📊 SCRAPING REPORT (Total: {total_time:.1f}s)")
    logger.info(separator)
    logger.info(f"✅ Success: {stats['success']} sites")
    logger.info(f"❌ Failed:  {stats['failed']} sites")
    logger.info(f"⏱️ Timeout: {stats['timeout']} sites")
    logger.info("─" * 60)
    for line in stats['details']:
        logger.info(line)
    logger.info(separator)
    
    logger.info(f"Collected {len(all_articles)} valid articles from web scraping.")
    return all_articles
