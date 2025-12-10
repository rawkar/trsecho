import feedparser
import logging
from datetime import datetime
from dateutil import parser as date_parser
from typing import List
from .models import Article

logger = logging.getLogger(__name__)

def parse_date(date_str):
    """Parse date string to datetime object."""
    if not date_str:
        return datetime.now().astimezone()
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            return dt.astimezone()
        return dt
    except Exception:
        return datetime.now().astimezone()

def collect_rss(config) -> List[Article]:
    """Collect articles from configured RSS feeds."""
    articles = []
    feeds = config.get('sources', {}).get('rss', [])
    
    if not feeds:
        logger.warning("No RSS feeds configured.")
        return []

    for feed_config in feeds:
        url = feed_config.get('url')
        source_name = feed_config.get('name', 'Unknown')
        
        if not url:
            continue
            
        logger.info(f"Fetching RSS feed: {source_name} ({url})")
        
        try:
            feed = feedparser.parse(url)
            
            if feed.bozo:
                logger.warning(f"Error parsing feed {source_name}: {feed.bozo_exception}")
                # Continue anyway as feedparser often returns usable data even with errors
            
            for entry in feed.entries[:10]: # Limit to 10 latest per feed
                try:
                    title = entry.get('title', 'No Title')
                    link = entry.get('link', '')
                    summary = entry.get('summary', '') or entry.get('description', '')
                    published = entry.get('published', '') or entry.get('updated', '')
                    
                    if not link:
                        continue
                        
                    article = Article(
                        title=title,
                        url=link,
                        source=source_name,
                        published_date=parse_date(published),
                        summary=summary[:500], # Truncate summary
                        content_type="article"
                    )
                    articles.append(article)
                    
                except Exception as e:
                    logger.error(f"Error processing entry in {source_name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to fetch feed {source_name}: {e}")
            
    logger.info(f"Collected {len(articles)} articles from RSS feeds.")
    return articles
