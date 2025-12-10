import logging
from typing import List
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from .models import Article

logger = logging.getLogger(__name__)

def is_similar(a: str, b: str, threshold: float = 0.85) -> bool:
    """Check if two strings are similar."""
    return SequenceMatcher(None, a, b).ratio() > threshold

def deduplicate_articles(articles: List[Article], config) -> List[Article]:
    """
    Remove duplicate articles based on URL and title similarity.
    Also filters out old articles (older than 7 days).
    """
    unique_articles = []
    seen_urls = set()
    seen_titles = []
    
    threshold = config.get('app', {}).get('deduplication_threshold', 0.85)
    max_age_days = config.get('app', {}).get('max_article_age_days', 7)
    
    # Calculate cutoff date
    cutoff_date = datetime.now().astimezone() - timedelta(days=max_age_days)
    
    # Filter out ads/sponsored content and old articles first
    filtered_articles = []
    blocklist = ["annons", "sponsrad", "reklam"]
    
    old_count = 0
    for article in articles:
        # Filter by date
        if article.published_date < cutoff_date:
            old_count += 1
            continue
            
        text_lower = f"{article.title} {article.summary}".lower()
        if any(term in text_lower for term in blocklist):
            continue
        filtered_articles.append(article)
    
    if old_count > 0:
        logger.info(f"Filtered out {old_count} articles older than {max_age_days} days")
        
    # Deduplicate
    for article in filtered_articles:
        # 1. Check URL
        if article.url in seen_urls:
            continue
            
        # 2. Check Title Similarity
        is_duplicate = False
        for seen_title in seen_titles:
            if is_similar(article.title.lower(), seen_title.lower(), threshold):
                is_duplicate = True
                break
        
        if is_duplicate:
            continue
            
        unique_articles.append(article)
        seen_urls.add(article.url)
        seen_titles.append(article.title)
        
    logger.info(f"Deduplication: Reduced {len(articles)} to {len(unique_articles)} articles.")
    return unique_articles
