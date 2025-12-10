import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_search_report(articles, source_health_report, config):
    """
    Generate a text-based search report.
    """
    report_lines = []
    
    # 1. Source Health
    rss_health = source_health_report.get('rss', {})
    scrape_health = source_health_report.get('scrape', {})
    
    total_sources = len(rss_health) + len(scrape_health)
    healthy_sources = sum(1 for s in rss_health.values() if s['healthy']) + sum(1 for s in scrape_health.values() if s['healthy'])
    
    report_lines.append(f"Källstatus: {healthy_sources}/{total_sources} källor nåbara.")
    
    # List unhealthy sources
    unhealthy = []
    for name, data in rss_health.items():
        if not data['healthy']: unhealthy.append(f"RSS: {name}")
    for name, data in scrape_health.items():
        if not data['healthy']: unhealthy.append(f"Webb: {name}")
        
    if unhealthy:
        report_lines.append("⚠️ Problem med följande källor:")
        for u in unhealthy:
            report_lines.append(f"  - {u}")
            
    # 2. Search Agent Results
    search_results = [a for a in articles if "via Google News" in a.source or "Google Alert" in a.source]
    if search_results:
        report_lines.append(f"\nSökagenten hittade {len(search_results)} artiklar via aktiv sökning.")
    else:
        report_lines.append("\nSökagenten hittade inga nya artiklar via aktiv sökning.")
        
    # 3. Total
    report_lines.append(f"\nTotalt {len(articles)} artiklar i dagens utskick.")
    
    return "\n".join(report_lines)
