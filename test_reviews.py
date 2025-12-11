
import logging
from datetime import datetime
from src.models import Article
from src.categorizer import RelevanceScorer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_review_filtering():
    scorer = RelevanceScorer()
    
    test_cases = [
        {
            "title": "Gör vild föreställning om Folkhemmets mormor",
            "source": "tv4.se",
            "text": "Det är en gripande föreställning på Dramaten med starka rollprestationer. En publiksuccé.",
            "expect_include": False,
            "reason_part": "Recension"
        },
        {
            "title": "Teateråret 2025 – från Dödsdans till Das Kapital",
            "source": "sverigesradio.se",
            "text": "Vi sammanfattar teateråret och de bästa uppsättningarna. Det har varit ett magisk år för scenkonsten.",
            "expect_include": False,
            "reason_part": "Recension"
        },
        {
            "title": "Varsel på Malmö Opera – 20 tjänster försvinner",
            "source": "sverigesradio.se",
            "text": "Malmö Opera måste spara pengar och lägger nu varsel om uppsägning av personal. Det handlar om arbetsbrist.",
            "expect_include": True,
            "reason_part": ""
        },
        {
            "title": "Dramaten anställer 15 nya skådespelare",
            "source": "svt.se",
            "text": "Dramaten satsar och rekryterar nya skådespelare för fast anställning. Det är en stor satsning.",
            "expect_include": True,
            "reason_part": ""
        },
        {
            "title": "Hög kvalitet på Svensk Scenkonst föreställning",
            "source": "svenskscenkonst.se", # High trust source
            "text": "Vår medlemsorganisation sätter upp en fantastisk föreställning. Vi är stolta.",
            "expect_include": True, # Should NOT filter high trust even if it sounds like review
            "reason_part": ""
        }
    ]
    
    print("\n--- Testing Review Filtering ---")
    pass_count = 0
    for case in test_cases:
        article = Article(
            title=case['title'],
            url="http://example.com",
            source=case['source'],
            published_date=datetime.now(),
            summary=case['text'][:100],
            body_text=case['text']
        )
        # Needs domain for modifier check
        article.domain = case['source']
        
        score, reason = scorer.calculate_relevance(article)
        print(f"Article: '{case['title']}'")
        print(f"  Source: {case['source']}")
        print(f"  Score: {score}")
        print(f"  Reason: {reason}")
        
        start_included = (score > 0)
        
        if start_included == case['expect_include']:
            print("  ✅ PASS")
            pass_count += 1
        else:
            print(f"  ❌ FAIL (Expected {'Include' if case['expect_include'] else 'Exclude'})")
            
    print(f"\nPassed {pass_count}/{len(test_cases)}")

if __name__ == "__main__":
    test_review_filtering()
