import logging
from datetime import datetime, timedelta
from typing import List, Dict
from .models import Article

logger = logging.getLogger(__name__)

def calculate_relevance(text: str, config) -> float:
    """
    Calculate relevance score based on keyword presence and context.
    """
    text_lower = text.lower()
    score = 0.0
    
    # 1. Critical Terms (Core Mission) - Big Boost
    critical_terms = [
        "trygghetsråd", "trs", "ptk", "svensk scenkonst", "arbetsgivaralliansen",
        "teateralliansen", "dansalliansen", "musikalliansen", "omställningsavtal",
        "omställningsstöd", "kultursektorn", "ideell sektor", "kulturrådet"
    ]
    
    # 2. Medium Value Terms (Industry Relevance) - Small Boost
    # These alone should give enough score to pass the threshold (0.2-0.3)
    medium_terms = [
        "arbetsmarknad", "kollektivavtal", "omställning", "kompetensutveckling",
        "uppsägning", "arbetsbrist", "fackförbund", "avtalsrörelse", "lönerevision",
        "yrkeshögskola", "studier", "arbetsmiljö", "las", "anställningsskydd"
    ]
    
    # 3. Static/Irrelevant Indicators - Penalty
    static_terms = [
        "om oss", "kontakta oss", "styrelse", "stadgar", "våra medlemmar",
        "bli medlem", "logga in", "mina sidor", "integritetspolicy",
        "om webbplatsen", "tillgänglighetsredogörelse", "hitta hit",
        "fakturering", "pressrum", "grafisk profil", "lediga jobb hos oss",
        "vad gör", "så finansieras", "vårt uppdrag", "organisation"
    ]
    
    # Check Negative/Static Terms First
    negative_terms = config.get('blocklist', {}).get('titles', [])
    for term in negative_terms + static_terms:
        if term in text_lower:
            score -= 0.5
            
    # Check Critical Terms
    for term in critical_terms:
        if term in text_lower:
            score += 0.4
            
    # Check Medium Terms
    for term in medium_terms:
        if term in text_lower:
            score += 0.15
            
    # Cap score
    return min(max(score, 0.0), 1.0)

def categorize_articles(articles: List[Article], config) -> Dict[str, List[Article]]:
    """
    Categorize articles based on configuration.
    Returns a dictionary mapping category names to lists of articles.
    """
    categories_config = config.get('categories', [])
    categorized_data = {cat['name']: [] for cat in categories_config}
    categorized_data['Övrigt'] = [] # Fallback category
    
    min_score = config.get('app', {}).get('min_relevance_score', 0.3)
    blocklist = config.get('blocklist', {})
    blocked_titles = [t.lower() for t in blocklist.get('titles', [])]
    blocked_urls = [u.lower() for u in blocklist.get('urls', [])]
    
    for article in articles:
        # 1. Hard Blocklist Check (Titles & URLs)
        title_lower = article.title.lower()
        url_lower = article.url.lower()
        
        if any(term in title_lower for term in blocked_titles):
            logger.info(f"Skipping blocked title: {article.title}")
            continue
            
        if any(term in url_lower for term in blocked_urls):
            logger.info(f"Skipping blocked URL: {article.url}")
            continue

        # Combine title and summary for matching
        text_to_check = f"{article.title} {article.summary}"
        text_lower = text_to_check.lower()
        
        # 2. Relevance Calculation
        # We recalculate/adjust score even if it exists (e.g. from search agent) 
        # to ensure negative terms are applied.
        
        calculated_score = calculate_relevance(text_to_check, config)
        
        if article.relevance_score > 0.0:
            # If article already has a score (e.g. 0.5 from search), we average it with calculated
            # but we ensure negative penalties from calculate_relevance are felt.
            # If calculate_relevance is 0.0 (due to negative terms), the result should be low.
            article.relevance_score = (article.relevance_score + calculated_score) / 2
        else:
            article.relevance_score = calculated_score
            
        # Filter out low relevance articles
        if article.relevance_score < min_score:
            logger.info(f"Skipping low relevance article: {article.title} (Score: {article.relevance_score})")
            continue

        # 3. Strict Date Filter (Double check)
        max_age_days = config.get('app', {}).get('max_article_age_days', 2)
        cutoff_date = datetime.now().astimezone() - timedelta(days=max_age_days)
        
        # Ensure article date is timezone aware for comparison
        if article.published_date.tzinfo is None:
            article.published_date = article.published_date.astimezone()
            
        if article.published_date < cutoff_date:
            logger.info(f"Skipping old article: {article.title} ({article.published_date})")
            continue

        # 4. Content Density Filter (if body_text is available)
        min_content_length = config.get('app', {}).get('min_content_length', 300)
        if article.body_text and len(article.body_text) < min_content_length:
             logger.info(f"Skipping thin content: {article.title} ({len(article.body_text)} chars)")
             continue
        
        assigned_category = None
        
        # Check categories in order
        for cat_config in categories_config:
            cat_name = cat_config['name']
            keywords = [k.lower() for k in cat_config.get('keywords', [])]
            
            if any(keyword in text_lower for keyword in keywords):
                assigned_category = cat_name
                break
        
        # Assign to category
        if assigned_category:
            article.category = assigned_category
            categorized_data[assigned_category].append(article)
        else:
            # Add to 'Övrigt' if it passes the minimum threshold
            # (it already passed the threshold check above, so we know score >= min_score)
            article.category = 'Övrigt'
            categorized_data['Övrigt'].append(article)
            
    # Sort articles by date (newest first) within each category
    for cat in categorized_data:
        categorized_data[cat].sort(key=lambda x: x.published_date, reverse=True)
        
        # Limit per category
        limit = config.get('app', {}).get('max_articles_per_category', 10)
        categorized_data[cat] = categorized_data[cat][:limit]
        
    return categorized_data
