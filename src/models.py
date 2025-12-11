from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class Article:
    title: str
    url: str
    source: str
    published_date: datetime
    summary: str
    content_type: str = "article"  # article, video, pdf, press_release
    category: Optional[str] = None
    relevance_score: float = 0.0
    original_html: Optional[str] = None
    body_text: str = "" # Full text content for analysis
    organization: Optional[str] = None
    domain: Optional[str] = None
    estimated_read_time: int = 0
    found_via: Optional[str] = None
    
    def to_dict(self):
        return {
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'published_date': self.published_date.isoformat(),
            'summary': self.summary,
            'content_type': self.content_type,
            'category': self.category,
            'relevance_score': self.relevance_score,
            'organization': self.organization,
            'domain': self.domain,
            'estimated_read_time': self.estimated_read_time
        }
