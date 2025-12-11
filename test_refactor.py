import logging
from datetime import datetime
from src.models import Article
from src.search_agent import IntelligentSearchAgent
from src.categorizer import categorize_articles, RelevanceScorer
from src.enricher import enrich_article
from src.scraper import scrape_site

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_search_agent():
    logger.info("Testing Search Agent (Google News RSS)...")
    agent = IntelligentSearchAgent(max_age_hours=48)
    
    query = "trygghetsråd"
    url = agent.build_google_news_url(query)
    logger.info(f"Generated URL: {url}")
    
    # We mock search to avoid spamming Google
    results = agent.search()
    logger.info(f"Found {len(results)} articles.")
    if results:
        logger.info(f"Sample: {results[0]['title']} ({results[0]['url']})")

def test_categorization_and_enrichment():
    logger.info("Testing Categorization & Enrichment...")
    
    # Test Trusted Domain
    a1 = Article(
        title="Nytt omställningsavtal klart",
        url="https://www.ptk.se/nyheter/nytt-avtal",
        source="PTK",
        published_date=datetime.now(),
        summary="Detta är en viktig nyhet om omställning.",
        body_text="Detta är en viktig nyhet om omställning för alla parter."
    )
    
    # Enrich
    enrich_article(a1)
    logger.info(f"Enriched Article 1: Org={a1.organization}, Domain={a1.domain}, Time={a1.estimated_read_time}min")
    
    # Categorize
    config = {
        'categories': [{'name': 'Omställning', 'keywords': ['omställning']}],
        'blocklist': {'titles': [], 'urls': []},
        'app': {'min_relevance_score': 0.1, 'max_article_age_days': 2, 'min_content_length': 10}
    }
    
    cats = categorize_articles([a1], config)
    logger.info(f"Categorized Article 1: {a1.category} score={a1.relevance_score}")
    
    # Test Concept Cluster via RelevanceScorer
    a2 = Article(
        title="Uppsägningar inom teatern",
        url="https://www.random-blog.se/teater-kris",
        source="Random Blog",
        published_date=datetime.now(),
        summary="Många skådespelare förlorar jobbet.",
        body_text="Det är tufft nu."
    )
    enrich_article(a2)

    scorer = RelevanceScorer()
    score, reason = scorer.calculate_relevance(a2)
    logger.info(f"Article 2 Score: {score} ({reason})")
    
    # Test Categorization Flow
    cats2 = categorize_articles([a2], config)
    # Check if a2 ended up in a category
    logger.info(f"Categorized Article 2: {a2.category} score={a2.relevance_score}")

def test_scraper_single():
    logger.info("Testing Scraper Single Site...")
    config = {
        'app': {'max_article_age_days': 5, 'min_content_length': 10},
        'blocklist': {'titles': [], 'urls': []}
    }
    site_config = {
        'url': 'https://www.ptk.se/nyheter-och-press/nyheter/',
        'name': 'PTK Nyheter',
        'selector': 'h3 a' 
    }
    site_config['selector'] = 'a'
    
    articles = scrape_site(site_config, config)
    logger.info(f"Scraped {len(articles)} articles from PTK.")
    for a in articles[:3]:
        logger.info(f" - {a.title}")

if __name__ == "__main__":
    test_search_agent()
    test_categorization_and_enrichment()
    # test_scraper_single() 
