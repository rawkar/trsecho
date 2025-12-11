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
    
    # Extract Domain
    from urllib.parse import urlparse
    try:
        domain = urlparse(article.url).netloc.replace('www.', '')
        article.domain = domain
    except:
        article.domain = ""

    # Clean Source Name / Organization
    # 1. Use existing source if it's clean (not a URL)
    if article.source and '.' not in article.source:
        article.organization = article.source
    # 2. If source is a URL, try to map it or use domain
    elif article.domain:
        # Simple heuristic capitalization
        parts = article.domain.split('.')
        if len(parts) >= 2:
            name = parts[-2]
            article.organization = name.capitalize() # e.g. "dn" -> "Dn" (Not perfect but better)
            
            # Manual Mapping Overrides
            mappings = {
                'dn': 'Dagens Nyheter',
                'svd': 'Svenska Dagbladet',
                'sverigesradio': 'Sveriges Radio',
                'svt': 'SVT',
                'dagenssamhalle': 'Dagens Samhälle',
                'arbetsvarlden': 'Arbetsvärlden',
                'lag-avtal': 'Lag & Avtal',
                'arbetet': 'Arbetet',
                'kollega': 'Kollega',
                'publikt': 'Publikt',
                'akademikern': 'Akademikern'
            }
            if name in mappings:
                article.organization = mappings[name]
        else:
            article.organization = article.domain
    else:
        article.organization = "Okänd"
        
    # Estimated Read Time
    # Avg reading speed 200 wpm
    word_count = len(article.body_text.split()) if article.body_text else 0
    # Use summary if body text is empty
    if word_count == 0 and article.summary:
        word_count = len(article.summary.split())
        
    read_time = max(1, round(word_count / 200))
    article.estimated_read_time = read_time
    
    return article

def enrich_articles(articles: List[Article], config) -> List[Article]:
    """Enrich a list of articles."""
    for article in articles:
        enrich_article(article)
    return articles
