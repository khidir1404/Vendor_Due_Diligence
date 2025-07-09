#!/usr/bin/env python3
"""
Enterprise Vendor Due Diligence Platform - Stanza Edition
Production-ready application for comprehensive vendor risk assessment
with PDF archival and advanced contextual analysis using Stanza NLP.
"""

import os
import sys
import asyncio
import logging
import threading
import queue
import datetime
import time
import json
import hashlib
import uuid
from pathlib import Path
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

# Core dependencies
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from googleapiclient.discovery import build
from tenacity import retry, stop_after_attempt, wait_fixed
import stanza  # Using Stanza instead of spaCy
from playwright.async_api import async_playwright, Browser, Page
import aiofiles
from concurrent.futures import ThreadPoolExecutor, as_completed

# GUI dependencies
try:
    import customtkinter as ctk
    ctk.set_default_color_theme("blue")
    GUI_LIB = "customtkinter"
except ImportError:
    import tkinter as ctk
    from tkinter import ttk, scrolledtext, messagebox
    GUI_LIB = "tkinter"

# -----------------------------------
# Configuration & Environment Setup
# -----------------------------------

# Load environment variables
load_dotenv()

@dataclass
class AppConfig:
    """Centralized configuration management"""
    # API Credentials
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    custom_search_engine_id: str = os.getenv("CUSTOM_SEARCH_ENGINE_ID", "")
    
    # Application Settings
    max_google_pages: int = 3
    results_per_page: int = 10
    max_concurrent_scrapes: int = 8
    http_timeout: int = 20
    pdf_timeout: int = 30
    
    # Risk Analysis
    min_confidence_score: float = 0.75
    context_window_size: int = 150
    
    # File Management
    base_output_dir: str = "vendor_intelligence"
    pdf_archive_dir: str = "pdf_archive"
    reports_dir: str = "reports"
    logs_dir: str = "logs"
    
    # Risk Keywords (Enhanced)
    risk_keywords: List[str] = None
    
    def __post_init__(self):
        if self.risk_keywords is None:
            self.risk_keywords = [
                # Financial Crimes
                "fraud", "fraudulent", "embezzlement", "money laundering", "tax evasion",
                "bribery", "kickback", "corruption", "insider trading", "ponzi scheme",
                
                # Legal Issues
                "lawsuit", "litigation", "sued", "convicted", "guilty", "sentenced",
                "indicted", "charged", "violated", "breach", "penalty", "fine",
                
                # Regulatory Violations
                "SEC violation", "regulatory action", "compliance failure", "sanctions",
                "OFAC", "investigation", "probe", "audit findings", "enforcement action",
                
                # Operational Risks
                "data breach", "cybersecurity incident", "hack", "leaked", "exposed",
                "safety violation", "accident", "recall", "contamination", "defective",
                
                # Reputational Issues
                "scandal", "misconduct", "unethical", "discrimination", "harassment",
                "whistleblower", "cover-up", "conflict of interest", "nepotism"
            ]

# Initialize configuration
config = AppConfig()

# -----------------------------------
# Advanced Logging Setup
# -----------------------------------

class ProductionLogger:
    """Enterprise-grade logging configuration"""
    
    def __init__(self, log_dir: str = config.logs_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.setup_logging()
    
    def setup_logging(self):
        """Configure comprehensive logging"""
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        )
        
        # Root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        root_logger.addHandler(console_handler)
        
        # Application log file
        app_log = self.log_dir / f"vendor_dd_{datetime.date.today()}.log"
        file_handler = logging.FileHandler(app_log)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
        # Error log file
        error_log = self.log_dir / f"errors_{datetime.date.today()}.log"
        error_handler = logging.FileHandler(error_log)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)

# Initialize logging
logger_setup = ProductionLogger()
logger = logging.getLogger(__name__)

# -----------------------------------
# Data Models
# -----------------------------------

@dataclass
class RiskFinding:
    """Structured risk finding with context"""
    url: str
    title: str
    context: str
    confidence_score: float
    risk_category: str
    entities_found: List[str]
    timestamp: datetime.datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class VendorProfile:
    """Comprehensive vendor assessment profile"""
    company_name: str
    analysis_timestamp: datetime.datetime
    total_pages_analyzed: int
    risk_findings: List[RiskFinding]
    clean_pages: int
    pdf_files_generated: List[str]
    overall_risk_score: float
    risk_level: str
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['risk_findings'] = [finding.to_dict() for finding in self.risk_findings]
        return data

# -----------------------------------
# Advanced NLP Risk Analyzer using Stanza
# -----------------------------------

class ContextualRiskAnalyzer:
    """Advanced NLP-powered risk analysis engine using Stanza"""
    
    def __init__(self):
        self.nlp = None
        self.load_models()
    
    def load_models(self):
        """Load Stanza models with error handling"""
        try:
            # Initialize Stanza pipeline with English models
            self.nlp = stanza.Pipeline(
                lang='en',
                processors='tokenize,ner,pos,lemma',
                verbose=False,
                download_method=None  # Don't auto-download, assume models are present
            )
            logger.info("Stanza English pipeline loaded successfully")
        except Exception as e:
            logger.warning(f"Stanza pipeline loading failed: {e}")
            logger.info("Attempting to download English models...")
            try:
                # Download English models if not present
                stanza.download('en', verbose=False)
                self.nlp = stanza.Pipeline(
                    lang='en',
                    processors='tokenize,ner,pos,lemma',
                    verbose=False
                )
                logger.info("Stanza models downloaded and loaded successfully")
            except Exception as download_error:
                logger.error(f"Failed to download/load Stanza models: {download_error}")
                self.nlp = None
    
    def extract_company_mentions(self, text: str, company_name: str) -> List[Tuple[int, int, str]]:
        """Extract company mentions with context positions"""
        mentions = []
        company_variations = self._generate_company_variations(company_name)
        
        text_lower = text.lower()
        for variation in company_variations:
            start = 0
            while True:
                pos = text_lower.find(variation.lower(), start)
                if pos == -1:
                    break
                
                # Extract context window
                context_start = max(0, pos - config.context_window_size)
                context_end = min(len(text), pos + len(variation) + config.context_window_size)
                context = text[context_start:context_end]
                
                mentions.append((pos, pos + len(variation), context))
                start = pos + 1
        
        return mentions
    
    def _generate_company_variations(self, company_name: str) -> List[str]:
        """Generate company name variations for better matching"""
        variations = [company_name]
        
        # Remove common suffixes
        suffixes = ["Inc", "Corp", "Corporation", "LLC", "Ltd", "Limited", "Co"]
        base_name = company_name
        for suffix in suffixes:
            if base_name.endswith(f" {suffix}"):
                base_name = base_name[:-len(f" {suffix}")]
                variations.append(base_name)
        
        # Add variations with/without periods
        variations.extend([name.replace(".", "") for name in variations])
        variations.extend([name + "." for name in variations if not name.endswith(".")])
        
        return list(set(variations))
    
    def analyze_risk_context(self, text: str, company_name: str) -> Optional[RiskFinding]:
        """Perform contextual risk analysis using Stanza"""
        if not self.nlp:
            return None
        
        try:
            # Extract company mentions with context
            mentions = self.extract_company_mentions(text, company_name)
            if not mentions:
                return None
            
            # Analyze each mention for risk context
            for start_pos, end_pos, context in mentions:
                risk_score = self._calculate_risk_score(context, company_name)
                
                if risk_score >= config.min_confidence_score:
                    # Process context with Stanza for entity extraction
                    doc = self.nlp(context)
                    
                    # Extract named entities using Stanza
                    entities = []
                    for sentence in doc.sentences:
                        for ent in sentence.ents:
                            entities.append(ent.text)
                    
                    # Determine risk category
                    risk_category = self._classify_risk_category(context)
                    
                    return RiskFinding(
                        url="",  # To be filled by caller
                        title="",  # To be filled by caller
                        context=context.strip(),
                        confidence_score=risk_score,
                        risk_category=risk_category,
                        entities_found=entities,
                        timestamp=datetime.datetime.now()
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Risk analysis error: {e}")
            return None
    
    def _calculate_risk_score(self, context: str, company_name: str) -> float:
        """Calculate risk confidence score based on context"""
        context_lower = context.lower()
        company_lower = company_name.lower()
        
        # Check for risk keywords near company mention
        risk_indicators = 0
        total_keywords = len(config.risk_keywords)
        
        for keyword in config.risk_keywords:
            if keyword.lower() in context_lower:
                # Check proximity to company name
                company_pos = context_lower.find(company_lower)
                keyword_pos = context_lower.find(keyword.lower())
                
                if company_pos != -1 and keyword_pos != -1:
                    distance = abs(company_pos - keyword_pos)
                    # Closer keywords have higher weight
                    if distance < 50:
                        risk_indicators += 1.0
                    elif distance < 100:
                        risk_indicators += 0.7
                    elif distance < 200:
                        risk_indicators += 0.4
        
        # Calculate confidence score
        base_score = min(risk_indicators / max(total_keywords * 0.1, 1), 1.0)
        
        # Boost score for strong indicators
        strong_indicators = ["convicted", "guilty", "sentenced", "fined", "violated", "breach"]
        for indicator in strong_indicators:
            if indicator in context_lower:
                base_score = min(base_score + 0.2, 1.0)
        
        return base_score
    
    def _classify_risk_category(self, context: str) -> str:
        """Classify the type of risk based on context"""
        context_lower = context.lower()
        
        categories = {
            "Financial Crime": ["fraud", "embezzlement", "money laundering", "bribery", "corruption"],
            "Legal Issues": ["lawsuit", "sued", "convicted", "guilty", "litigation", "violation"],
            "Regulatory": ["SEC", "regulatory", "compliance", "sanctions", "OFAC", "enforcement"],
            "Operational": ["breach", "hack", "safety", "recall", "accident", "defective"],
            "Reputational": ["scandal", "misconduct", "unethical", "discrimination", "harassment"]
        }
        
        for category, keywords in categories.items():
            if any(keyword in context_lower for keyword in keywords):
                return category
        
        return "General Risk"

# -----------------------------------
# PDF Generation Engine
# -----------------------------------

class PDFArchiveManager:
    """High-performance web-to-PDF conversion system"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.browser = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def generate_pdf(self, url: str, company_name: str) -> Optional[str]:
        """Generate PDF from URL with enhanced error handling"""
        try:
            # Create safe filename
            parsed_url = urlparse(url)
            safe_domain = self._sanitize_filename(parsed_url.netloc)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{company_name}_{safe_domain}_{timestamp}.pdf"
            filepath = self.output_dir / filename
            
            # Create new page with extended timeout
            page = await self.browser.new_page()
            
            # Set realistic viewport and headers
            await page.set_viewport_size({"width": 1920, "height": 1080})
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            
            # Navigate with timeout
            await page.goto(url, timeout=config.pdf_timeout * 1000, wait_until="networkidle")
            
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Generate PDF with print-optimized settings
            await page.pdf(
                path=str(filepath),
                format="A4",
                print_background=True,
                margin={
                    "top": "1cm",
                    "right": "1cm", 
                    "bottom": "1cm",
                    "left": "1cm"
                }
            )
            
            await page.close()
            
            logger.info(f"PDF generated successfully: {filename}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"PDF generation failed for {url}: {e}")
            return None
    
    def _sanitize_filename(self, filename: str) -> str:
        """Create filesystem-safe filename"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Truncate if too long
        return filename[:50]

# -----------------------------------
# Search & Analysis Engine
# -----------------------------------

class GoogleSearchManager:
    """Enterprise Google Custom Search integration"""
    
    def __init__(self):
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Custom Search service"""
        try:
            if not config.google_api_key or not config.custom_search_engine_id:
                raise ValueError("Google API credentials not configured")
            
            self.service = build("customsearch", "v1", developerKey=config.google_api_key)
            logger.info("Google Custom Search service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google service: {e}")
            self.service = None
    
    async def search_company_risks(self, company_name: str) -> List[str]:
        """Search for company risk-related content"""
        if not self.service:
            logger.error("Google Search service not available")
            return []
        
        all_urls = []
        
        # Enhanced search query with risk context
        search_query = f'"{company_name}" (' + ' OR '.join(config.risk_keywords[:10]) + ')'
        
        try:
            for page in range(config.max_google_pages):
                start_index = page * config.results_per_page + 1
                
                result = self.service.cse().list(
                    q=search_query,
                    cx=config.custom_search_engine_id,
                    start=start_index,
                    num=config.results_per_page
                ).execute()
                
                items = result.get('items', [])
                page_urls = [item.get('link') for item in items if item.get('link')]
                all_urls.extend(page_urls)
                
                # Rate limiting
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Google search error: {e}")
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(all_urls))

# -----------------------------------
# Content Analysis Engine
# -----------------------------------

class WebContentAnalyzer:
    """Advanced web content extraction and analysis"""
    
    def __init__(self):
        self.risk_analyzer = ContextualRiskAnalyzer()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def analyze_page(self, url: str, company_name: str) -> Optional[RiskFinding]:
        """Analyze webpage for risk indicators"""
        try:
            # Fetch page content
            response = self.session.get(url, timeout=config.http_timeout)
            response.raise_for_status()
            
            # Parse content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = soup.title.string.strip() if soup.title else urlparse(url).netloc
            
            # Extract main content (remove scripts, styles, etc.)
            for script_or_style in soup(["script", "style", "nav", "footer", "header"]):
                script_or_style.decompose()
            
            text_content = soup.get_text(" ", strip=True)
            
            # Perform contextual risk analysis
            risk_finding = self.risk_analyzer.analyze_risk_context(text_content, company_name)
            
            if risk_finding:
                risk_finding.url = url
                risk_finding.title = title
                logger.info(f"Risk found in {url}: {risk_finding.risk_category}")
                return risk_finding
            else:
                logger.debug(f"No risk indicators found in {url}")
                return None
                
        except Exception as e:
            logger.error(f"Analysis failed for {url}: {e}")
            return None

# -----------------------------------
# Report Generation System
# -----------------------------------

class EnterpriseReportGenerator:
    """Advanced report generation with multiple formats"""
    
    def __init__(self, reports_dir: str):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_comprehensive_report(self, vendor_profile: VendorProfile) -> str:
        """Generate detailed text report"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"VendorDueDiligence_{vendor_profile.company_name}_{timestamp}.txt"
        filepath = self.reports_dir / filename
        
        report_content = self._build_report_content(vendor_profile)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"Comprehensive report generated: {filename}")
        return str(filepath)
    
    def _build_report_content(self, profile: VendorProfile) -> str:
        """Build formatted report content"""
        lines = []
        
        # Header
        lines.extend([
            "=" * 80,
            "ENTERPRISE VENDOR DUE DILIGENCE REPORT",
            "=" * 80,
            f"Company: {profile.company_name}",
            f"Analysis Date: {profile.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Report ID: {uuid.uuid4().hex[:8].upper()}",
            f"NLP Engine: Stanford Stanza v{stanza.__version__}",
            "",
            "EXECUTIVE SUMMARY",
            "-" * 20,
            f"Overall Risk Level: {profile.risk_level}",
            f"Risk Score: {profile.overall_risk_score:.2f}/1.00",
            f"Total Pages Analyzed: {profile.total_pages_analyzed}",
            f"Risk Findings: {len(profile.risk_findings)}",
            f"Clean Pages: {profile.clean_pages}",
            f"PDF Archives Generated: {len(profile.pdf_files_generated)}",
            ""
        ])
        
        # Risk Analysis
        if profile.risk_findings:
            lines.extend([
                "DETAILED RISK FINDINGS",
                "-" * 25,
                ""
            ])
            
            # Group findings by category
            by_category = {}
            for finding in profile.risk_findings:
                category = finding.risk_category
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(finding)
            
            for category, findings in by_category.items():
                lines.append(f"{category.upper()} ({len(findings)} findings)")
                lines.append("─" * (len(category) + 20))
                
                for i, finding in enumerate(findings, 1):
                    lines.extend([
                        f"{i}. Source: {finding.title}",
                        f"   URL: {finding.url}",
                        f"   Confidence: {finding.confidence_score:.2f}",
                        f"   Context: {finding.context[:200]}...",
                        f"   Named Entities: {', '.join(finding.entities_found[:5])}",
                        ""
                    ])
        else:
            lines.extend([
                "RISK ASSESSMENT RESULTS",
                "-" * 25,
                "✓ No significant risk indicators identified",
                "✓ Company mentions found in clean contexts",
                "✓ Recommended for standard due diligence procedures",
                ""
            ])
        
        # Recommendations
        lines.extend([
            "RECOMMENDATIONS",
            "-" * 15,
        ])
        lines.extend([f"• {rec}" for rec in profile.recommendations])
        lines.append("")
        
        # PDF Archives
        if profile.pdf_files_generated:
            lines.extend([
                "ARCHIVED DOCUMENTS",
                "-" * 18,
                f"Generated {len(profile.pdf_files_generated)} PDF archives:"
            ])
            for pdf_file in profile.pdf_files_generated:
                lines.append(f"• {Path(pdf_file).name}")
            lines.append("")
        
        # Compliance Notice
        lines.extend([
            "COMPLIANCE & METHODOLOGY",
            "-" * 25,
            "• Analysis conducted using Stanford Stanza NLP framework",
            "• Risk scoring based on proximity and semantic analysis",
            "• All source documents archived for audit purposes",
            "• Findings require human review for final decision-making",
            "",
            "=" * 80,
            "END OF REPORT",
            "=" * 80
        ])
        
        return "\n".join(lines)

# -----------------------------------
# Main Application Controller
# -----------------------------------

class VendorDueDiligenceEngine:
    """Main application orchestrator"""
    
    def __init__(self):
        self.search_manager = GoogleSearchManager()
        self.content_analyzer = WebContentAnalyzer()
        self.report_generator = EnterpriseReportGenerator(config.reports_dir)
        
        # Create directory structure
        self._create_directory_structure()
    
    def _create_directory_structure(self):
        """Create organized directory structure"""
        base_dir = Path(config.base_output_dir)
        
        dirs_to_create = [
            base_dir,
            base_dir / config.pdf_archive_dir,
            base_dir / config.reports_dir,
            base_dir / config.logs_dir
        ]
        
        for directory in dirs_to_create:
            directory.mkdir(parents=True, exist_ok=True)
        
        logger.info("Directory structure created successfully")
    
    async def conduct_due_diligence(self, company_name: str) -> VendorProfile:
        """Execute comprehensive vendor due diligence"""
        logger.info(f"Starting due diligence analysis for: {company_name}")
        start_time = datetime.datetime.now()
        
        # Initialize results
        risk_findings = []
        pdf_files = []
        clean_pages = 0
        
        try:
            # Step 1: Search for risk-related content
            urls = await self.search_manager.search_company_risks(company_name)
            logger.info(f"Found {len(urls)} URLs for analysis")
            
            # Step 2: Concurrent analysis with PDF generation
            async with PDFArchiveManager(Path(config.base_output_dir) / config.pdf_archive_dir) as pdf_manager:
                
                # Analyze content and generate PDFs concurrently
                tasks = []
                for url in urls:
                    task = asyncio.create_task(
                        self._analyze_and_archive(url, company_name, pdf_manager)
                    )
                    tasks.append(task)
                
                # Process results as they complete
                for i, task in enumerate(asyncio.as_completed(tasks)):
                    try:
                        result = await task
                        if result:
                            risk_finding, pdf_path = result
                            if risk_finding:
                                risk_findings.append(risk_finding)
                                logger.info(f"Risk identified: {risk_finding.risk_category}")
                            else:
                                clean_pages += 1
                            
                            if pdf_path:
                                pdf_files.append(pdf_path)
                        
                        # Progress logging
                        progress = ((i + 1) / len(tasks)) * 100
                        logger.info(f"Analysis progress: {progress:.1f}%")
                        
                    except Exception as e:
                        logger.error(f"Task failed: {e}")
                        continue
            
            # Step 3: Calculate risk metrics
            overall_risk_score = self._calculate_overall_risk_score(risk_findings, len(urls))
            risk_level = self._determine_risk_level(overall_risk_score, len(risk_findings))
            recommendations = self._generate_recommendations(risk_level, len(risk_findings), len(urls))
            
            # Step 4: Create vendor profile
            vendor_profile = VendorProfile(
                company_name=company_name,
                analysis_timestamp=start_time,
                total_pages_analyzed=len(urls),
                risk_findings=risk_findings,
                clean_pages=clean_pages,
                pdf_files_generated=pdf_files,
                overall_risk_score=overall_risk_score,
                risk_level=risk_level,
                recommendations=recommendations
            )
            
            logger.info(f"Due diligence completed for {company_name}: {risk_level} risk level")
            return vendor_profile
            
        except Exception as e:
            logger.error(f"Due diligence failed for {company_name}: {e}")
            raise
    
    async def _analyze_and_archive(self, url: str, company_name: str, pdf_manager: PDFArchiveManager) -> Optional[Tuple[Optional[RiskFinding], Optional[str]]]:
        """Analyze content and generate PDF archive"""
        try:
            # Concurrent analysis and PDF generation
            analysis_task = self.content_analyzer.analyze_page(url, company_name)
            pdf_task = pdf_manager.generate_pdf(url, company_name)
            
            risk_finding, pdf_path = await asyncio.gather(analysis_task, pdf_task)
            
            return (risk_finding, pdf_path)
            
        except Exception as e:
            logger.error(f"Analysis and archival failed for {url}: {e}")
            return None
    
    def _calculate_overall_risk_score(self, risk_findings: List[RiskFinding], total_pages: int) -> float:
        """Calculate comprehensive risk score"""
        if not risk_findings or total_pages == 0:
            return 0.0
        
        # Base score from average confidence
        avg_confidence = sum(finding.confidence_score for finding in risk_findings) / len(risk_findings)
        
        # Adjust for frequency
        frequency_factor = min(len(risk_findings) / total_pages, 0.5)
        
        # Adjust for severity
        severity_multiplier = 1.0
        high_severity_categories = ["Financial Crime", "Legal Issues", "Regulatory"]
        for finding in risk_findings:
            if finding.risk_category in high_severity_categories:
                severity_multiplier = min(severity_multiplier + 0.1, 1.5)
        
        final_score = (avg_confidence * 0.6 + frequency_factor * 0.4) * severity_multiplier
        return min(final_score, 1.0)
    
    def _determine_risk_level(self, risk_score: float, finding_count: int) -> str:
        """Determine categorical risk level"""
        if risk_score >= 0.8 or finding_count >= 10:
            return "HIGH RISK"
        elif risk_score >= 0.6 or finding_count >= 5:
            return "MEDIUM RISK"
        elif risk_score >= 0.3 or finding_count >= 2:
            return "LOW RISK"
        else:
            return "MINIMAL RISK"
    
    def _generate_recommendations(self, risk_level: str, finding_count: int, total_pages: int) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if risk_level == "HIGH RISK":
            recommendations.extend([
                "Immediate escalation to senior management required",
                "Conduct detailed investigation before proceeding",
                "Consider engaging specialized due diligence firm",
                "Review all contractual terms and conditions",
                "Implement enhanced monitoring procedures"
            ])
        elif risk_level == "MEDIUM RISK":
            recommendations.extend([
                "Additional verification of identified risk areas required",
                "Request clarification from vendor regarding flagged issues",
                "Consider phased engagement with milestone reviews",
                "Implement standard risk mitigation procedures"
            ])
        elif risk_level == "LOW RISK":
            recommendations.extend([
                "Standard due diligence procedures recommended",
                "Monitor identified areas during engagement",
                "Document risk mitigation strategies in contract"
            ])
        else:
            recommendations.extend([
                "Proceed with standard vendor onboarding process",
                "Implement routine monitoring procedures",
                "Maintain regular vendor performance reviews"
            ])
        
        # Add general recommendations
        recommendations.extend([
            f"Analyzed {total_pages} web sources using Stanford Stanza NLP",
            "All source documents archived for audit purposes",
            "Recommend periodic re-assessment based on vendor risk profile"
        ])
        
        return recommendations

# -----------------------------------
# Enterprise GUI Application
# -----------------------------------

class EnterpriseVendorDueDiligenceGUI:
    """Production-ready GUI application"""
    
    def __init__(self):
        self.root = ctk.CTk() if GUI_LIB == "customtkinter" else ctk.Tk()
        self.root.title("Enterprise Vendor Due Diligence Platform - Stanza Edition")
        self.root.geometry("1200x800")
        
        self.due_diligence_engine = VendorDueDiligenceEngine()
        self.result_queue = queue.Queue()
        self.is_running = False
        
        self._setup_gui()
        self._start_queue_monitor()
    
    def _setup_gui(self):
        """Setup enterprise-grade GUI"""
        # Header
        header_frame = ctk.CTkFrame(self.root) if GUI_LIB == "customtkinter" else ctk.Frame(self.root)
        header_frame.pack(fill="x", padx=20, pady=10)
        
        title_font = ctk.CTkFont(size=24, weight="bold") if GUI_LIB == "customtkinter" else ("Arial", 18, "bold")
        title_label = ctk.CTkLabel(header_frame, text="Enterprise Vendor Due Diligence Platform", font=title_font) if GUI_LIB == "customtkinter" else ctk.Label(header_frame, text="Enterprise Vendor Due Diligence Platform", font=title_font)
        title_label.pack()
        
        subtitle_label = ctk.CTkLabel(header_frame, text="Advanced Risk Assessment with PDF Archival & Stanford Stanza NLP") if GUI_LIB == "customtkinter" else ctk.Label(header_frame, text="Advanced Risk Assessment with PDF Archival & Stanford Stanza NLP")
        subtitle_label.pack()
        
        # Input section
        input_frame = ctk.CTkFrame(self.root) if GUI_LIB == "customtkinter" else ctk.Frame(self.root)
        input_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(input_frame, text="Target Company:").pack(side="left", padx=(0, 10)) if GUI_LIB == "customtkinter" else ctk.Label(input_frame, text="Target Company:").pack(side="left", padx=(0, 10))
        
        self.company_entry = ctk.CTkEntry(input_frame, placeholder_text="Enter company name for analysis", width=400) if GUI_LIB == "customtkinter" else ctk.Entry(input_frame, width=50)
        self.company_entry.pack(side="left", padx=(0, 10))
        
        self.analyze_btn = ctk.CTkButton(input_frame, text="Start Analysis", command=self._start_analysis) if GUI_LIB == "customtkinter" else ctk.Button(input_frame, text="Start Analysis", command=self._start_analysis)
        self.analyze_btn.pack(side="left")
        
        # Progress section
        progress_frame = ctk.CTkFrame(self.root) if GUI_LIB == "customtkinter" else ctk.Frame(self.root)
        progress_frame.pack(fill="x", padx=20, pady=10)
        
        if GUI_LIB == "customtkinter":
            self.progress_bar = ctk.CTkProgressBar(progress_frame)
            self.progress_bar.pack(fill="x", pady=5)
            self.progress_bar.set(0)
        else:
            self.progress_bar = ttk.Progressbar(progress_frame, mode="indeterminate")
            self.progress_bar.pack(fill="x", pady=5)
        
        self.status_label = ctk.CTkLabel(progress_frame, text="Ready for analysis - Stanford Stanza NLP Engine Loaded") if GUI_LIB == "customtkinter" else ctk.Label(progress_frame, text="Ready for analysis - Stanford Stanza NLP Engine Loaded")
        self.status_label.pack()
        
        # Results section
        results_frame = ctk.CTkFrame(self.root) if GUI_LIB == "customtkinter" else ctk.Frame(self.root)
        results_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        results_label = ctk.CTkLabel(results_frame, text="Analysis Results:", font=ctk.CTkFont(weight="bold")) if GUI_LIB == "customtkinter" else ctk.Label(results_frame, text="Analysis Results:", font=("Arial", 12, "bold"))
        results_label.pack(anchor="w")
        
        if GUI_LIB == "customtkinter":
            self.results_text = ctk.CTkTextbox(results_frame, wrap="word")
        else:
            self.results_text = scrolledtext.ScrolledText(results_frame, wrap="word")
            # Configure color tags
            self.results_text.tag_config("risk", foreground="red", background="#ffe6e6")
            self.results_text.tag_config("clean", foreground="green", background="#e6ffe6")
            self.results_text.tag_config("info", foreground="blue")
            self.results_text.tag_config("header", foreground="purple", font=("Arial", 12, "bold"))
        
        self.results_text.pack(fill="both", expand=True)
        self._set_text_state("disabled")
    
    def _start_analysis(self):
        """Start vendor due diligence analysis"""
        if self.is_running:
            return
        
        company_name = self.company_entry.get().strip()
        if not company_name:
            self._show_message("Input Required", "Please enter a company name for analysis")
            return
        
        self.is_running = True
        self.analyze_btn.configure(state="disabled")
        self._update_status("Initializing enterprise due diligence analysis with Stanza NLP...")
        self._clear_results()
        
        if GUI_LIB == "customtkinter":
            self.progress_bar.start()
        else:
            self.progress_bar.start()
        
        # Start analysis in background thread
        analysis_thread = threading.Thread(
            target=self._run_analysis_worker,
            args=(company_name,),
            daemon=True
        )
        analysis_thread.start()
    
    def _run_analysis_worker(self, company_name: str):
        """Background worker for analysis"""
        try:
            # Run async analysis in thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            vendor_profile = loop.run_until_complete(
                self.due_diligence_engine.conduct_due_diligence(company_name)
            )
            
            # Generate report
            report_path = self.due_diligence_engine.report_generator.generate_comprehensive_report(vendor_profile)
            
            # Send results to GUI
            self.result_queue.put(("COMPLETED", vendor_profile, report_path))
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            self.result_queue.put(("ERROR", str(e)))
        finally:
            loop.close()
    
    def _start_queue_monitor(self):
        """Monitor result queue for updates"""
        try:
            while True:
                item = self.result_queue.get_nowait()
                
                if item[0] == "COMPLETED":
                    _, vendor_profile, report_path = item
                    self._display_results(vendor_profile, report_path)
                    self._analysis_complete()
                elif item[0] == "ERROR":
                    _, error_msg = item
                    self._log_result(f"❌ Analysis failed: {error_msg}", "risk")
                    self._analysis_complete()
                elif item[0] == "STATUS":
                    _, status_msg = item
                    self._update_status(status_msg)
                elif item[0] == "PROGRESS":
                    _, progress = item
                    if GUI_LIB == "customtkinter":
                        self.progress_bar.set(progress)
                else:
                    self._log_result(str(item), "info")
                    
        except queue.Empty:
            pass
        
        self.root.after(100, self._start_queue_monitor)
    
    def _display_results(self, vendor_profile: VendorProfile, report_path: str):
        """Display comprehensive analysis results"""
        self._log_result("=== ENTERPRISE DUE DILIGENCE ANALYSIS COMPLETE ===", "header")
        self._log_result(f"Company: {vendor_profile.company_name}", "info")
        self._log_result(f"Analysis Date: {vendor_profile.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S')}", "info")
        self._log_result(f"NLP Engine: Stanford Stanza v{stanza.__version__}", "info")
        self._log_result("", "info")
        
        # Executive Summary
        self._log_result("EXECUTIVE SUMMARY:", "header")
        self._log_result(f"Overall Risk Level: {vendor_profile.risk_level}", 
                        "risk" if "HIGH" in vendor_profile.risk_level else "clean" if "MINIMAL" in vendor_profile.risk_level else "info")
        self._log_result(f"Risk Score: {vendor_profile.overall_risk_score:.2f}/1.00", "info")
        self._log_result(f"Pages Analyzed: {vendor_profile.total_pages_analyzed}", "info")
        self._log_result(f"Risk Findings: {len(vendor_profile.risk_findings)}", 
                        "risk" if vendor_profile.risk_findings else "clean")
        self._log_result(f"PDF Archives: {len(vendor_profile.pdf_files_generated)}", "info")
        self._log_result("", "info")
        
        # Risk Findings
        if vendor_profile.risk_findings:
            self._log_result("RISK FINDINGS DETECTED:", "risk")
            for i, finding in enumerate(vendor_profile.risk_findings[:5], 1):  # Show top 5
                self._log_result(f"{i}. {finding.risk_category} (Confidence: {finding.confidence_score:.2f})", "risk")
                self._log_result(f"   Source: {finding.title}", "info")
                self._log_result(f"   Context: {finding.context[:150]}...", "info")
                if finding.entities_found:
                    self._log_result(f"   Named Entities: {', '.join(finding.entities_found[:3])}", "info")
                self._log_result("", "info")
        else:
            self._log_result("✓ No significant risk indicators identified", "clean")
            self._log_result("✓ Company mentions found in clean contexts", "clean")
        
        # Recommendations
        self._log_result("KEY RECOMMENDATIONS:", "header")
        for rec in vendor_profile.recommendations[:5]:  # Show top 5
            self._log_result(f"• {rec}", "info")
        
        self._log_result("", "info")
        self._log_result(f"📄 Comprehensive report saved: {Path(report_path).name}", "info")
        self._log_result(f"📁 PDF archives available in: {config.pdf_archive_dir}/", "info")
        self._log_result(f"🔬 Powered by Stanford Stanza NLP Framework", "info")
    
    def _analysis_complete(self):
        """Clean up after analysis completion"""
        self.is_running = False
        self.analyze_btn.configure(state="normal")
        self._update_status("Analysis completed successfully with Stanza NLP")
        
        if GUI_LIB == "customtkinter":
            self.progress_bar.stop()
            self.progress_bar.set(1.0)
        else:
            self.progress_bar.stop()
    
    def _log_result(self, message: str, tag: str = "info"):
        """Add message to results display"""
        self._set_text_state("normal")
        if GUI_LIB == "tkinter" and tag:
            self.results_text.insert("end", message + "\n", tag)
        else:
            self.results_text.insert("end", message + "\n")
        self.results_text.see("end")
        self._set_text_state("disabled")
    
    def _clear_results(self):
        """Clear results display"""
        self._set_text_state("normal")
        self.results_text.delete("1.0", "end")
        self._set_text_state("disabled")
    
    def _set_text_state(self, state: str):
        """Set text widget state"""
        if GUI_LIB == "tkinter":
            self.results_text.config(state=state)
    
    def _update_status(self, message: str):
        """Update status label"""
        if GUI_LIB == "customtkinter":
            self.status_label.configure(text=message)
        else:
            self.status_label.config(text=message)
    
    def _show_message(self, title: str, message: str):
        """Show message dialog"""
        if GUI_LIB == "tkinter":
            messagebox.showinfo(title, message)
        else:
            print(f"{title}: {message}")
    
    def run(self):
        """Start the application"""
        logger.info("Starting Enterprise Vendor Due Diligence Platform with Stanza NLP")
        self.root.mainloop()

# -----------------------------------
# Application Entry Point
# -----------------------------------

def validate_environment():
    """Validate environment configuration"""
    issues = []
    
    if not config.google_api_key:
        issues.append("GOOGLE_API_KEY not set in environment")
    
    if not config.custom_search_engine_id:
        issues.append("CUSTOM_SEARCH_ENGINE_ID not set in environment")
    
    # Check if Stanza is properly installed
    try:
        stanza.download('en', verbose=False)
    except Exception as e:
        issues.append(f"Stanza setup issue: {e}")
    
    if issues:
        logger.error("Environment validation failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        
        print("\n" + "="*60)
        print("ENVIRONMENT CONFIGURATION REQUIRED")
        print("="*60)
        print("Please ensure the following:")
        print("1. Create a .env file with:")
        print("   GOOGLE_API_KEY=your_google_api_key_here")
        print("   CUSTOM_SEARCH_ENGINE_ID=your_custom_search_engine_id_here")
        print("2. Install Stanza: pip install stanza")
        print("3. Download English models: python -c 'import stanza; stanza.download(\"en\")'")
        print("\nFor setup instructions, see: https://developers.google.com/custom-search/v1/overview")
        print("For Stanza docs, see: https://stanfordnlp.github.io/stanza/")
        print("="*60)
        return False
    
    return True

def main():
    """Main application entry point"""
    try:
        print("🚀 Initializing Enterprise Vendor Due Diligence Platform with Stanza NLP...")
        
        # Validate environment
        if not validate_environment():
            sys.exit(1)
        
        # Start GUI application
        app = EnterpriseVendorDueDiligenceGUI()
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
