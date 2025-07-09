#!/usr/bin/env python3

import os
import sys
import threading
import queue
import datetime
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from serpapi import GoogleSearch
from tenacity import retry, stop_after_attempt, wait_fixed
from fpdf import FPDF

# Attempt to import CustomTkinter; fallback to Tkinter
try:
    import customtkinter as ctk
    ctk.set_default_color_theme("blue")
    GUI_LIB = "customtkinter"
except ImportError:
    import tkinter as ctk
    from tkinter import ttk, scrolledtext, messagebox
    GUI_LIB = "tkinter"

# -----------------------------------
# Configuration & Constants
# -----------------------------------
load_dotenv()  # Load environment variables from .env file
SERP_API_KEY = os.getenv("SERPAPI_KEY")

# Risk keyword block for Google search
RISK_KEYWORDS = (
    "(crime OR bribe OR fraud OR condemn OR accuse OR implicate OR \"grease payment\" "
    "OR \"facilitation payment\" OR litigation OR judicial OR fine OR launder OR OFAC "
    "OR terror OR manipulate OR counterfeit OR traffic OR court OR appeal OR investigate "
    "OR guilty OR illegal OR arrest OR evasion OR sentence OR kickback OR prison OR jail "
    "OR corruption OR corrupt)"
)

MAX_GOOGLE_PAGES = 3  # 3 pages x 10 results = 30 links
RESULTS_PER_PAGE = 10
MAX_THREADS = 10  # Max concurrent scraping threads
HTTP_TIMEOUT = 15  # Timeout per HTTP request (seconds)
QUEUE_POLL_INTERVAL = 100  # GUI queue polling (ms)

# -----------------------------------
# PDF Report Generator Class
# -----------------------------------
class VendorDueDiligencePDF(FPDF):
    def __init__(self, company_name):
        super().__init__()
        self.company_name = company_name
        self.risk_count = 0
        self.clean_count = 0
        
    def header(self):
        # Company logo space (you can add logo here)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(0, 51, 102)  # Dark blue
        self.cell(0, 10, 'VENDOR DUE DILIGENCE REPORT', 0, 1, 'C')
        self.ln(5)
        
        # Company name
        self.set_font('Arial', 'B', 14)
        self.set_text_color(0, 0, 0)  # Black
        self.cell(0, 10, f'Company: {self.company_name}', 0, 1, 'C')
        self.ln(5)
        
        # Report date
        self.set_font('Arial', '', 10)
        self.set_text_color(128, 128, 128)  # Gray
        report_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cell(0, 10, f'Generated: {report_date}', 0, 1, 'C')
        self.ln(10)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        
    def add_section_header(self, title):
        self.ln(5)
        self.set_font('Arial', 'B', 12)
        self.set_text_color(0, 51, 102)  # Dark blue
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)
        
    def add_risk_finding(self, url, title):
        self.risk_count += 1
        self.set_font('Arial', '', 10)
        self.set_text_color(204, 0, 0)  # Red for risk
        self.cell(10, 8, '●', 0, 0, 'L')
        self.set_text_color(0, 0, 0)  # Black for text
        
        # Add risk number
        self.cell(15, 8, f'Risk {self.risk_count}:', 0, 0, 'L')
        
        # Add title (truncate if too long)
        title_text = title[:80] + '...' if len(title) > 80 else title
        self.cell(0, 8, title_text, 0, 1, 'L')
        
        # Add URL on next line with smaller font
        self.set_font('Arial', '', 8)
        self.set_text_color(100, 100, 100)  # Gray
        self.cell(25, 6, '', 0, 0, 'L')  # Indent
        
        # Split URL if too long
        url_text = url[:90] + '...' if len(url) > 90 else url
        self.cell(0, 6, url_text, 0, 1, 'L')
        self.ln(2)
        
    def add_clean_finding(self, title):
        self.clean_count += 1
        self.set_font('Arial', '', 10)
        self.set_text_color(0, 153, 0)  # Green for clean
        self.cell(10, 8, '●', 0, 0, 'L')
        self.set_text_color(0, 0, 0)  # Black for text
        
        # Add clean number and title
        title_text = title[:90] + '...' if len(title) > 90 else title
        self.cell(0, 8, f'Clean {self.clean_count}: {title_text}', 0, 1, 'L')
        self.ln(1)
        
    def add_summary_section(self):
        self.add_page()
        self.add_section_header('EXECUTIVE SUMMARY')
        
        total_analyzed = self.risk_count + self.clean_count
        risk_percentage = (self.risk_count / total_analyzed * 100) if total_analyzed > 0 else 0
        clean_percentage = (self.clean_count / total_analyzed * 100) if total_analyzed > 0 else 0
        
        # Risk assessment box
        if self.risk_count > 0:
            risk_level = "HIGH RISK" if risk_percentage > 20 else "MEDIUM RISK" if risk_percentage > 10 else "LOW RISK"
            risk_color = (204, 0, 0) if risk_percentage > 20 else (255, 165, 0) if risk_percentage > 10 else (255, 255, 0)
        else:
            risk_level = "LOW RISK"
            risk_color = (0, 153, 0)
            
        # Summary statistics
        self.set_font('Arial', 'B', 12)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, 'ANALYSIS RESULTS', 0, 1, 'L')
        self.ln(3)
        
        # Create summary table
        self.set_font('Arial', '', 11)
        
        # Total analyzed
        self.cell(60, 8, 'Total Pages Analyzed:', 0, 0, 'L')
        self.cell(30, 8, str(total_analyzed), 0, 1, 'L')
        
        # Risk findings
        self.set_text_color(204, 0, 0)  # Red
        self.cell(60, 8, 'Risk Findings:', 0, 0, 'L')
        self.cell(30, 8, f'{self.risk_count} ({risk_percentage:.1f}%)', 0, 1, 'L')
        
        # Clean findings
        self.set_text_color(0, 153, 0)  # Green
        self.cell(60, 8, 'Clean Results:', 0, 0, 'L')
        self.cell(30, 8, f'{self.clean_count} ({clean_percentage:.1f}%)', 0, 1, 'L')
        
        # Risk level assessment
        self.ln(5)
        self.set_text_color(0, 0, 0)
        self.set_font('Arial', 'B', 12)
        self.cell(60, 10, 'Risk Assessment:', 0, 0, 'L')
        
        self.set_text_color(*risk_color)
        self.cell(0, 10, risk_level, 0, 1, 'L')
        
        # Recommendations
        self.ln(5)
        self.set_text_color(0, 0, 0)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'RECOMMENDATIONS', 0, 1, 'L')
        self.ln(3)
        
        self.set_font('Arial', '', 10)
        if self.risk_count == 0:
            self.cell(0, 8, '• No immediate risk indicators found in online search', 0, 1, 'L')
            self.cell(0, 8, '• Proceed with standard due diligence procedures', 0, 1, 'L')
        elif risk_percentage > 20:
            self.cell(0, 8, '• HIGH RISK: Extensive risk-related mentions found', 0, 1, 'L')
            self.cell(0, 8, '• Recommend detailed investigation before proceeding', 0, 1, 'L')
            self.cell(0, 8, '• Consider engaging specialized due diligence firm', 0, 1, 'L')
        elif risk_percentage > 10:
            self.cell(0, 8, '• MEDIUM RISK: Some risk indicators identified', 0, 1, 'L')
            self.cell(0, 8, '• Review flagged items in detail', 0, 1, 'L')
            self.cell(0, 8, '• Obtain additional clarification from vendor', 0, 1, 'L')
        else:
            self.cell(0, 8, '• LOW RISK: Minimal risk indicators found', 0, 1, 'L')
            self.cell(0, 8, '• Proceed with standard verification procedures', 0, 1, 'L')

# -----------------------------------
# Utility Functions
# -----------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_page(url: str) -> str:
    """Fetch the webpage content with retry and timeout."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.text

def google_search(company: str, start: int = 0) -> list[str]:
    """Perform Google search via SERP API and return list of links."""
    params = {
        "engine": "google",
        "q": f'"{company}" {RISK_KEYWORDS}',
        "api_key": SERP_API_KEY,
        "start": start,
        "num": RESULTS_PER_PAGE,
    }
    search = GoogleSearch(params)
    result = search.get_dict()
    organic_results = result.get("organic_results", [])
    return [item.get("link") for item in organic_results if item.get("link")]

# -----------------------------------
# GUI Application Class
# -----------------------------------
class VendorDueDiligenceApp:
    def __init__(self):
        # Initialize root window
        self.root = ctk.CTk() if GUI_LIB == "customtkinter" else ctk.Tk()
        self.root.title("Vendor Due Diligence")
        self.root.geometry("900x700")
        
        # Initialize state variables
        self.result_queue: queue.Queue[str] = queue.Queue()
        self.is_running: bool = False
        self.pdf_generator = None
        
        # Build GUI components
        self._build_gui()
        
        # Start queue polling
        self.root.after(QUEUE_POLL_INTERVAL, self._process_queue)

    # -------------------- GUI Build --------------------
    def _build_gui(self):
        # Title label
        title_font = ctk.CTkFont(size=20, weight="bold") if GUI_LIB == "customtkinter" else ("Arial", 16, "bold")
        title_label = ctk.CTkLabel(self.root, text="Vendor Due Diligence Checker", font=title_font) if GUI_LIB == "customtkinter" else ctk.Label(self.root, text="Vendor Due Diligence Checker", font=title_font)
        title_label.pack(pady=10)

        # Input frame
        frame_cls = ctk.CTkFrame if GUI_LIB == "customtkinter" else ctk.Frame
        input_frame = frame_cls(self.root)
        input_frame.pack(fill="x", padx=20, pady=10)

        # Company name entry
        label_cls = ctk.CTkLabel if GUI_LIB == "customtkinter" else ctk.Label
        label_cls(input_frame, text="Company Name:").pack(side="left", padx=(0, 10))

        entry_cls = ctk.CTkEntry if GUI_LIB == "customtkinter" else ctk.Entry
        self.company_entry = entry_cls(input_frame, placeholder_text="Enter company name" if GUI_LIB == "customtkinter" else None, width=300)
        self.company_entry.pack(side="left", padx=(0, 10))

        # Run button
        button_cls = ctk.CTkButton if GUI_LIB == "customtkinter" else ctk.Button
        self.run_button = button_cls(input_frame, text="Run Due Diligence", command=self._on_run)
        self.run_button.pack(side="left")

        # Progress bar
        if GUI_LIB == "customtkinter":
            self.progress = ctk.CTkProgressBar(self.root)
            self.progress.pack(fill="x", padx=20, pady=10)
            self.progress.set(0)
        else:
            self.progress = ttk.Progressbar(self.root, mode="determinate")
            self.progress.pack(fill="x", padx=20, pady=10)

        # Status label
        self.status_label = label_cls(self.root, text="Ready")
        self.status_label.pack(pady=5)

        # Results textbox with color tags
        textbox_cls = ctk.CTkTextbox if GUI_LIB == "customtkinter" else scrolledtext.ScrolledText
        self.results_text = textbox_cls(self.root, wrap="word")
        self.results_text.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Configure color tags for results display
        if GUI_LIB == "tkinter":
            self.results_text.tag_config("risk", foreground="red", background="#ffe6e6")
            self.results_text.tag_config("clean", foreground="green", background="#e6ffe6")
            self.results_text.tag_config("info", foreground="blue")
        
        self._set_text_state("disabled")

    # -------------------- GUI Utilities --------------------
    def _log(self, msg: str, tag: str = ""):
        self._set_text_state("normal")
        if GUI_LIB == "tkinter" and tag:
            self.results_text.insert("end", msg + "\n", tag)
        else:
            self.results_text.insert("end", msg + "\n")
        self.results_text.see("end")
        self._set_text_state("disabled")

    def _clear_log(self):
        self._set_text_state("normal")
        self.results_text.delete("1.0", "end")
        self._set_text_state("disabled")

    def _set_text_state(self, state: str):
        if GUI_LIB == "tkinter":
            self.results_text.config(state=state)

    def _update_status(self, text: str):
        if GUI_LIB == "customtkinter":
            self.status_label.configure(text=text)
        else:
            self.status_label.config(text=text)

    # -------------------- Event Handlers --------------------
    def _on_run(self):
        if self.is_running:
            return  # Prevent multiple runs

        company = self.company_entry.get().strip()
        if not company:
            message = "Please enter a company name."
            if GUI_LIB == "tkinter":
                messagebox.showwarning("Input Required", message)
            else:
                print(message)
            return

        if not SERP_API_KEY:
            error_msg = "SERPAPI_KEY not set. Please create a .env file with your key."
            self._update_status(error_msg)
            return

        # Prepare UI
        self.is_running = True
        self.run_button.configure(state="disabled")
        self._update_status(f"Running due diligence for '{company}'...")
        self._clear_log()
        
        # Initialize PDF generator
        self.pdf_generator = VendorDueDiligencePDF(company)
        
        self._log(f"=== Vendor Due Diligence Report ===", "info")
        self._log(f"Company: {company}", "info")
        self._log(f"Start Time: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}", "info")
        self._log("", "info")

        if GUI_LIB == "customtkinter":
            self.progress.set(0)
        else:
            self.progress.configure(maximum=1.0, value=0)

        # Start background thread
        threading.Thread(target=self._worker, args=(company,), daemon=True).start()

    # -------------------- Background Processing --------------------
    def _worker(self, company: str):
        try:
            # Add first page to PDF
            self.pdf_generator.add_page()
            self.pdf_generator.add_section_header('SEARCH METHODOLOGY')
            self.pdf_generator.set_font('Arial', '', 10)
            self.pdf_generator.cell(0, 8, f'Search Query: "{company}" + risk keywords', 0, 1, 'L')
            self.pdf_generator.cell(0, 8, f'Search Depth: First {MAX_GOOGLE_PAGES} pages of Google results', 0, 1, 'L')
            self.pdf_generator.cell(0, 8, f'Risk Keywords: Financial crimes, legal issues, regulatory violations', 0, 1, 'L')
            self.pdf_generator.ln(5)

            # Collect Google links
            all_links: list[str] = []
            for page in range(MAX_GOOGLE_PAGES):
                start_index = page * RESULTS_PER_PAGE
                new_links = google_search(company, start=start_index)
                all_links.extend(new_links)
                time.sleep(1)  # Respect rate limits

            # Remove duplicates
            all_links = list(dict.fromkeys(all_links))
            total_links = len(all_links)
            self.result_queue.put(f"🔍 Collected {total_links} unique links from Google.")

            # Add findings section to PDF
            self.pdf_generator.add_section_header('DETAILED FINDINGS')

            # Analyze links with multithreading
            flagged_links: list[dict] = []
            clean_links: list[str] = []
            progress_count = 0
            lock = threading.Lock()

            def analyze(url: str):
                nonlocal progress_count
                try:
                    html = fetch_page(url)
                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.title.string.strip() if soup.title else urlparse(url).netloc
                    text_content = soup.get_text(" ", strip=True).lower()

                    if company.lower() in text_content:
                        with lock:
                            flagged_links.append({"url": url, "title": title})
                            self.pdf_generator.add_risk_finding(url, title)
                        self.result_queue.put(f"🚨 RISK: {title}", "risk")
                    else:
                        with lock:
                            clean_links.append(title)
                            self.pdf_generator.add_clean_finding(title)
                        self.result_queue.put(f"✅ CLEAN: {title}", "clean")

                except Exception as exc:
                    self.result_queue.put(f"⚠️ ERROR: {url}: {exc}")

                finally:
                    with lock:
                        progress_count += 1
                        progress = progress_count / total_links if total_links else 1
                        self.result_queue.put(("PROGRESS", progress))

            threads: list[threading.Thread] = []
            for link in all_links:
                t = threading.Thread(target=analyze, args=(link,), daemon=True)
                t.start()
                threads.append(t)
                if len(threads) >= MAX_THREADS:
                    for t in threads:
                        t.join()
                    threads = []

            # Join any remaining threads
            for t in threads:
                t.join()

            # Add summary section to PDF
            self.pdf_generator.add_summary_section()

            # Generate final results
            risk_count = len(flagged_links)
            clean_count = len(clean_links)
            
            self.result_queue.put("")
            self.result_queue.put("=== FINAL SUMMARY ===")
            if risk_count > 0:
                self.result_queue.put(f"🚨 RISK DETECTED: {risk_count} pages with risk mentions", "risk")
                self.result_queue.put(f"✅ CLEAN RESULTS: {clean_count} pages clean", "clean")
                self.result_queue.put(f"📊 RISK RATIO: {risk_count}/{total_links} ({risk_count/total_links*100:.1f}%)", "info")
            else:
                self.result_queue.put(f"✅ NO RISK DETECTED: All {clean_count} pages clean", "clean")
                self.result_queue.put("📊 RISK RATIO: 0% - Low risk profile", "info")

            # Save PDF report
            pdf_filename = f"VDD_{company}_{datetime.datetime.now():%Y%m%d_%H%M%S}.pdf"
            self.pdf_generator.output(pdf_filename)
            
            self.result_queue.put("")
            self.result_queue.put(f"📄 PDF REPORT SAVED: {pdf_filename}", "info")
            self.result_queue.put("✨ Report generation completed successfully!", "info")

        except Exception as e:
            self.result_queue.put(f"❌ Search failed: {str(e)}")
        finally:
            self.result_queue.put("DONE")

    # -------------------- Queue Processing --------------------
    def _process_queue(self):
        try:
            while True:
                item = self.result_queue.get_nowait()
                
                if isinstance(item, tuple) and item[0] == "PROGRESS":
                    progress_value = item[1]
                    if GUI_LIB == "customtkinter":
                        self.progress.set(progress_value)
                    else:
                        self.progress.configure(value=progress_value)
                elif item == "DONE":
                    self.is_running = False
                    self.run_button.configure(state="normal")
                    self._update_status("✅ Completed - PDF report generated!")
                    if GUI_LIB == "customtkinter":
                        self.progress.set(1)
                    else:
                        self.progress.configure(value=1)
                else:
                    # Check if item is a tuple with tag
                    if isinstance(item, tuple) and len(item) == 2:
                        message, tag = item
                        self._log(message, tag)
                    else:
                        # Determine tag based on content
                        message = str(item)
                        if "🚨" in message or "RISK:" in message:
                            tag = "risk"
                        elif "✅" in message or "CLEAN:" in message:
                            tag = "clean"
                        else:
                            tag = "info"
                        self._log(message, tag)
        except queue.Empty:
            pass

        self.root.after(QUEUE_POLL_INTERVAL, self._process_queue)

    # -------------------- Run Application --------------------
    def run(self):
        self.root.mainloop()

# -----------------------------------
# Entrypoint
# -----------------------------------
def main():
    if not SERP_API_KEY:
        print("ERROR: SERPAPI_KEY not found in environment variables. Create a .env file with your key.")
        sys.exit(1)

    app = VendorDueDiligenceApp()
    app.run()

if __name__ == "__main__":
    main()
