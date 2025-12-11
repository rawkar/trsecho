import logging
from datetime import datetime, timedelta
from typing import List, Dict
from .models import Article

logger = logging.getLogger(__name__)

# Trust-Based Domain Lists
HIGH_TRUST_DOMAINS = [
    'ptk.se', 'svenskscenkonst.se', 'arbetsgivaralliansen.se',
    'teateralliansen.se', 'dansalliansen.se', 'musikalliansen.se',
    'trr.se', 'omstella.se', 'kulturradet.se', 'konstnarsnamnden.se',
    'fremia.se', 'scensverige.se', 'musikerforbundet.se', 'nodsverige.se',
    'nysta.nu', 'famna.se', 'famna.org', 'trs.se'
]

MEDIUM_TRUST_DOMAINS = [
    'musikerforbundet.se', 'scenochfilm.se', 'regeringen.se'
]

LOW_TRUST_DOMAINS = [
    'tn.se', 'arbetet.se', 'kollega.se', 'dagenssamhalle.se',
    'publikt.se', 'svensktnaringsliv.se'
]

class RelevanceScorer:
    """
    Bedömer relevans för TRS baserat på:
    1. Käll-trust (varifrån kommer artikeln?)
    2. Branschrelevans (handlar den om TRS sektorer?)
    3. Ämnesrelevans (handlar den om TRS sakfrågor?)
    4. Negativa signaler (finns det indikationer på irrelevans?)
    """
    
    # Sektorer som TRS ARBETAR MED
    TRS_SECTORS = [
        # Scenkonst
        'teater', 'orkester', 'opera', 'balett', 'dans', 'musik', 'scenkonst',
        'konserthus', 'dramatisk', 'scen', 'föreställning', 'repertoar',
        'symfoni', 'kör', 'dirigent', 'musiker', 'skådespelare', 'dansare',
        
        # Ideell sektor
        'ideell', 'idéburen', 'civilsamhälle', 'folkrörelse', 'förening',
        'stiftelse', 'folkhögskola', 'trossamfund', 'kyrka', 'idrott',
        'riksidrottsförbund',
        
        # Kultur generellt
        'kultur', 'konstnär', 'konstnärlig', 'kulturarbetare', 'kultursektor',
        
        # Specifika organisationer
        'teateralliansen', 'dansalliansen', 'musikalliansen',
        'arbetsgivaralliansen', 'svensk scenkonst', 'ptk', 'fremia'
    ]
    
    # Sektorer som TRS INTE arbetar med
    NON_TRS_SECTORS = [
        # Industri
        'fabrik', 'tillverkning', 'industri', 'produktion', 'verkstad',
        'livsmedel', 'slakteri', 'kycklingfabrik', 'stål', 'papper',
        
        # Transport
        'tåg', 'lokförare', 'sj ', 'pendeltåg', 'tunnelbana', 'buss',
        'lastbil', 'chaufför', 'transport', 'logistik', 'flyg',
        
        # Handel och service
        'butik', 'detaljhandel', 'handel', 'restaurang', 'hotell',
        'besöksnäring', 'krog',
        
        # Offentlig sektor (utanför TRS)
        'kommun', 'region', 'landsting', 'myndighet', 'statlig',
        'grundskola', 'gymnasium', 'friskola', 'lärare',
        
        # Vård (utanför idéburen)
        'sjukhus', 'vårdcentral', 'regionvård', 'läkare', 'sjuksköterska',
        'lss-boende', 'äldreboende',
        
        # Bygg
        'bygge', 'byggarbetsplats', 'entreprenad', 'anläggning',

        # Bild och Form (Utanför Scenkonst)
        'iaspis', 'bild och form', 'bildkonst', 'formkonst', 'konsthantverk',
        'utställning' # Ofta relevant men kan vara falsk positiv, se upp
    ]

    NON_SWEDISH_INDICATORS = [
        'bulgarien', 'grekland', 'grekiska', 'danmark', 'norge', 'finland',
        'tyskland', 'frankrike', 'italien', 'spanien', 'polen', 'eu-budget',
        'europeiska kommissionen', 'bryssel', 'usa', 'kinda', 'japan'
    ]

    WORK_ANGLE_REQUIRED_SOURCES = [
        'sverigesradio.se', 'tv4.se', 'svt.se', 'dn.se', 'svd.se', 
        'expressen.se', 'aftonbladet.se'
    ]
    
    # Sakfrågor som är KÄRNAN för TRS
    TRS_CORE_TOPICS = [
        'omställning', 'omställningsstöd', 'omställningsavtal',
        'uppsägning', 'arbetsbrist', 'varsel', 'nedskärning',
        'karriärväxling', 'karriäromställning',
        'kompetensutveckling', 'kompetensstöd',
        'omställningsstudiestöd', 'trygghetsråd',
        'kollektivavtal', 'partssamverkan',
        'frilans', 'tidsbegränsad anställning',
        'anställning', 'arbetsmarknad', 'arbetsmiljö', 'lön'
    ]
    
    WORK_ANGLE_KEYWORDS = [
        'anställ', 'uppsäg', 'varsel', 'nedskärning', 'sparkrav',
        'omställ', 'kollektivavtal', 'frilans', 'löne', 'personal',
        'jobb', 'rekryter', 'avsked', 'pension', 'budget', 'arbetsmiljö',
        'fack', 'trygghet', 'villkor'
    ]

    REVIEW_INDICATORS = [
        # Recensionsord
        'recension', 'recenserar', 'betyg', 'stjärnor',
        'premiär', 'urpremiär', 'nypremiär',
        
        # Föreställningsbeskrivningar
        'föreställning', 'pjäs', 'uppsättning', 'regigrepp',
        'rollprestation', 'scenografi', 'manus',
        
        # Konsertbeskrivningar
        'konsert', 'spelning', 'turné', 'album', 'skiva', 'låt',
        
        # Upplevelsebeskrivningar
        'gripande', 'mäktig', 'rörande', 'underhållande',
        'publiksuccé', 'succé', 'sevärd', 'magisk',
        
        # Kulturjournalistik/porträtt
        'berättar om', 'livshistoria', 'karriär',
        'skådespelaren', 'artisten', 'musikern', 'intervju med',
        
        # Sammanfattningar
        'årets bästa', 'årets teater', 'teateråret', 'musikåret',
        'jubileum', 'firande', 'hyllning',
    ]

    def calculate_relevance(self, article: Article) -> tuple[float, str]:
        """
        Returnerar (relevanspoäng, förklaring)
        Poäng 0.0-1.0 där högre = mer relevant
        """
        score = 0.0
        reasons = []
        
        # Combine title, summary and body if available for better context
        text = f"{article.title} {article.summary} {article.body_text[:500]}".lower()
        source = article.domain.lower() if article.domain else (article.source.lower() if article.source else "")
        
        # STEG 0: Geografisk filtrering (Ny)
        if not self.check_geographic_relevance(text):
            return (0.0, "Irrelevant geografi (utlandet)")

        # STEG 1: Kolla käll-trust
        source_modifier = self.get_source_modifier(source)
        
        # STEG 1.5: Arbetsmarknadsvinkel för generella nyheter (Ny & Update)
        # Check explicit generic source constraint
        if hasattr(self, 'requires_work_angle') and self.requires_work_angle(source, text):
             pass # logic handled inside check_work_angle actually

        if not self.check_work_angle(source, text):
             return (0.0, "Saknar arbetsmarknadsvinkel (generell källa)")

        # NYTT STEG 1.6: Filtrera recensioner och kulturjournalistik
        # Gäller INTE för high-trust-källor (om source_modifier >= 2.0)
        if source_modifier < 2.0:
            is_review, review_reason = self._is_review_or_entertainment(text)
            if is_review:
                return (0.0, review_reason)

        # STEG 2: Kolla om det handlar om TRS sektorer
        sector_score, sector_reason = self.check_sector_relevance(text)
        if sector_score < 0:
            # Artikeln handlar om en sektor TRS INTE arbetar med
            return (0.0, f"Irrelevant sektor: {sector_reason}")
        score += sector_score
        if sector_reason:
            reasons.append(sector_reason)
        
        # STEG 3: Kolla om det handlar om TRS sakfrågor
        topic_score, topic_reason = self.check_topic_relevance(text)
        score += topic_score
        if topic_reason:
            reasons.append(topic_reason)
        
        # STEG 4: Justera baserat på källa
        # If source is high trust, we ensure at least a small positive score if no strong irrelevance
        if source_modifier > 1.5 and score < 0.1:
             score = 0.1
             reasons.append("Hög förtroendekälla/Low baseline")

        final_score = min(1.0, score * source_modifier)
        
        return (final_score, "; ".join(reasons) if reasons else "Ingen stark signal")
    
    def _is_review_or_entertainment(self, text: str) -> tuple[bool, str]:
        """
        Kontrollerar om artikeln är en recension eller kulturjournalistik
        utan arbetsmarknadsvinkel.
        Returns: (är_recension, anledning)
        """
        text_lower = text.lower()
        
        # Om artikeln har arbetsmarknadsvinkel är det INTE en ren recension
        if any(kw in text_lower for kw in self.WORK_ANGLE_KEYWORDS):
            return (False, "")
            
        # Scenkonst-upplevelsetermer som indikerar recension/evenemang om de står ensamma (utan arbetsvinkel)
        PERFORMANCE_TERMS = [
            'föreställning', 'pjäs', 'uppsättning', 'konsert', 
            'spelning', 'turné', 'premiär', 'repertoar'
        ]
        
        for term in PERFORMANCE_TERMS:
            if term in text_lower:
                return (True, f"Recension/kulturartikel: {term}")
        
        # Kolla även om den handlar om scenkonst generellt och har recensionsord
        has_scenkonst = any(s in text_lower for s in [
            'teater', 'opera', 'balett', 'orkester', 'dans', 
            'musik', 'konsert', 'scen', 'dramatik'
        ])
        
        if has_scenkonst:
            # Kolla efter recensionsindikatorer
            for indicator in self.REVIEW_INDICATORS:
                if indicator in text_lower:
                    return (True, f"Recension/kulturartikel: {indicator}")
        
        return (False, "")

    def check_geographic_relevance(self, text: str) -> bool:
        """Returnerar False om artikeln tydligt handlar om annat land."""
        for indicator in self.NON_SWEDISH_INDICATORS:
            if indicator in text:
                # Men kolla om det OCKSÅ nämner Sverige
                if 'sverige' in text or 'svensk' in text:
                    return True  # Jämförande artikel, kan vara relevant
                return False
        return True

    def check_work_angle(self, source: str, text: str) -> bool:
        """
        Kräv arbetsmarknadsvinkel för generella nyhetskällor.
        Returnerar True om artikeln är OK (antingen inte generell källa, eller har vinkel).
        """
        is_general_source = any(s in source for s in self.WORK_ANGLE_REQUIRED_SOURCES)
        if not is_general_source:
            return True
            
        work_keywords = ['anställ', 'arbets', 'omställ', 'kollektivavtal', 
                         'frilans', 'uppsäg', 'varsel', 'löne', 'fack', 'trygghet']
        
        if any(kw in text for kw in work_keywords):
            return True
            
        return False
    
    def get_source_modifier(self, domain: str) -> float:
        """
        Käll-trust påverkar hur högt vi värderar artikeln.
        Kärnkällor får högre modifier (lättare att passera tröskeln).
        """
        for trusted in HIGH_TRUST_DOMAINS:
            if trusted in domain:
                return 2.0  # Dubbla poängen
        
        for medium in MEDIUM_TRUST_DOMAINS:
            if medium in domain:
                return 1.5
        
        for low in LOW_TRUST_DOMAINS:
            if low in domain:
                return 0.7  # Kräver starkare signaler
        
        return 1.0  # Default
    
    def check_sector_relevance(self, text: str) -> tuple[float, str]:
        """
        Kontrollerar om artikeln handlar om en relevant sektor.
        Returnerar negativt värde om den TYDLIGT handlar om fel sektor.
        """
        # Kolla först om det finns starka negativa signaler
        for sector in self.NON_TRS_SECTORS:
            if sector in text:
                # Men vänta - finns det OCKSÅ positiva signaler?
                has_positive = any(pos in text for pos in self.TRS_SECTORS)
                if not has_positive:
                    return (-1.0, sector)
        
        # Kolla positiva sektorsignaler
        matches = [s for s in self.TRS_SECTORS if s in text]
        if matches:
            # Cap matches score contribution
            return (0.3 * min(len(matches), 3), f"Sektor: {', '.join(matches[:3])}")
        
        return (0.0, "")
    
    def check_topic_relevance(self, text: str) -> tuple[float, str]:
        """
        Kontrollerar om artikeln handlar om TRS kärnfrågor.
        """
        matches = [t for t in self.TRS_CORE_TOPICS if t in text]
        if matches:
            return (0.4 * min(len(matches), 3), f"Ämne: {', '.join(matches[:3])}")
        
        return (0.0, "")

def should_include(article: Article, score: float, source_domain: str) -> bool:
    """
    Bestämmer om artikeln ska inkluderas baserat på poäng OCH källa.
    """
    domain = source_domain.lower() if source_domain else ""
    
    # Kärnkällor: Låg tröskel
    if any(t in domain for t in HIGH_TRUST_DOMAINS):
        return score >= 0.1
    
    # Generella nyhetskällor: Hög tröskel
    if any(t in domain for t in LOW_TRUST_DOMAINS):
        return score >= 0.50
    
    # Övriga: Medium tröskel
    return score >= 0.30

# Re-use CONCEPT_CLUSTERS for fallback categorization if needed, but Scorer logic works implicitly with these concepts too.
CONCEPT_CLUSTERS = {
    'Omställning': ['omställning', 'uppsägning', 'arbetsbrist', 'varsel', 
                    'karriärväxling', 'nytt jobb', 'arbetslös', 'arbetsförmedling',
                    'trygghetsråd', 'avgångsersättning', 'studier', 'yrkesväxling'],
    
    'Scenkonst': ['scenkonst', 'teater', 'dans', 'musik', 'orkester', 'opera', 'balett',
                  'skådespelare', 'musiker', 'dansare', 'konstnär', 'kultur',
                  'föreställning', 'scen', 'repertoar', 'koreograf', 'regissör'],
    
    'Civilsamhälle': ['civilsamhälle', 'ideell', 'förening', 'stiftelse', 'ngo', 
                      'folkrörelse', 'idéburen', 'frivillig', 'non-profit'],
                      
    'Arbetsmarknad': ['arbetsmarknad', 'sysselsättning', 'rekrytering', 'kompetens',
                      'bristyrke', 'arbetskraft', 'lönebildning', 'avtalsrörelse']
}

def categorize_articles(articles: List[Article], config) -> Dict[str, List[Article]]:
    """
    Categorize articles based on configuration + Relevance Scoring logic.
    """
    scorer = RelevanceScorer()
    categories_config = config.get('categories', [])
    categorized_data = {cat['name']: [] for cat in categories_config}
    categorized_data['Övrigt'] = [] 
    
    blocklist = config.get('blocklist', {})
    blocked_titles = [t.lower() for t in blocklist.get('titles', [])]
    blocked_urls = [u.lower() for u in blocklist.get('urls', [])]
    
    for article in articles:
        # 1. Hard Blocklist Check (Titles & URLs)
        if any(term in article.title.lower() for term in blocked_titles):
            logger.info(f"Skipping blocked title: {article.title}")
            continue
            
        if any(term in article.url.lower() for term in blocked_urls):
            logger.info(f"Skipping blocked URL: {article.url}")
            continue
            
        # 2. Date Filtering
        max_age_days = config.get('app', {}).get('max_article_age_days', 2)
        cutoff_date = datetime.now().astimezone() - timedelta(days=max_age_days)
         # Ensure article date is timezone aware for comparison
        if article.published_date.tzinfo is None:
            article.published_date = article.published_date.astimezone()
        
        if article.published_date < cutoff_date:
            logger.debug(f"Skipping old article: {article.title}")
            continue

        # 3. Content Density
        min_content_length = config.get('app', {}).get('min_content_length', 300)
        if article.body_text and len(article.body_text) < min_content_length:
             logger.debug(f"Skipping thin content: {article.title}")
             continue

        # 4. Relevance Calculation
        score, reason = scorer.calculate_relevance(article)
        
        # Use simple domain extraction
        domain = article.domain if article.domain else ""
        
        # 5. Filtering Decision
        if not should_include(article, score, domain):
            logger.info(f"❌ EXKLUDERAD ({score:.2f}): {article.title[:50]}... - {reason}")
            continue
        
        logger.info(f"✅ INKLUDERAD ({score:.2f}): {article.title[:20]}... - {reason}")
        article.relevance_score = score
        # article.relevance_reason = reason # Could add this field to Article model later for debugging email
        
        # 6. Categorization
        assigned_category = None
        text_lower = f"{article.title} {article.summary}".lower()
        
        # Check categories from config
        for cat_config in categories_config:
            cat_name = cat_config['name']
            keywords = [k.lower() for k in cat_config.get('keywords', [])]
            if any(keyword in text_lower for keyword in keywords):
                assigned_category = cat_name
                break
        
        # Fallback to Concept Clusters
        if not assigned_category:
            for cat_name, terms in CONCEPT_CLUSTERS.items():
                if any(term in text_lower for term in terms):
                    # Only assign if the category exists in output structure
                    if cat_name in categorized_data:
                        assigned_category = cat_name
                        break
        
        if assigned_category:
            article.category = assigned_category
            if assigned_category in categorized_data:
                categorized_data[assigned_category].append(article)
            else:
                 categorized_data['Övrigt'].append(article)
        else:
            article.category = 'Övrigt'
            categorized_data['Övrigt'].append(article)

    # Sort and Limit
    for cat in categorized_data:
        categorized_data[cat].sort(key=lambda x: x.published_date, reverse=True)
        limit = config.get('app', {}).get('max_articles_per_category', 10)
        categorized_data[cat] = categorized_data[cat][:limit]
        
    return categorized_data
