import json
import re
from collections import defaultdict
from datetime import datetime
import logging

class ContentConsistencyAnalyzer:
    def __init__(self, json_file_path: str):
        self.json_file_path = json_file_path
        self.data = None
        self.inconsistencies = {
            'pricing_discrepancies': [],
            'package_details_discrepancies': [],
            'service_feature_discrepancies': [],
            'translation_mismatches': [],
            'contact_info_discrepancies': []
        }
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.load_data()
    
    def load_data(self):
        """Load JSON data from file"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            self.logger.info(f"Loaded data from {self.json_file_path} with {len(self.data)} pages")
        except Exception as e:
            self.logger.error(f"Error loading data: {e}")
            raise
    
    def detect_language(self, text: str) -> str:
        """Detect if text is English, Sinhala, or Mixed"""
        if not text or not text.strip():
            return "empty"
        
        # Count Sinhala Unicode characters (0D80-0DFF range)
        sinhala_chars = sum(1 for char in text if '\u0D80' <= char <= '\u0DFF')
        # Count English letters
        english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        
        total_alpha_chars = sinhala_chars + english_chars
        
        if total_alpha_chars == 0:
            return "no_text"
        
        sinhala_ratio = sinhala_chars / total_alpha_chars
        english_ratio = english_chars / total_alpha_chars
        
        if sinhala_ratio > 0.7:
            return "sinhala"
        elif english_ratio > 0.7:
            return "english"
        elif sinhala_ratio > 0.1 and english_ratio > 0.1:
            return "mixed"
        else:
            return "other"
    
    def extract_prices(self, text: str) -> list:
        """Extract price information from text"""
        prices = []
        
        # Price patterns
        patterns = [
            # Rs. 2500, Rs.2500, Rs 2500
            r'Rs\.?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            # LKR 2500, LKR2500
            r'LKR\.?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            # 2500/-, 2500/-
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*/-',
            # /month, per month with price
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:/month|per month|monthly)',
            # Price in Sinhala context (රු.)
            r'රු\.?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Convert price to standard format (remove commas)
                price_value = float(match.replace(',', ''))
                prices.append({
                    'value': price_value,
                    'original': match,
                    'context': self.get_price_context(text, match)
                })
        
        return prices
    
    def get_price_context(self, text: str, price: str, context_length: int = 50) -> str:
        """Get context around a price mention"""
        price_index = text.lower().find(price.lower())
        if price_index == -1:
            return ""
        
        start = max(0, price_index - context_length)
        end = min(len(text), price_index + len(price) + context_length)
        
        context = text[start:end]
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        
        return context.strip()
    
    def extract_package_details(self, text: str) -> dict:
        """Extract package/plan details from text"""
        details = {
            'speeds': [],
            'data_limits': [],
            'features': []
        }
        
        # Speed patterns (Mbps, GB/s, etc.)
        speed_patterns = [
            r'(\d+(?:\.\d+)?)\s*Mbps',
            r'(\d+(?:\.\d+)?)\s*mbps',
            r'(\d+(?:\.\d+)?)\s*MB/s',
            r'(\d+(?:\.\d+)?)\s*GB/s'
        ]
        
        for pattern in speed_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                details['speeds'].append({
                    'value': float(match),
                    'context': self.get_price_context(text, match)
                })
        
        # Data limit patterns
        data_patterns = [
            r'(\d+(?:\.\d+)?)\s*GB',
            r'(\d+(?:\.\d+)?)\s*TB',
            r'unlimited\s+data',
            r'unlimited'
        ]
        
        for pattern in data_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, str) and 'unlimited' in match.lower():
                    details['data_limits'].append({
                        'type': 'unlimited',
                        'context': self.get_price_context(text, match)
                    })
                else:
                    details['data_limits'].append({
                        'value': float(match) if match.replace('.', '').isdigit() else match,
                        'context': self.get_price_context(text, str(match))
                    })
        
        # Common features
        feature_keywords = [
            'fiber', 'fibre', 'adsl', '4g', 'lte', 'wifi', 'wi-fi',
            'peotv', 'iptv', 'telephone', 'voice', 'email', 'cloud',
            'free installation', 'free router', 'unlimited', 'fixed'
        ]
        
        text_lower = text.lower()
        for feature in feature_keywords:
            if feature in text_lower:
                details['features'].append({
                    'feature': feature,
                    'context': self.get_price_context(text, feature)
                })
        
        return details
    
    def extract_contact_info(self, text: str) -> dict:
        """Extract contact information from text"""
        contact = {
            'phone_numbers': [],
            'email_addresses': [],
            'addresses': []
        }
        
        # Phone number patterns (Sri Lankan format)
        phone_patterns = [
            r'\b(?:\+94|0094|0)\s*\d{2}\s*\d{7}\b',  # +94 11 1234567
            r'\b\d{3}-\d{7}\b',  # 011-1234567
            r'\b\d{10}\b'  # 0111234567
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                contact['phone_numbers'].append({
                    'number': match,
                    'context': self.get_price_context(text, match)
                })
        
        # Email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_matches = re.findall(email_pattern, text)
        for email in email_matches:
            contact['email_addresses'].append({
                'email': email,
                'context': self.get_price_context(text, email)
            })
        
        return contact
    
    def analyze_pricing_consistency(self):
        """Find pricing inconsistencies across pages"""
        self.logger.info("Analyzing pricing consistency...")
        
        # Group prices by product/service type
        price_groups = defaultdict(list)
        
        for url, page_data in self.data.items():
            text = page_data.get('text', '')
            title = page_data.get('title', '')
            
            # Extract prices from both text and OCR
            all_text = f"{title} {text}"
            
            # Add OCR text
            for img in page_data.get('ocr_images', []):
                ocr_text = img.get('text', '')
                if ocr_text:
                    all_text += f" {ocr_text}"
            
            prices = self.extract_prices(all_text)
            
            for price in prices:
                # Try to categorize the price based on context
                context_lower = price['context'].lower()
                category = 'unknown'
                
                if any(word in context_lower for word in ['fiber', 'fibre', 'fttx']):
                    category = 'fiber'
                elif any(word in context_lower for word in ['adsl', 'megaline']):
                    category = 'adsl'
                elif any(word in context_lower for word in ['4g', 'lte', 'mobile']):
                    category = '4g_mobile'
                elif any(word in context_lower for word in ['peotv', 'tv', 'television']):
                    category = 'tv'
                elif any(word in context_lower for word in ['package', 'plan', 'bundle']):
                    category = 'package'
                
                price_groups[category].append({
                    'url': url,
                    'price': price['value'],
                    'original': price['original'],
                    'context': price['context'],
                    'language': self.detect_language(price['context'])
                })
        
        # Find inconsistencies within each category
        for category, prices in price_groups.items():
            if len(prices) > 1:
                # Group by similar price values (within 10% range)
                price_values = [p['price'] for p in prices]
                unique_prices = []
                
                for price_info in prices:
                    price_val = price_info['price']
                    is_duplicate = False
                    
                    for existing_group in unique_prices:
                        existing_price = existing_group[0]['price']
                        # Consider prices within 10% as potentially the same service
                        if abs(price_val - existing_price) / existing_price < 0.1:
                            existing_group.append(price_info)
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        unique_prices.append([price_info])
                
                # Report significant price differences
                if len(unique_prices) > 1:
                    price_ranges = [(group[0]['price'], len(group)) for group in unique_prices]
                    price_ranges.sort()
                    
                    min_price = price_ranges[0][0]
                    max_price = price_ranges[-1][0]
                    
                    # Only report if there's a significant difference (more than 20%)
                    if (max_price - min_price) / min_price > 0.2:
                        self.inconsistencies['pricing_discrepancies'].append({
                            'category': category,
                            'price_range': f"Rs. {min_price:.0f} - Rs. {max_price:.0f}",
                            'difference_percentage': f"{((max_price - min_price) / min_price * 100):.1f}%",
                            'occurrences': [
                                {
                                    'url': group[0]['url'],
                                    'price': f"Rs. {group[0]['price']:.0f}",
                                    'context': group[0]['context'],
                                    'language': group[0]['language'],
                                    'count': len(group)
                                } for group in unique_prices
                            ]
                        })
    
    def analyze_package_consistency(self):
        """Find inconsistencies in package/plan details"""
        self.logger.info("Analyzing package details consistency...")
        
        package_details = {}
        
        for url, page_data in self.data.items():
            text = page_data.get('text', '')
            title = page_data.get('title', '')
            
            all_text = f"{title} {text}"
            
            # Add OCR text
            for img in page_data.get('ocr_images', []):
                ocr_text = img.get('text', '')
                if ocr_text:
                    all_text += f" {ocr_text}"
            
            details = self.extract_package_details(all_text)
            
            if details['speeds'] or details['data_limits'] or details['features']:
                package_details[url] = {
                    'details': details,
                    'language': self.detect_language(all_text)
                }
        
        # Find packages with same features but different details
        feature_groups = defaultdict(list)
        
        for url, data in package_details.items():
            features = [f['feature'] for f in data['details']['features']]
            feature_key = '-'.join(sorted(features))
            
            if feature_key:
                feature_groups[feature_key].append({
                    'url': url,
                    'speeds': data['details']['speeds'],
                    'data_limits': data['details']['data_limits'],
                    'language': data['language']
                })
        
        # Check for inconsistencies within feature groups
        for feature_key, packages in feature_groups.items():
            if len(packages) > 1:
                # Check speed inconsistencies
                all_speeds = []
                for pkg in packages:
                    all_speeds.extend([s['value'] for s in pkg['speeds']])
                
                if all_speeds and len(set(all_speeds)) > 1:
                    self.inconsistencies['package_details_discrepancies'].append({
                        'type': 'speed_inconsistency',
                        'feature_group': feature_key,
                        'speed_variations': list(set(all_speeds)),
                        'packages': packages
                    })
                
                # Check data limit inconsistencies
                data_limit_types = []
                for pkg in packages:
                    for limit in pkg['data_limits']:
                        if 'type' in limit:
                            data_limit_types.append(limit['type'])
                        elif 'value' in limit:
                            data_limit_types.append(str(limit['value']))
                
                if data_limit_types and len(set(data_limit_types)) > 1:
                    self.inconsistencies['package_details_discrepancies'].append({
                        'type': 'data_limit_inconsistency',
                        'feature_group': feature_key,
                        'data_variations': list(set(data_limit_types)),
                        'packages': packages
                    })
    
    def analyze_translation_consistency(self):
        """Check if English and Sinhala versions say the same thing"""
        self.logger.info("Analyzing English-Sinhala translation consistency...")
        
        # Separate pages by language
        english_pages = {}
        sinhala_pages = {}
        mixed_pages = {}
        
        for url, page_data in self.data.items():
            text = page_data.get('text', '')
            title = page_data.get('title', '')
            
            all_text = f"{title} {text}"
            
            # Add OCR text
            for img in page_data.get('ocr_images', []):
                ocr_text = img.get('text', '')
                if ocr_text:
                    all_text += f" {ocr_text}"
            
            language = self.detect_language(all_text)
            
            page_info = {
                'text': all_text,
                'prices': self.extract_prices(all_text),
                'package_details': self.extract_package_details(all_text),
                'contact_info': self.extract_contact_info(all_text)
            }
            
            if language == 'english':
                english_pages[url] = page_info
            elif language == 'sinhala':
                sinhala_pages[url] = page_info
            elif language == 'mixed':
                mixed_pages[url] = page_info
        
        # Compare similar pages between languages
        self.compare_cross_language_consistency(english_pages, sinhala_pages, 'english', 'sinhala')
        
        # Check mixed language pages for internal consistency
        for url, page_info in mixed_pages.items():
            self.check_mixed_language_consistency(url, page_info)
    
    def compare_cross_language_consistency(self, pages1, pages2, lang1, lang2):
        """Compare pages between two languages for consistency"""
        
        for url1, info1 in pages1.items():
            for url2, info2 in pages2.items():
                # Check if pages might be translations of each other
                # (simplified check based on similar URL structure or similar content structure)
                
                if self.might_be_translations(url1, url2, info1, info2):
                    # Compare prices
                    prices1 = [p['value'] for p in info1['prices']]
                    prices2 = [p['value'] for p in info2['prices']]
                    
                    if prices1 and prices2:
                        # Check if price lists are significantly different
                        if not self.price_lists_match(prices1, prices2):
                            self.inconsistencies['translation_mismatches'].append({
                                'type': 'price_mismatch_between_languages',
                                'url1': url1,
                                'url2': url2,
                                'language1': lang1,
                                'language2': lang2,
                                'prices1': prices1,
                                'prices2': prices2,
                                'difference': 'Prices differ between language versions'
                            })
                    
                    # Compare package features
                    features1 = [f['feature'] for f in info1['package_details']['features']]
                    features2 = [f['feature'] for f in info2['package_details']['features']]
                    
                    if features1 and features2:
                        # Check feature consistency
                        features1_set = set(features1)
                        features2_set = set(features2)
                        
                        if features1_set != features2_set:
                            missing_in_lang2 = features1_set - features2_set
                            missing_in_lang1 = features2_set - features1_set
                            
                            if missing_in_lang1 or missing_in_lang2:
                                self.inconsistencies['translation_mismatches'].append({
                                    'type': 'feature_mismatch_between_languages',
                                    'url1': url1,
                                    'url2': url2,
                                    'language1': lang1,
                                    'language2': lang2,
                                    'missing_in_lang1': list(missing_in_lang1),
                                    'missing_in_lang2': list(missing_in_lang2)
                                })
    
    def might_be_translations(self, url1, url2, info1, info2):
        """Simple heuristic to check if two pages might be translations"""
        # Check if URLs are similar (same path structure)
        if url1.replace('/en/', '/').replace('/si/', '/') == url2.replace('/en/', '/').replace('/si/', '/'):
            return True
        
        # Check if they have similar number of prices (indicating same products)
        if abs(len(info1['prices']) - len(info2['prices'])) <= 1 and len(info1['prices']) > 0:
            return True
        
        # Check if they have similar features
        features1 = set(f['feature'] for f in info1['package_details']['features'])
        features2 = set(f['feature'] for f in info2['package_details']['features'])
        
        if features1 and features2:
            overlap = len(features1.intersection(features2))
            total = len(features1.union(features2))
            if total > 0 and overlap / total > 0.5:  # More than 50% feature overlap
                return True
        
        return False
    
    def price_lists_match(self, prices1, prices2, tolerance=0.05):
        """Check if two price lists are essentially the same"""
        if len(prices1) != len(prices2):
            return False
        
        prices1_sorted = sorted(prices1)
        prices2_sorted = sorted(prices2)
        
        for p1, p2 in zip(prices1_sorted, prices2_sorted):
            if abs(p1 - p2) / max(p1, p2) > tolerance:  # More than 5% difference
                return False
        
        return True
    
    def check_mixed_language_consistency(self, url, page_info):
        """Check internal consistency within mixed language pages"""
        # This is a simplified check - in practice, you'd need more sophisticated analysis
        prices = page_info['prices']
        
        english_prices = [p for p in prices if self.detect_language(p['context']) == 'english']
        sinhala_prices = [p for p in prices if self.detect_language(p['context']) == 'sinhala']
        
        if english_prices and sinhala_prices:
            eng_values = [p['value'] for p in english_prices]
            sin_values = [p['value'] for p in sinhala_prices]
            
            if not self.price_lists_match(eng_values, sin_values):
                self.inconsistencies['translation_mismatches'].append({
                    'type': 'internal_language_price_mismatch',
                    'url': url,
                    'english_prices': eng_values,
                    'sinhala_prices': sin_values,
                    'issue': 'Different prices in English and Sinhala sections of the same page'
                })
    
    def analyze_contact_consistency(self):
        """Check for consistent contact information across pages"""
        self.logger.info("Analyzing contact information consistency...")
        
        all_contacts = defaultdict(list)
        
        for url, page_data in self.data.items():
            text = page_data.get('text', '')
            title = page_data.get('title', '')
            
            all_text = f"{title} {text}"
            
            # Add OCR text
            for img in page_data.get('ocr_images', []):
                ocr_text = img.get('text', '')
                if ocr_text:
                    all_text += f" {ocr_text}"
            
            contact_info = self.extract_contact_info(all_text)
            
            # Group contact info
            for phone in contact_info['phone_numbers']:
                all_contacts['phones'].append({
                    'url': url,
                    'number': phone['number'],
                    'context': phone['context']
                })
            
            for email in contact_info['email_addresses']:
                all_contacts['emails'].append({
                    'url': url,
                    'email': email['email'],
                    'context': email['context']
                })
        
        # Check for inconsistencies in contact information
        if all_contacts['phones']:
            unique_phones = set(contact['number'] for contact in all_contacts['phones'])
            if len(unique_phones) > 3:  # Too many different phone numbers
                self.inconsistencies['contact_info_discrepancies'].append({
                    'type': 'multiple_phone_numbers',
                    'count': len(unique_phones),
                    'numbers': list(unique_phones),
                    'details': all_contacts['phones']
                })
        
        if all_contacts['emails']:
            unique_emails = set(contact['email'] for contact in all_contacts['emails'])
            if len(unique_emails) > 3:  # Too many different email addresses
                self.inconsistencies['contact_info_discrepancies'].append({
                    'type': 'multiple_email_addresses',
                    'count': len(unique_emails),
                    'emails': list(unique_emails),
                    'details': all_contacts['emails']
                })
    
    def analyze_all_inconsistencies(self):
        """Run all consistency analyses"""
        self.logger.info("Starting comprehensive content consistency analysis...")
        
        self.analyze_pricing_consistency()
        self.analyze_package_consistency()
        self.analyze_translation_consistency()
        self.analyze_contact_consistency()
        
        self.logger.info("Content consistency analysis completed.")
    
    def generate_report(self):
        """Generate a focused consistency report"""
        stats = self.generate_summary_stats()
        
        report = []
        report.append("=" * 80)
        report.append("SLT WEBSITE CONTENT CONSISTENCY ANALYSIS")
        report.append("=" * 80)
        report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Source file: {self.json_file_path}")
        report.append(f"Pages analyzed: {stats['total_pages_analyzed']}")
        report.append(f"Total inconsistencies found: {stats['total_inconsistencies']}")
        report.append("")
        
        # Pricing Discrepancies
        if self.inconsistencies['pricing_discrepancies']:
            report.append("🔍 PRICING DISCREPANCIES FOUND")
            report.append("=" * 50)
            for i, issue in enumerate(self.inconsistencies['pricing_discrepancies'], 1):
                report.append(f"\n{i}. {issue['category'].upper()} PRICING INCONSISTENCY")
                report.append(f"   Price Range: {issue['price_range']}")
                report.append(f"   Difference: {issue['difference_percentage']}")
                report.append("   Found in:")
                
                for occ in issue['occurrences']:
                    report.append(f"   • {occ['url']}")
                    report.append(f"     Price: {occ['price']} ({occ['language']} content)")
                    report.append(f"     Context: {occ['context'][:100]}...")
                    report.append("")
        else:
            report.append("✅ NO PRICING DISCREPANCIES FOUND")
            report.append("")
        
        # Translation Mismatches
        if self.inconsistencies['translation_mismatches']:
            report.append("🔍 ENGLISH-SINHALA TRANSLATION MISMATCHES")
            report.append("=" * 50)
            for i, issue in enumerate(self.inconsistencies['translation_mismatches'], 1):
                report.append(f"\n{i}. {issue['type'].upper()}")
                
                if issue['type'] == 'price_mismatch_between_languages':
                    report.append(f"   {issue['language1'].title()} page: {issue['url1']}")
                    report.append(f"   {issue['language1'].title()} prices: {issue['prices1']}")
                    report.append(f"   {issue['language2'].title()} page: {issue['url2']}")
                    report.append(f"   {issue['language2'].title()} prices: {issue['prices2']}")
                
                elif issue['type'] == 'feature_mismatch_between_languages':
                    report.append(f"   {issue['language1'].title()} page: {issue['url1']}")
                    report.append(f"   {issue['language2'].title()} page: {issue['url2']}")
                    if issue.get('missing_in_lang1'):
                        report.append(f"   Missing in {issue['language1'].title()}: {issue.get('missing_in_lang1')}")
                    if issue.get('missing_in_lang2'):
                        report.append(f"   Missing in {issue['language2'].title()}: {issue.get('missing_in_lang2')}")
                
                elif issue['type'] == 'internal_language_price_mismatch':
                    report.append(f"   Page: {issue['url']}")
                    report.append(f"   English prices: {issue['english_prices']}")
                    report.append(f"   Sinhala prices: {issue['sinhala_prices']}")
                    report.append(f"   Issue: {issue['issue']}")
                
                report.append("")
        else:
            report.append("✅ NO TRANSLATION MISMATCHES FOUND")
            report.append("")
        
        # Package Details Discrepancies
        if self.inconsistencies['package_details_discrepancies']:
            report.append("🔍 PACKAGE DETAILS DISCREPANCIES")
            report.append("=" * 50)
            for i, issue in enumerate(self.inconsistencies['package_details_discrepancies'], 1):
                report.append(f"\n{i}. {issue['type'].upper()}")
                report.append(f"   Feature Group: {issue.get('feature_group', '')}")
                
                if 'speed_variations' in issue:
                    report.append(f"   Speed variations: {issue['speed_variations']}")
                if 'data_variations' in issue:
                    report.append(f"   Data limit variations: {issue['data_variations']}")
                
                report.append("   Found in packages:")
                for pkg in issue.get('packages', []):
                    speeds = [s.get('value') for s in pkg.get('speeds', [])]
                    data_limits = [
                        (d.get('type') if 'type' in d else d.get('value')) for d in pkg.get('data_limits', [])
                    ]
                    report.append(f"   • {pkg.get('url')} - speeds: {speeds}, data_limits: {data_limits}, language: {pkg.get('language')}")
                
                report.append("")
        else:
            report.append("✅ NO PACKAGE DETAILS DISCREPANCIES FOUND")
            report.append("")
        
        # Contact Info Discrepancies
        if self.inconsistencies['contact_info_discrepancies']:
            report.append("🔍 CONTACT INFORMATION DISCREPANCIES")
            report.append("=" * 50)
            for i, issue in enumerate(self.inconsistencies['contact_info_discrepancies'], 1):
                report.append(f"\n{i}. {issue.get('type', 'unknown').upper()}")
                report.append(f"   Count: {issue.get('count', '')}")
                if 'numbers' in issue:
                    report.append(f"   Numbers: {issue['numbers']}")
                if 'emails' in issue:
                    report.append(f"   Emails: {issue['emails']}")
                report.append("   Details:")
                for d in issue.get('details', []):
                    report.append(f"   • {d.get('url')} - {d.get('number') or d.get('email')} (context: {d.get('context','')[:80]})")
                report.append("")
        else:
            report.append("✅ NO CONTACT INFORMATION DISCREPANCIES FOUND")
            report.append("")
        
        # Summary and Recommendations
        report.append("📋 SUMMARY & RECOMMENDATIONS")
        report.append("=" * 50)
        
        total_issues = stats['total_inconsistencies']
        if total_issues == 0:
            report.append("🎉 EXCELLENT! No content inconsistencies found.")
            report.append("Your website content is consistent across all pages and languages.")
        else:
            report.append(f"⚠️  FOUND {total_issues} CONTENT INCONSISTENCIES")
            report.append("")
            report.append("PRIORITY ACTIONS NEEDED:")
            
            pricing_issues = len(self.inconsistencies['pricing_discrepancies'])
            translation_issues = len(self.inconsistencies['translation_mismatches'])
            package_issues = len(self.inconsistencies['package_details_discrepancies'])
            contact_issues = len(self.inconsistencies['contact_info_discrepancies'])
            
            if pricing_issues:
                report.append(f" - Fix pricing inconsistencies ({pricing_issues} issues)")
            if translation_issues:
                report.append(f" - Review translation mismatches ({translation_issues} issues)")
            if package_issues:
                report.append(f" - Harmonize package details ({package_issues} issues)")
            if contact_issues:
                report.append(f" - Consolidate contact information ({contact_issues} issues)")
        
        # Return full report text
        report_text = "\n".join(report)
        return report_text
    def save_report(self, filename: str = None):
        """Save generated report to a file (and optionally print)"""
        report_text = self.generate_report()
        if filename is None:
            filename = f"consistency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_text)
            self.logger.info(f"Report saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")
        return filename

    def generate_summary_stats(self):
        """Generate summary statistics for the report"""
        total_pages = len(self.data) if self.data else 0
        counts = {
            'pricing_discrepancies': len(self.inconsistencies['pricing_discrepancies']),
            'translation_mismatches': len(self.inconsistencies['translation_mismatches']),
            'package_details_discrepancies': len(self.inconsistencies['package_details_discrepancies']),
            'contact_info_discrepancies': len(self.inconsistencies['contact_info_discrepancies'])
        }
        total_inconsistencies = sum(counts.values())
        return {
            'total_pages_analyzed': total_pages,
            'total_inconsistencies': total_inconsistencies,
            'inconsistency_counts': counts
        }

def main():
    """Main function to run the content consistency analyzer"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python content_consistency_analyzer.py <Scrapped.json>")
        print("Example: python content_consistency_analyzer.py Scrapped.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    try:
        print("🔍 Starting SLT Content Consistency Analysis...")
        print(f"📁 Analyzing file: {json_file}")
        print("")
        
        analyzer = ContentConsistencyAnalyzer(json_file)
        analyzer.analyze_all_inconsistencies()
        
        # Generate and save report
        report_file = analyzer.save_report()
        
        if report_file:
            print("✅ ANALYSIS COMPLETED!")
            print(f"📄 Detailed report: {report_file}")
            print("")
            
            # Print key findings to console
            stats = analyzer.generate_summary_stats()
            total_issues = stats['total_inconsistencies']
            
            print("🎯 KEY FINDINGS:")
            if total_issues == 0:
                print("   🎉 No content inconsistencies found! Your website is consistent.")
            else:
                print(f"   ⚠️  Found {total_issues} content inconsistencies:")
                
                counts = stats['inconsistency_counts']
                if counts['pricing_discrepancies'] > 0:
                    print(f"   💰 Pricing discrepancies: {counts['pricing_discrepancies']}")
                if counts['translation_mismatches'] > 0:
                    print(f"   🌐 Translation mismatches: {counts['translation_mismatches']}")
                if counts['package_details_discrepancies'] > 0:
                    print(f"   📦 Package inconsistencies: {counts['package_details_discrepancies']}")
                if counts['contact_info_discrepancies'] > 0:
                    print(f"   📞 Contact info issues: {counts['contact_info_discrepancies']}")
                
                print("")
                if counts['pricing_discrepancies'] > 0 or counts['translation_mismatches'] > 0:
                    print("🚨 HIGH PRIORITY ISSUES FOUND!")
                    print("   → Check the detailed report for specific problems")
                    print("   → Fix pricing and translation issues immediately")
            
            print(f"\n📖 Read the full report: {report_file}")
        else:
            print("❌ Error generating report.")
    
    except FileNotFoundError:
        print(f"❌ Error: Could not find file '{json_file}'")
        print("   Make sure the file path is correct and the file exists.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON format in '{json_file}'")
        print(f"   JSON Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()