import feedparser
import urllib.parse
from datetime import datetime, timedelta
from typing import List
import logging
from .models import Article

class IntelligentSearchAgent:
    """Söker aktivt efter nyheter via Google News RSS"""
    
    GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"
    
    
    def __init__(self, queries: List[str] = None, max_age_hours: int = 48):
        self.queries = queries or []
        self.max_age_hours = max_age_hours
        self.logger = logging.getLogger(__name__)
    
    def build_google_news_url(self, query: str) -> str:
        """Bygger Google News RSS URL för en sökterm"""
        encoded_query = urllib.parse.quote(query)
        # hl=sv (språk), gl=SE (land), ceid=SE:sv (edition)
        return f"{self.GOOGLE_NEWS_RSS_BASE}?q={encoded_query}&hl=sv&gl=SE&ceid=SE:sv"
    
    def search(self) -> List[dict]:
        """Kör alla sökningar och returnerar unika artiklar"""
        all_articles = []
        seen_urls = set()
        
        self.logger.info("Agent: Starting active search via Google News RSS...")
        
        for query in self.queries:
            self.logger.info(f"Agent: Searching Google News for '{query}'...")
            
            url = self.build_google_news_url(query)
            
            try:
                feed = feedparser.parse(url)
                
                if feed.bozo:
                    self.logger.warning(f"Feed parse error for '{query}': {feed.bozo_exception}")
                    continue
                
                count = 0
                for entry in feed.entries:
                    # Extrahera den faktiska URL:en (Google News wrapprar länkar)
                    article_url = self.extract_real_url(entry.get('link', ''))
                    
                    # Hoppa över dubletter
                    if article_url in seen_urls:
                        continue
                    seen_urls.add(article_url)
                    
                    # Parsa publiceringsdatum
                    published = self.parse_date(entry.get('published', ''))
                    
                    # Filtrera bort för gamla artiklar om datum finns
                    if published and self.is_too_old(published):
                        continue
                    
                    # Om inget datum, sätt till nu (vanligt för sökresultat)
                    if not published:
                        published = datetime.now().astimezone()

                    article_data = {
                        'title': entry.get('title', ''),
                        'url': article_url,
                        'description': self.clean_description(entry.get('summary', '')),
                        'source': self.extract_source(entry),
                        'published': published,
                        'found_via': f"Google News: '{query}'"
                    }
                    
                    all_articles.append(article_data)
                    count += 1
                    
                self.logger.info(f"Agent: Found {count} new results for '{query}'")
                
            except Exception as e:
                self.logger.error(f"Agent: Error searching for '{query}': {e}")
                continue
        
        self.logger.info(f"Agent: Found {len(all_articles)} unique articles via active search.")
        return all_articles
    
    def extract_real_url(self, google_url: str) -> str:
        """Google News wrappar länkar - extrahera den riktiga URL:en"""
        # Google News-länkar ser ut så här:
        # https://news.google.com/rss/articles/CBMi...
        # Den riktiga länken finns ofta i redirect eller måste följas.
        # För enkelhetens skull returnerar vi wrapper-länken då den fungerar för användaren.
        return google_url
    
    def extract_source(self, entry) -> str:
        """Extrahera källans namn från RSS-entry"""
        # Google News inkluderar källan i titeln: "Rubrik - Källan"
        title = entry.get('title', '')
        if ' - ' in title:
            return title.split(' - ')[-1].strip()
        
        # Alternativt, kolla source-fältet
        source = entry.get('source', {})
        if isinstance(source, dict):
            return source.get('title', 'Okänd källa')
        
        return 'Okänd källa'
    
    def clean_description(self, summary: str) -> str:
        """Rensa HTML från beskrivningen"""
        import re
        # Ta bort HTML-taggar
        clean = re.sub(r'<[^>]+>', '', summary)
        # Ta bort extra whitespace
        clean = ' '.join(clean.split())
        return clean[:300]  # Max 300 tecken
    
    def parse_date(self, date_str: str) -> datetime:
        """Parsa datum från RSS-feed"""
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(date_str)
        except:
            return None
    
    def is_too_old(self, published: datetime) -> bool:
        """Kolla om artikeln är för gammal"""
        from datetime import timezone
        
        if published.tzinfo is None:
             published = published.astimezone()
             
        now = datetime.now(published.tzinfo)
        age = now - published
        return age > timedelta(hours=self.max_age_hours)

def run_search_agent(config) -> List[Article]:
    """
    Run the intelligent search agent.
    """
    agent_config = config.get('search_agent', {})
    
    if not agent_config.get('enabled'):
        return []

    queries = agent_config.get('queries', [])
    # Instantiera agenten
    agent = IntelligentSearchAgent(queries=queries, max_age_hours=48)
    search_results = agent.search()
    
    articles = []
    # Konvertera till Article-objekt
    for result in search_results:
        article = Article(
            title=result['title'],
            url=result['url'],
            source=result['source'],
            published_date=result['published'],
            summary=result['description'],
            content_type="article",
            # relevant=True,  <- Removed
            relevance_score=0.6, # Startpoäng för sökresultat
            found_via=result['found_via']
        )
        articles.append(article)
        
    return articles
