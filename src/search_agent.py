import feedparser
import logging
import urllib.parse
from datetime import datetime
from typing import List
from .models import Article
from .source_validator import validate_source

logger = logging.getLogger(__name__)

def search_google_news_rss(query: str) -> List[Article]:
    """
    Search Google News via RSS.
    This is a free and effective way to get news results without an API key.
    """
    encoded_query = urllib.parse.quote(query)
    # search for past 24h (when:1d) and in Swedish (hl=sv, gl=SE, ceid=SE:sv)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}+when:1d&hl=sv&gl=SE&ceid=SE:sv"
    
    articles = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]: # Top 5 per query
            title = entry.get('title', '')
            link = entry.get('link', '')
            published = entry.get('published', '')
            source = entry.get('source', {}).get('title', 'Google News')
            
            if not link:
                continue
                
            # Google News RSS links are redirects, but usually valid enough for display
            # Optionally we could resolve them, but that takes time.
            
            # Parse date
            try:
                from dateutil import parser as date_parser
                pub_date = date_parser.parse(published)
            except:
                pub_date = datetime.now().astimezone()

            article = Article(
                title=title,
                url=link,
                source=f"{source} (via Google News)",
                published_date=pub_date,
                summary=f"Found via search for: {query}",
                content_type="article",
                relevance_score=0.5, # Default score for search results
                body_text="" # Search results don't have body text initially, could be enriched later
            )
            articles.append(article)
            
    except Exception as e:
        logger.error(f"Google News RSS search failed for '{query}': {e}")
        
    return articles

def run_search_agent(config) -> List[Article]:
    """
    Run the intelligent search agent.
    1. Validate configured sources (and try to find alternatives if down - placeholder logic).
    2. Active search using configured queries.
    """
    articles = []
    agent_config = config.get('search_agent', {})
    
    if not agent_config.get('enabled'):
        return []

    logger.info("Agent: Starting active search...")
    
    # 1. Active Search
    queries = agent_config.get('queries', [])
    for query in queries:
        logger.info(f"Agent: Searching for '{query}'...")
        results = search_google_news_rss(query)
        articles.extend(results)
        
    # 2. Discovery / Fallback (Placeholder for advanced logic)
    # In a full implementation, we would check the 'source_validator' report
    # and if a source is down, we would specifically search for that source's name.
    
    logger.info(f"Agent: Found {len(articles)} articles via active search.")
    return articles
