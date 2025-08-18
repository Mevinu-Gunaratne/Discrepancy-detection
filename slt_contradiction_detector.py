#!/usr/bin/env python3
"""
SLT.lk Website Contradiction Detector

This script crawls the entire SLT.lk website to find contradictions in content,
including banners and differences between Sinhala and English versions.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin, urlparse, parse_qs
from collections import defaultdict, Counter
import json
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple, Optional
import difflib
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from datetime import datetime
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('slt_crawler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class PageContent:
    url: str
    title: str
    content: str
    banners: List[str]
    language: str
    metadata: Dict[str, str]
    images: List[str]
    links: List[str]
    prices: List[str]
    contact_info: List[str]
    services: List[str]

@dataclass
class Contradiction:
    type: str
    page1: str
    page2: str
    content1: str
    content2: str
    severity: str
    description: str

class SLTWebsiteCrawler:
    def __init__(self):
        self.base_url = "https://www.slt.lk"
        self.visited_urls = set()
        self.pages_content = []
        self.contradictions = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Language detection patterns
        self.sinhala_pattern = re.compile(r'[\u0D80-\u0DFF]+')
        self.english_pattern = re.compile(r'[a-zA-Z]+')
        
        # Content extraction patterns
        self.price_pattern = re.compile(r'Rs\.?\s*\d+(?:,\d{3})*(?:\.\d{2})?|\d+(?:,\d{3})*(?:\.\d{2})?\s*LKR', re.IGNORECASE)
        self.phone_pattern = re.compile(r'\b(?:\+94|0)(?:11|21|23|24|25|26|27|31|32|33|34|35|36|37|38|41|45|47|51|52|54|55|57|63|65|66|67|81|91)\d{7}\b')
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
    def get_page_content(self, url: str) -> Optional[PageContent]:
        """Extract content from a single page"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract basic information
            title = soup.find('title').get_text().strip() if soup.find('title') else ""
            
            # Extract main content
            content_areas = soup.find_all(['div', 'section', 'article', 'main'])
            content = ' '.join([area.get_text().strip() for area in content_areas])
            
            # Extract banners (common banner selectors)
            banner_selectors = [
                '.banner', '.hero', '.slider', '.carousel', 
                '[class*="banner"]', '[class*="hero"]', '[class*="slider"]',
                '.promo', '.announcement', '.alert'
            ]
            banners = []
            for selector in banner_selectors:
                banner_elements = soup.select(selector)
                banners.extend([banner.get_text().strip() for banner in banner_elements if banner.get_text().strip()])
            
            # Detect language
            sinhala_chars = len(self.sinhala_pattern.findall(content))
            english_chars = len(self.english_pattern.findall(content))
            language = 'sinhala' if sinhala_chars > english_chars else 'english' if english_chars > 0 else 'unknown'
            
            # Extract metadata
            metadata = {}
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                if meta.get('name') and meta.get('content'):
                    metadata[meta.get('name')] = meta.get('content')
            
            # Extract images
            images = [img.get('src') for img in soup.find_all('img') if img.get('src')]
            
            # Extract links
            links = [link.get('href') for link in soup.find_all('a') if link.get('href')]
            
            # Extract prices
            prices = self.price_pattern.findall(content)
            
            # Extract contact information
            phones = self.phone_pattern.findall(content)
            emails = self.email_pattern.findall(content)
            contact_info = phones + emails
            
            # Extract service information (common service keywords)
            service_keywords = [
                'broadband', 'internet', 'mobile', 'phone', 'landline', 'fiber',
                'package', 'plan', 'subscription', 'service', 'connection'
            ]
            services = []
            for keyword in service_keywords:
                matches = re.findall(rf'\b{keyword}[^.]*\.', content, re.IGNORECASE)
                services.extend(matches)
            
            return PageContent(
                url=url,
                title=title,
                content=content,
                banners=banners,
                language=language,
                metadata=metadata,
                images=images,
                links=links,
                prices=prices,
                contact_info=contact_info,
                services=services
            )
            
        except Exception as e:
            logger.error(f"Error crawling {url}: {str(e)}")
            return None
    
    def discover_urls(self, start_url: str) -> Set[str]:
        """Discover all URLs on the website"""
        urls_to_visit = {start_url}
        discovered_urls = set()
        
        while urls_to_visit:
            current_url = urls_to_visit.pop()
            
            if current_url in discovered_urls or not self.is_slt_url(current_url):
                continue
                
            discovered_urls.add(current_url)
            logger.info(f"Discovering URLs from: {current_url}")
            
            try:
                response = self.session.get(current_url, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all links
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    full_url = urljoin(current_url, href)
                    
                    if self.is_slt_url(full_url) and full_url not in discovered_urls:
                        urls_to_visit.add(full_url)
                        
                time.sleep(0.5)  # Be respectful to the server
                
            except Exception as e:
                logger.error(f"Error discovering URLs from {current_url}: {str(e)}")
        
        return discovered_urls
    
    def is_slt_url(self, url: str) -> bool:
        """Check if URL belongs to SLT domain"""
        parsed = urlparse(url)
        return parsed.netloc in ['www.slt.lk', 'slt.lk'] and not any(
            ext in url.lower() for ext in ['.pdf', '.jpg', '.png', '.gif', '.css', '.js']
        )
    
    def crawl_website(self):
        """Main crawling function"""
        logger.info("Starting SLT website crawl...")
        
        # Discover all URLs
        all_urls = self.discover_urls(self.base_url)
        logger.info(f"Discovered {len(all_urls)} URLs")
        
        # Crawl pages concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(self.get_page_content, url): url for url in all_urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    page_content = future.result()
                    if page_content:
                        self.pages_content.append(page_content)
                        logger.info(f"Crawled: {url}")
                except Exception as e:
                    logger.error(f"Error processing {url}: {str(e)}")
                
                time.sleep(0.1)  # Small delay between requests
    
    def find_contradictions(self):
        """Analyze content for contradictions"""
        logger.info("Analyzing content for contradictions...")
        
        # Group pages by language
        english_pages = [p for p in self.pages_content if p.language == 'english']
        sinhala_pages = [p for p in self.pages_content if p.language == 'sinhala']
        
        # Find price contradictions
        self._find_price_contradictions()
        
        # Find service description contradictions
        self._find_service_contradictions()
        
        # Find contact information contradictions
        self._find_contact_contradictions()
        
        # Find banner contradictions
        self._find_banner_contradictions()
        
        # Find language version differences
        self._find_language_version_differences()
        
        # Find title contradictions
        self._find_title_contradictions()
        
        logger.info(f"Found {len(self.contradictions)} potential contradictions")
    
    def _find_price_contradictions(self):
        """Find contradictions in pricing information"""
        price_mentions = defaultdict(list)
        
        for page in self.pages_content:
            for price in page.prices:
                # Extract service context around price
                content_lower = page.content.lower()
                price_index = content_lower.find(price.lower())
                if price_index != -1:
                    start = max(0, price_index - 100)
                    end = min(len(content_lower), price_index + 100)
                    context = page.content[start:end]
                    
                    price_mentions[price].append((page.url, context))
        
        # Check for same prices with different contexts
        for price, mentions in price_mentions.items():
            if len(mentions) > 1:
                contexts = [mention[1] for mention in mentions]
                for i in range(len(contexts)):
                    for j in range(i + 1, len(contexts)):
                        similarity = difflib.SequenceMatcher(None, contexts[i], contexts[j]).ratio()
                        if similarity < 0.7:  # Different contexts for same price
                            self.contradictions.append(Contradiction(
                                type="price_contradiction",
                                page1=mentions[i][0],
                                page2=mentions[j][0],
                                content1=contexts[i],
                                content2=contexts[j],
                                severity="medium",
                                description=f"Same price ({price}) mentioned with different contexts"
                            ))
    
    def _find_service_contradictions(self):
        """Find contradictions in service descriptions"""
        service_descriptions = defaultdict(list)
        
        for page in self.pages_content:
            for service in page.services:
                service_key = re.sub(r'\b(the|a|an)\b', '', service.lower()).strip()
                service_descriptions[service_key].append((page.url, service))
        
        # Check for contradictory service descriptions
        for service_key, descriptions in service_descriptions.items():
            if len(descriptions) > 1:
                contents = [desc[1] for desc in descriptions]
                for i in range(len(contents)):
                    for j in range(i + 1, len(contents)):
                        similarity = difflib.SequenceMatcher(None, contents[i], contents[j]).ratio()
                        if similarity < 0.5 and len(contents[i]) > 50 and len(contents[j]) > 50:
                            self.contradictions.append(Contradiction(
                                type="service_contradiction",
                                page1=descriptions[i][0],
                                page2=descriptions[j][0],
                                content1=contents[i],
                                content2=contents[j],
                                severity="high",
                                description=f"Contradictory service descriptions for similar services"
                            ))
    
    def _find_contact_contradictions(self):
        """Find contradictions in contact information"""
        all_contacts = []
        for page in self.pages_content:
            for contact in page.contact_info:
                all_contacts.append((page.url, contact))
        
        # Group similar contact types
        phone_contacts = [(url, contact) for url, contact in all_contacts if self.phone_pattern.match(contact)]
        email_contacts = [(url, contact) for url, contact in all_contacts if self.email_pattern.match(contact)]
        
        # Check for different contact info for same service
        contact_counter = Counter([contact for _, contact in all_contacts])
        inconsistent_contacts = [contact for contact, count in contact_counter.items() if count == 1]
        
        if len(inconsistent_contacts) > 5:  # Many unique contacts might indicate inconsistency
            self.contradictions.append(Contradiction(
                type="contact_inconsistency",
                page1="multiple",
                page2="multiple",
                content1=str(inconsistent_contacts[:5]),
                content2="",
                severity="medium",
                description=f"Found {len(inconsistent_contacts)} unique contact details across pages"
            ))
    
    def _find_banner_contradictions(self):
        """Find contradictions in banner messages"""
        banner_messages = []
        for page in self.pages_content:
            for banner in page.banners:
                if len(banner) > 20:  # Only consider substantial banners
                    banner_messages.append((page.url, banner))
        
        # Look for contradictory promotional messages
        for i in range(len(banner_messages)):
            for j in range(i + 1, len(banner_messages)):
                url1, banner1 = banner_messages[i]
                url2, banner2 = banner_messages[j]
                
                # Check for contradictory promotional claims
                promotional_words = ['best', 'fastest', 'cheapest', 'lowest', 'highest', 'maximum', 'minimum']
                banner1_lower = banner1.lower()
                banner2_lower = banner2.lower()
                
                for word in promotional_words:
                    if word in banner1_lower and word in banner2_lower:
                        if banner1_lower != banner2_lower:  # Different banners with same superlative
                            similarity = difflib.SequenceMatcher(None, banner1, banner2).ratio()
                            if similarity < 0.8:
                                self.contradictions.append(Contradiction(
                                    type="banner_contradiction",
                                    page1=url1,
                                    page2=url2,
                                    content1=banner1,
                                    content2=banner2,
                                    severity="medium",
                                    description=f"Contradictory promotional claims in banners"
                                ))
    
    def _find_language_version_differences(self):
        """Find differences between Sinhala and English versions"""
        english_pages = [p for p in self.pages_content if p.language == 'english']
        sinhala_pages = [p for p in self.pages_content if p.language == 'sinhala']
        
        # Try to match pages by URL structure or title similarity
        for eng_page in english_pages:
            for sin_page in sinhala_pages:
                # Check if pages might be translations of each other
                url_similarity = difflib.SequenceMatcher(None, eng_page.url, sin_page.url).ratio()
                
                if url_similarity > 0.8:  # Likely same page in different languages
                    # Compare prices
                    if set(eng_page.prices) != set(sin_page.prices):
                        self.contradictions.append(Contradiction(
                            type="language_price_difference",
                            page1=eng_page.url,
                            page2=sin_page.url,
                            content1=str(eng_page.prices),
                            content2=str(sin_page.prices),
                            severity="high",
                            description="Different prices in English and Sinhala versions"
                        ))
                    
                    # Compare contact information
                    if set(eng_page.contact_info) != set(sin_page.contact_info):
                        self.contradictions.append(Contradiction(
                            type="language_contact_difference",
                            page1=eng_page.url,
                            page2=sin_page.url,
                            content1=str(eng_page.contact_info),
                            content2=str(sin_page.contact_info),
                            severity="medium",
                            description="Different contact information in language versions"
                        ))
    
    def _find_title_contradictions(self):
        """Find contradictions in page titles"""
        title_groups = defaultdict(list)
        
        for page in self.pages_content:
            # Group by similar titles
            title_words = set(page.title.lower().split())
            for other_page in self.pages_content:
                if page.url != other_page.url:
                    other_title_words = set(other_page.title.lower().split())
                    common_words = title_words.intersection(other_title_words)
                    if len(common_words) >= 2:  # At least 2 common words
                        title_key = ' '.join(sorted(common_words))
                        title_groups[title_key].append(page)
        
        # Check for contradictory information in similarly titled pages
        for title_key, pages in title_groups.items():
            if len(pages) > 1:
                for i in range(len(pages)):
                    for j in range(i + 1, len(pages)):
                        page1, page2 = pages[i], pages[j]
                        
                        # Compare key information
                        if set(page1.prices) != set(page2.prices) and page1.prices and page2.prices:
                            self.contradictions.append(Contradiction(
                                type="similar_title_price_contradiction",
                                page1=page1.url,
                                page2=page2.url,
                                content1=f"Prices: {page1.prices}",
                                content2=f"Prices: {page2.prices}",
                                severity="high",
                                description=f"Different prices on similarly titled pages: '{title_key}'"
                            ))
    
    def generate_report(self) -> Dict:
        """Generate comprehensive report"""
        report = {
            'crawl_summary': {
                'total_pages': len(self.pages_content),
                'english_pages': len([p for p in self.pages_content if p.language == 'english']),
                'sinhala_pages': len([p for p in self.pages_content if p.language == 'sinhala']),
                'total_contradictions': len(self.contradictions),
                'crawl_timestamp': datetime.now().isoformat()
            },
            'contradictions_by_type': {
                contradiction_type: len([c for c in self.contradictions if c.type == contradiction_type])
                for contradiction_type in set([c.type for c in self.contradictions])
            },
            'contradictions_by_severity': {
                severity: len([c for c in self.contradictions if c.severity == severity])
                for severity in set([c.severity for c in self.contradictions])
            },
            'detailed_contradictions': [
                {
                    'type': c.type,
                    'severity': c.severity,
                    'description': c.description,
                    'page1': c.page1,
                    'page2': c.page2,
                    'content1': c.content1[:200] + '...' if len(c.content1) > 200 else c.content1,
                    'content2': c.content2[:200] + '...' if len(c.content2) > 200 else c.content2
                }
                for c in self.contradictions
            ],
            'pages_analyzed': [
                {
                    'url': p.url,
                    'title': p.title,
                    'language': p.language,
                    'banners_count': len(p.banners),
                    'prices_found': len(p.prices),
                    'contact_info_count': len(p.contact_info)
                }
                for p in self.pages_content
            ]
        }
        return report
    
    def save_report(self, filename: str = None):
        """Save the analysis report"""
        if filename is None:
            filename = f"slt_contradiction_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = self.generate_report()
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Report saved to {filename}")
        return filename

def main():
    """Main execution function"""
    crawler = SLTWebsiteCrawler()
    
    try:
        # Crawl the website
        crawler.crawl_website()
        
        # Find contradictions
        crawler.find_contradictions()
        
        # Generate and save report
        report_file = crawler.save_report()
        
        # Print summary
        report = crawler.generate_report()
        print(f"\n=== SLT.lk Contradiction Analysis Complete ===")
        print(f"Total pages analyzed: {report['crawl_summary']['total_pages']}")
        print(f"English pages: {report['crawl_summary']['english_pages']}")
        print(f"Sinhala pages: {report['crawl_summary']['sinhala_pages']}")
        print(f"Total contradictions found: {report['crawl_summary']['total_contradictions']}")
        print(f"Report saved to: {report_file}")
        
        if report['crawl_summary']['total_contradictions'] > 0:
            print(f"\nContradictions by type:")
            for c_type, count in report['contradictions_by_type'].items():
                print(f"  {c_type}: {count}")
        
    except KeyboardInterrupt:
        logger.info("Crawling interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()