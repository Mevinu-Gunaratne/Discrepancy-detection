import json
import re
from difflib import SequenceMatcher
from collections import defaultdict, Counter
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any
import unicodedata

class DiscrepancyAnalyzer:
    def __init__(self, json_file_path: str):
        self.json_file_path = json_file_path
        self.data = None
        self.discrepancies = {
            'english_content': [],
            'english_sinhala': [],
            'sinhala_sinhala': [],
            'banner_text': [],
            'missing_translations': [],
            'inconsistent_terminology': [],
            'formatting_issues': []
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
            self.logger.info(f"Loaded data from {self.json_file_path}")
        except Exception as e:
            self.logger.error(f"Error loading data: {e}")
            raise
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Normalize Unicode characters
        text = unicodedata.normalize('NFKC', text)
        
        # Convert to lowercase for comparison
        text = text.lower()
        
        return text
    
    def similarity_score(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)
        
        if not norm1 and not norm2:
            return 1.0
        if not norm1 or not norm2:
            return 0.0
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def extract_english_text(self, page_data: Dict) -> Dict[str, str]:
        """Extract all English text from a page"""
        english_content = {
            'title': '',
            'headings': [],
            'paragraphs': [],
            'links': [],
            'buttons': [],
            'banner_ocr': []
        }
        
        # Extract text content based on language detection
        text_content = page_data.get('text_content', {})
        languages = page_data.get('languages', {})
        
        # Title
        if languages.get('title') == 'english':
            english_content['title'] = text_content.get('title', '')
        
        # Headings
        headings = text_content.get('headings', [])
        heading_langs = languages.get('headings', [])
        for i, heading in enumerate(headings):
            if i < len(heading_langs) and heading_langs[i] == 'english':
                english_content['headings'].append(heading.get('text', ''))
        
        # Paragraphs
        paragraphs = text_content.get('paragraphs', [])
        para_langs = languages.get('paragraphs', [])
        for i, para in enumerate(paragraphs):
            if i < len(para_langs) and para_langs[i] == 'english':
                english_content['paragraphs'].append(para)
        
        # Links
        links = text_content.get('links', [])
        link_langs = languages.get('links', [])
        for i, link in enumerate(links):
            if i < len(link_langs) and link_langs[i] == 'english':
                english_content['links'].append(link.get('text', ''))
        
        # Buttons
        buttons = text_content.get('buttons', [])
        button_langs = languages.get('buttons', [])
        for i, button in enumerate(buttons):
            if i < len(button_langs) and button_langs[i] == 'english':
                english_content['buttons'].append(button)
        
        # Banner OCR text (English)
        for banner in page_data.get('banner_data', []):
            ocr_text = banner.get('ocr_text', '')
            if self.detect_language(ocr_text) == 'english':
                english_content['banner_ocr'].append(ocr_text)
        
        return english_content
    
    def extract_sinhala_text(self, page_data: Dict) -> Dict[str, str]:
        """Extract all Sinhala text from a page"""
        sinhala_content = {
            'title': '',
            'headings': [],
            'paragraphs': [],
            'links': [],
            'buttons': [],
            'banner_ocr': []
        }
        
        text_content = page_data.get('text_content', {})
        languages = page_data.get('languages', {})
        
        # Title
        if languages.get('title') == 'sinhala':
            sinhala_content['title'] = text_content.get('title', '')
        
        # Headings
        headings = text_content.get('headings', [])
        heading_langs = languages.get('headings', [])
        for i, heading in enumerate(headings):
            if i < len(heading_langs) and heading_langs[i] == 'sinhala':
                sinhala_content['headings'].append(heading.get('text', ''))
        
        # Paragraphs
        paragraphs = text_content.get('paragraphs', [])
        para_langs = languages.get('paragraphs', [])
        for i, para in enumerate(paragraphs):
            if i < len(para_langs) and para_langs[i] == 'sinhala':
                sinhala_content['paragraphs'].append(para)
        
        # Links
        links = text_content.get('links', [])
        link_langs = languages.get('links', [])
        for i, link in enumerate(links):
            if i < len(link_langs) and link_langs[i] == 'sinhala':
                sinhala_content['links'].append(link.get('text', ''))
        
        # Buttons
        buttons = text_content.get('buttons', [])
        button_langs = languages.get('buttons', [])
        for i, button in enumerate(buttons):
            if i < len(button_langs) and button_langs[i] == 'sinhala':
                sinhala_content['buttons'].append(button)
        
        # Banner OCR text (Sinhala)
        for banner in page_data.get('banner_data', []):
            ocr_text = banner.get('ocr_text', '')
            if self.detect_language(ocr_text) == 'sinhala':
                sinhala_content['banner_ocr'].append(ocr_text)
        
        return sinhala_content
    
    def detect_language(self, text: str) -> str:
        """Detect language of text"""
        if not text:
            return "unknown"
        
        sinhala_chars = sum(1 for char in text if '\u0D80' <= char <= '\u0DFF')
        english_chars = sum(1 for char in text if char.isalpha() and char.isascii())
        
        total_chars = len(text.replace(' ', ''))
        
        if total_chars == 0:
            return "unknown"
        
        sinhala_ratio = sinhala_chars / total_chars
        english_ratio = english_chars / total_chars
        
        if sinhala_ratio > 0.1:
            return "sinhala" if sinhala_ratio > english_ratio else "mixed"
        elif english_ratio > 0.5:
            return "english"
        else:
            return "mixed"
    
    def find_english_content_discrepancies(self):
        """Find discrepancies within English content across pages"""
        self.logger.info("Analyzing English content discrepancies...")
        
        english_terms = defaultdict(set)
        
        # Collect all English terms across pages
        for page in self.data.get('pages', []):
            english_content = self.extract_english_text(page)
            url = page.get('url', '')
            
            for section, content in english_content.items():
                if isinstance(content, list):
                    for item in content:
                        if item.strip():
                            english_terms[item.strip().lower()].add((url, section, item))
                elif content.strip():
                    english_terms[content.strip().lower()].add((url, section, content))
        
        # Find terms that appear with variations
        for term_key, occurrences in english_terms.items():
            if len(occurrences) > 1:
                # Check if all occurrences are identical
                unique_texts = set(occ[2] for occ in occurrences)
                if len(unique_texts) > 1:
                    self.discrepancies['english_content'].append({
                        'type': 'inconsistent_english_term',
                        'term': term_key,
                        'variations': list(unique_texts),
                        'occurrences': [{'url': occ[0], 'section': occ[1], 'text': occ[2]} 
                                      for occ in occurrences]
                    })
    
    def find_translation_discrepancies(self):
        """Find discrepancies between English and Sinhala content"""
        self.logger.info("Analyzing English-Sinhala translation discrepancies...")
        
        pages = self.data.get('pages', [])
        
        for i, page1 in enumerate(pages):
            english_content1 = self.extract_english_text(page1)
            sinhala_content1 = self.extract_sinhala_text(page1)
            
            # Check if page has both English and Sinhala content
            has_english = any(content for content in english_content1.values() if content)
            has_sinhala = any(content for content in sinhala_content1.values() if content)
            
            if has_english and not has_sinhala:
                self.discrepancies['missing_translations'].append({
                    'type': 'missing_sinhala_translation',
                    'url': page1.get('url'),
                    'english_content': english_content1
                })
            elif has_sinhala and not has_english:
                self.discrepancies['missing_translations'].append({
                    'type': 'missing_english_translation',
                    'url': page1.get('url'),
                    'sinhala_content': sinhala_content1
                })
            
            # Compare similar pages for translation consistency
            for j, page2 in enumerate(pages[i+1:], i+1):
                if self.pages_are_similar(page1, page2):
                    english_content2 = self.extract_english_text(page2)
                    sinhala_content2 = self.extract_sinhala_text(page2)
                    
                    # Check for translation discrepancies
                    self.compare_translations(page1, page2, english_content1, 
                                           sinhala_content1, english_content2, sinhala_content2)
    
    def find_sinhala_content_discrepancies(self):
        """Find discrepancies within Sinhala content across pages"""
        self.logger.info("Analyzing Sinhala content discrepancies...")
        
        sinhala_terms = defaultdict(set)
        
        # Collect all Sinhala terms across pages
        for page in self.data.get('pages', []):
            sinhala_content = self.extract_sinhala_text(page)
            url = page.get('url', '')
            
            for section, content in sinhala_content.items():
                if isinstance(content, list):
                    for item in content:
                        if item.strip():
                            normalized = self.normalize_text(item)
                            sinhala_terms[normalized].add((url, section, item))
                elif content.strip():
                    normalized = self.normalize_text(content)
                    sinhala_terms[normalized].add((url, section, content))
        
        # Find terms that appear with variations
        for term_key, occurrences in sinhala_terms.items():
            if len(occurrences) > 1:
                unique_texts = set(occ[2] for occ in occurrences)
                if len(unique_texts) > 1:
                    self.discrepancies['sinhala_sinhala'].append({
                        'type': 'inconsistent_sinhala_term',
                        'term': term_key,
                        'variations': list(unique_texts),
                        'occurrences': [{'url': occ[0], 'section': occ[1], 'text': occ[2]} 
                                      for occ in occurrences]
                    })
    
    def analyze_banner_discrepancies(self):
        """Analyze discrepancies in banner text"""
        self.logger.info("Analyzing banner text discrepancies...")
        
        banner_texts = defaultdict(list)
        
        for page in self.data.get('pages', []):
            url = page.get('url', '')
            for banner in page.get('banner_data', []):
                if banner.get('is_banner', False):
                    ocr_text = banner.get('ocr_text', '').strip()
                    if ocr_text:
                        lang = self.detect_language(ocr_text)
                        banner_texts[self.normalize_text(ocr_text)].append({
                            'url': url,
                            'text': ocr_text,
                            'language': lang,
                            'banner_src': banner.get('src', '')
                        })
        
        # Find banner text inconsistencies
        for normalized_text, banners in banner_texts.items():
            if len(banners) > 1:
                unique_texts = set(b['text'] for b in banners)
                if len(unique_texts) > 1:
                    self.discrepancies['banner_text'].append({
                        'type': 'inconsistent_banner_text',
                        'normalized': normalized_text,
                        'variations': list(unique_texts),
                        'occurrences': banners
                    })
    
    def find_terminology_inconsistencies(self):
        """Find inconsistent terminology across the site"""
        self.logger.info("Analyzing terminology inconsistencies...")
        
        # Common terms that should be consistent
        common_terms = ['internet', 'broadband', 'package', 'plan', 'service', 'customer', 
                       'support', 'contact', 'home', 'business', 'mobile', 'fiber']
        
        term_variations = defaultdict(set)
        
        for page in self.data.get('pages', []):
            url = page.get('url', '')
            text_content = page.get('text_content', {})
            
            all_text = []
            for section, content in text_content.items():
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            all_text.append(item.get('text', ''))
                        else:
                            all_text.append(str(item))
                else:
                    all_text.append(str(content))
            
            combined_text = ' '.join(all_text).lower()
            
            for term in common_terms:
                # Find all occurrences of the term with context
                pattern = rf'\b\w*{term}\w*\b'
                matches = re.findall(pattern, combined_text)
                for match in matches:
                    term_variations[term].add((match, url))
        
        # Report inconsistent terminology
        for base_term, variations in term_variations.items():
            unique_forms = set(var[0] for var in variations)
            if len(unique_forms) > 1:
                self.discrepancies['inconsistent_terminology'].append({
                    'base_term': base_term,
                    'variations': list(unique_forms),
                    'occurrences': [{'form': var[0], 'url': var[1]} for var in variations]
                })
    
    def pages_are_similar(self, page1: Dict, page2: Dict) -> bool:
        """Check if two pages are similar enough to compare"""
        url1 = page1.get('url', '')
        url2 = page2.get('url', '')
        
        # Simple heuristic: pages with similar URLs
        return self.similarity_score(url1, url2) > 0.3
    
    def compare_translations(self, page1, page2, eng1, sin1, eng2, sin2):
        """Compare translations between similar pages"""
        # This is a simplified comparison - in practice, you'd need more sophisticated
        # translation matching algorithms
        
        for section in ['title', 'headings', 'paragraphs']:
            eng1_content = eng1.get(section, [])
            sin1_content = sin1.get(section, [])
            eng2_content = eng2.get(section, [])
            sin2_content = sin2.get(section, [])
            
            # Check if English content is similar but Sinhala content is different
            if (eng1_content and eng2_content and sin1_content and sin2_content):
                eng_similarity = self.similarity_score(str(eng1_content), str(eng2_content))
                sin_similarity = self.similarity_score(str(sin1_content), str(sin2_content))
                
                if eng_similarity > 0.8 and sin_similarity < 0.5:
                    self.discrepancies['english_sinhala'].append({
                        'type': 'translation_inconsistency',
                        'section': section,
                        'page1': page1.get('url'),
                        'page2': page2.get('url'),
                        'english_content': {
                            'page1': eng1_content,
                            'page2': eng2_content
                        },
                        'sinhala_content': {
                            'page1': sin1_content,
                            'page2': sin2_content
                        },
                        'english_similarity': eng_similarity,
                        'sinhala_similarity': sin_similarity
                    })
    
    def find_formatting_issues(self):
        """Find formatting and structural discrepancies"""
        self.logger.info("Analyzing formatting issues...")
        
        for page in self.data.get('pages', []):
            url = page.get('url', '')
            text_content = page.get('text_content', {})
            
            # Check for empty content
            empty_sections = []
            for section, content in text_content.items():
                if not content or (isinstance(content, list) and not any(content)):
                    empty_sections.append(section)
            
            if empty_sections:
                self.discrepancies['formatting_issues'].append({
                    'type': 'empty_content_sections',
                    'url': url,
                    'empty_sections': empty_sections
                })
            
            # Check for very long paragraphs (potential formatting issues)
            paragraphs = text_content.get('paragraphs', [])
            for i, para in enumerate(paragraphs):
                if len(para) > 1000:  # Very long paragraph
                    self.discrepancies['formatting_issues'].append({
                        'type': 'overly_long_paragraph',
                        'url': url,
                        'paragraph_index': i,
                        'length': len(para),
                        'preview': para[:100] + '...'
                    })
            
            # Check for duplicate content within the same page
            all_texts = []
            for section, content in text_content.items():
                if isinstance(content, list):
                    all_texts.extend([str(item) for item in content if item])
                elif content:
                    all_texts.append(str(content))
            
            # Find duplicates
            text_counts = Counter(all_texts)
            duplicates = {text: count for text, count in text_counts.items() if count > 1}
            
            if duplicates:
                self.discrepancies['formatting_issues'].append({
                    'type': 'duplicate_content_within_page',
                    'url': url,
                    'duplicates': duplicates
                })
    
    def analyze_all_discrepancies(self):
        """Run all discrepancy analyses"""
        self.logger.info("Starting comprehensive discrepancy analysis...")
        
        self.find_english_content_discrepancies()
        self.find_translation_discrepancies()
        self.find_sinhala_content_discrepancies()
        self.analyze_banner_discrepancies()
        self.find_terminology_inconsistencies()
        self.find_formatting_issues()
        
        self.logger.info("Discrepancy analysis completed.")
    
    def generate_summary_stats(self) -> Dict:
        """Generate summary statistics"""
        total_pages = len(self.data.get('pages', []))
        total_banners = sum(page.get('total_banners', 0) for page in self.data.get('pages', []))
        total_images = sum(page.get('total_images', 0) for page in self.data.get('pages', []))
        
        discrepancy_counts = {
            category: len(issues) for category, issues in self.discrepancies.items()
        }
        
        return {
            'total_pages_analyzed': total_pages,
            'total_banners_found': total_banners,
            'total_images_processed': total_images,
            'discrepancy_counts': discrepancy_counts,
            'total_discrepancies': sum(discrepancy_counts.values())
        }
    
    def generate_detailed_report(self) -> str:
        """Generate a detailed discrepancy report"""
        stats = self.generate_summary_stats()
        
        report = []
        report.append("="*80)
        report.append("SLT WEBSITE DISCREPANCY ANALYSIS REPORT")
        report.append("="*80)
        report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Source file: {self.json_file_path}")
        report.append("")
        
        # Summary
        report.append("SUMMARY STATISTICS")
        report.append("-" * 40)
        report.append(f"Total pages analyzed: {stats['total_pages_analyzed']}")
        report.append(f"Total banners found: {stats['total_banners_found']}")
        report.append(f"Total images processed: {stats['total_images_processed']}")
        report.append(f"Total discrepancies found: {stats['total_discrepancies']}")
        report.append("")
        
        # Discrepancy breakdown
        report.append("DISCREPANCY BREAKDOWN")
        report.append("-" * 40)
        for category, count in stats['discrepancy_counts'].items():
            report.append(f"{category.replace('_', ' ').title()}: {count}")
        report.append("")
        
        # Detailed findings
        if self.discrepancies['english_content']:
            report.append("1. ENGLISH CONTENT DISCREPANCIES")
            report.append("-" * 50)
            for i, issue in enumerate(self.discrepancies['english_content'][:10], 1):  # Limit to 10
                report.append(f"Issue {i}: {issue['type']}")
                report.append(f"Term: {issue['term']}")
                report.append(f"Variations found: {', '.join(issue['variations'])}")
                report.append(f"Occurrences: {len(issue['occurrences'])}")
                report.append("")
        
        if self.discrepancies['english_sinhala']:
            report.append("2. ENGLISH-SINHALA TRANSLATION DISCREPANCIES")
            report.append("-" * 50)
            for i, issue in enumerate(self.discrepancies['english_sinhala'][:10], 1):
                report.append(f"Issue {i}: {issue['type']}")
                report.append(f"Pages: {issue['page1']} vs {issue['page2']}")
                report.append(f"English similarity: {issue['english_similarity']:.2f}")
                report.append(f"Sinhala similarity: {issue['sinhala_similarity']:.2f}")
                report.append("")
        
        if self.discrepancies['sinhala_sinhala']:
            report.append("3. SINHALA CONTENT DISCREPANCIES")
            report.append("-" * 50)
            for i, issue in enumerate(self.discrepancies['sinhala_sinhala'][:10], 1):
                report.append(f"Issue {i}: {issue['type']}")
                report.append(f"Term: {issue['term']}")
                report.append(f"Variations found: {len(issue['variations'])}")
                report.append(f"Occurrences: {len(issue['occurrences'])}")
                report.append("")
        
        if self.discrepancies['banner_text']:
            report.append("4. BANNER TEXT DISCREPANCIES")
            report.append("-" * 50)
            for i, issue in enumerate(self.discrepancies['banner_text'][:10], 1):
                report.append(f"Issue {i}: {issue['type']}")
                report.append(f"Variations: {', '.join(issue['variations'])}")
                report.append(f"Found in {len(issue['occurrences'])} banners")
                report.append("")
        
        if self.discrepancies['missing_translations']:
            report.append("5. MISSING TRANSLATIONS")
            report.append("-" * 50)
            for i, issue in enumerate(self.discrepancies['missing_translations'][:10], 1):
                report.append(f"Issue {i}: {issue['type']}")
                report.append(f"URL: {issue['url']}")
                report.append("")
        
        if self.discrepancies['inconsistent_terminology']:
            report.append("6. INCONSISTENT TERMINOLOGY")
            report.append("-" * 50)
            for i, issue in enumerate(self.discrepancies['inconsistent_terminology'][:10], 1):
                report.append(f"Issue {i}: Base term '{issue['base_term']}'")
                report.append(f"Variations: {', '.join(issue['variations'])}")
                report.append(f"Total occurrences: {len(issue['occurrences'])}")
                report.append("")
        
        if self.discrepancies['formatting_issues']:
            report.append("7. FORMATTING ISSUES")
            report.append("-" * 50)
            for i, issue in enumerate(self.discrepancies['formatting_issues'][:10], 1):
                report.append(f"Issue {i}: {issue['type']}")
                report.append(f"URL: {issue['url']}")
                if 'empty_sections' in issue:
                    report.append(f"Empty sections: {', '.join(issue['empty_sections'])}")
                elif 'length' in issue:
                    report.append(f"Paragraph length: {issue['length']} characters")
                report.append("")
        
        # Recommendations
        report.append("RECOMMENDATIONS")
        report.append("-" * 40)
        recommendations = []
        
        if stats['discrepancy_counts']['english_content'] > 0:
            recommendations.append("• Establish a style guide for consistent English terminology")
        
        if stats['discrepancy_counts']['english_sinhala'] > 0:
            recommendations.append("• Review translation processes to ensure consistency")
        
        if stats['discrepancy_counts']['sinhala_sinhala'] > 0:
            recommendations.append("• Standardize Sinhala terminology across all pages")
        
        if stats['discrepancy_counts']['banner_text'] > 0:
            recommendations.append("• Create consistent banner templates and text standards")
        
        if stats['discrepancy_counts']['missing_translations'] > 0:
            recommendations.append("• Complete missing translations for bilingual consistency")
        
        if stats['discrepancy_counts']['formatting_issues'] > 0:
            recommendations.append("• Review content structure and formatting guidelines")
        
        for rec in recommendations:
            report.append(rec)
        
        report.append("")
        report.append("="*80)
        
        return "\n".join(report)
    
    def save_report(self, filename: str = None):
        """Save the detailed report to a file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'slt_discrepancy_report_{timestamp}.txt'
        
        report_content = self.generate_detailed_report()
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            # Also save raw discrepancy data as JSON
            json_filename = filename.replace('.txt', '.json')
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'analysis_timestamp': datetime.now().isoformat(),
                    'source_file': self.json_file_path,
                    'summary_stats': self.generate_summary_stats(),
                    'discrepancies': self.discrepancies
                }, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Report saved to {filename}")
            self.logger.info(f"Raw data saved to {json_filename}")
            
            return filename, json_filename
        
        except Exception as e:
            self.logger.error(f"Error saving report: {e}")
            return None, None

def main():
    """Main function to run the discrepancy analyzer"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python discrepancy_analyzer.py <scraped_data.json>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    try:
        print("Starting discrepancy analysis...")
        analyzer = DiscrepancyAnalyzer(json_file)
        analyzer.analyze_all_discrepancies()
        
        # Generate and save report
        report_file, json_file = analyzer.save_report()
        
        if report_file:
            print(f"\nAnalysis completed successfully!")
            print(f"Detailed report saved to: {report_file}")
            print(f"Raw data saved to: {json_file}")
            
            # Print summary to console
            stats = analyzer.generate_summary_stats()
            print(f"\nSUMMARY:")
            print(f"Total pages analyzed: {stats['total_pages_analyzed']}")
            print(f"Total discrepancies found: {stats['total_discrepancies']}")
            
            for category, count in stats['discrepancy_counts'].items():
                if count > 0:
                    print(f"- {category.replace('_', ' ').title()}: {count}")
        else:
            print("Error generating report.")
    
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()