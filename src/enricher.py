import logging
from typing import List
from .models import Article

logger = logging.getLogger(__name__)

def enrich_article(article: Article):
    """
    Enrich article with metadata:
    - Content Type (Article, PDF, Video, etc.)
    - Clean Source Name
    """
    url_lower = article.url.lower()
    
    # Detect Content Type
    if url_lower.endswith('.pdf'):
        article.content_type = "pdf"
    elif any(x in url_lower for x in ['youtube.com', 'vimeo.com', 'play.']):
        article.content_type = "video"
    elif 'press' in url_lower or 'pressmeddelande' in url_lower:
        article.content_type = "press_release"
    elif 'podd' in url_lower or 'podcast' in url_lower:
        article.content_type = "podcast"
    else:
        article.content_type = "article"
        
    # Clean Source Name (if it looks like a domain)
    if '.' in article.source and ' ' not in article.source:
        # It's likely a domain, try to make it prettier
        # e.g. "www.dn.se" -> "DN" (This is hard to do generically perfectly, but we can try)
        pass 
        
    # If source is generic "YouTube", try to extract channel if possible (hard without API)
    
    return article

def enrich_articles(articles: List[Article], config) -> List[Article]:
    """Enrich a list of articles."""
    for article in articles:
        enrich_article(article)
    return articles
