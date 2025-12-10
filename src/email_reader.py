import imaplib
import email
import logging
from email.header import decode_header
from datetime import datetime
from typing import List
from .models import Article
import re

logger = logging.getLogger(__name__)

def decode_str(s):
    """Decode email header string."""
    if not s:
        return ""
    decoded_list = decode_header(s)
    decoded_str = ""
    for content, encoding in decoded_list:
        if isinstance(content, bytes):
            if encoding:
                try:
                    decoded_str += content.decode(encoding)
                except LookupError:
                    decoded_str += content.decode('utf-8', errors='ignore')
            else:
                decoded_str += content.decode('utf-8', errors='ignore')
        else:
            decoded_str += str(content)
    return decoded_str

def extract_links_from_html(html_content):
    """Extract Google Alerts links from HTML content."""
    # This is a simplified regex for Google Alerts. 
    # Google Alerts usually have a specific structure like <a href="https://www.google.com/url?q=...">
    links = []
    # Regex to find google alert redirect links
    google_link_pattern = re.compile(r'href="https://www.google.com/url\?rct=j&amp;sa=t&amp;url=(.*?)(?:&amp;|&")')
    
    matches = google_link_pattern.findall(html_content)
    for match in matches:
        # Decode URL encoding if necessary
        from urllib.parse import unquote
        url = unquote(match)
        links.append(url)
    
    return links

def read_emails(config) -> List[Article]:
    """Read emails from configured IMAP account (Google Alerts)."""
    articles = []
    email_config = config.get('email', {})
    
    if not email_config.get('imap_enabled'):
        return []

    imap_server = email_config.get('imap_server')
    imap_user = email_config.get('imap_user')
    imap_pass = email_config.get('imap_password')
    
    if not all([imap_server, imap_user, imap_pass]):
        logger.warning("IMAP configuration incomplete.")
        return []

    try:
        logger.info(f"Connecting to IMAP server: {imap_server}")
        mail = imaplib.IMAP4_SSL(imap_server, email_config.get('imap_port', 993))
        mail.login(imap_user, imap_pass)
        
        folder = email_config.get('imap_folder', 'Inbox')
        mail.select(folder)
        
        # Search for unread emails from Google Alerts
        # Adjust search criteria as needed
        status, messages = mail.search(None, '(UNSEEN FROM "googlealerts-noreply@google.com")')
        
        if status != 'OK':
            logger.warning("No messages found or error searching.")
            return []
            
        email_ids = messages[0].split()
        logger.info(f"Found {len(email_ids)} new Google Alerts emails.")
        
        for e_id in email_ids[:5]: # Process max 5 emails
            status, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject = decode_str(msg["Subject"])
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/html":
                                body = part.get_payload(decode=True).decode()
                                links = extract_links_from_html(body)
                                
                                for link in links:
                                    # Create article from link
                                    # Note: We lack title/summary here without visiting the link
                                    # In a real app, we might want to visit the link to get metadata
                                    article = Article(
                                        title=f"Google Alert: {subject}", # Placeholder title
                                        url=link,
                                        source="Google Alerts",
                                        published_date=datetime.now().astimezone(),
                                        summary=f"Found via Google Alert: {subject}",
                                        content_type="article"
                                    )
                                    articles.append(article)
    
        mail.close()
        mail.logout()
        
    except Exception as e:
        logger.error(f"IMAP Error: {e}")
        
    logger.info(f"Collected {len(articles)} articles from emails.")
    return articles
