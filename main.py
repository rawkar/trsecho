import argparse
import logging
import sys
import yaml
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.collector import collect_rss
from src.scraper import scrape_web
from src.search_agent import run_search_agent
from src.email_reader import read_emails
from src.emailer import generate_and_send_email
from src.deduplicator import deduplicate_articles
from src.categorizer import categorize_articles
from src.enricher import enrich_articles
from src.source_validator import check_sources_health

def load_config(config_path='config.yaml'):
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        logging.error(f"Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logging.error(f"Error parsing config file: {e}")
            sys.exit(1)

def setup_logging(log_level):
    """Setup logging configuration."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/app.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def main():
    parser = argparse.ArgumentParser(description="TRS Omvärldsbevakning - Intelligent Media Monitoring")
    parser.add_argument('--preview', action='store_true', help="Run in preview mode (no email sent)")
    parser.add_argument('--test', action='store_true', help="Run in test mode (output to terminal)")
    parser.add_argument('--debug', action='store_true', help="Enable debug logging")
    parser.add_argument('--source', choices=['rss', 'scrape', 'search', 'email', 'all'], default='all', help="Limit to specific source type")
    
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    
    log_level = 'DEBUG' if args.debug else config['app'].get('log_level', 'INFO')
    setup_logging(log_level)
    
    logging.info(f"Starting TRS Omvärldsbevakning v{config['app']['version']}")
    logging.info(f"Mode: {'Preview' if args.preview else 'Test' if args.test else 'Production'}")
    
    try:
        articles = []
        
        # 0. Check Source Health
        logging.info("Checking source health...")
        source_health_report = check_sources_health(config)
        
        # 1. Data Collection
        if args.source in ['rss', 'all']:
            logging.info("Starting RSS collection...")
            articles.extend(collect_rss(config))
            
        if args.source in ['scrape', 'all']:
            logging.info("Starting Web Scraping...")
            articles.extend(scrape_web(config))
            
        if args.source in ['email', 'all']:
            logging.info("Checking Email (Google Alerts)...")
            articles.extend(read_emails(config))
            
        if args.source in ['search', 'all']:
            logging.info("Starting Intelligent Search Agent...")
            articles.extend(run_search_agent(config))
            
        # 2. Processing
        logging.info(f"Collected {len(articles)} raw articles. Processing...")
        
        # Enrich (Type, Source Name)
        articles = enrich_articles(articles, config)
        
        # Deduplicate
        articles = deduplicate_articles(articles, config)
        
        # Categorize
        categorized_data = categorize_articles(articles, config)
        
        # 3. Output
        if args.test:
            logging.info("Test mode: Displaying results in terminal")
            for cat, items in categorized_data.items():
                if items:
                    print(f"\n--- {cat} ({len(items)}) ---")
                    for item in items:
                        print(f"[{item.content_type.upper()}] {item.title} ({item.source})")
                        print(f"   {item.url}")
        else:
            logging.info("Generating output...")
            generate_and_send_email(categorized_data, articles, source_health_report, config, preview_only=args.preview)
            
        logging.info("Run completed successfully.")
        
    except Exception as e:
        logging.exception("An unexpected error occurred:")
        sys.exit(1)

if __name__ == "__main__":
    main()
