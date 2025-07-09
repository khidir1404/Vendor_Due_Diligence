import os
import threading
import queue
import datetime
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from googleapiclient.discovery import build
from tenacity import retry, stop_after_attempt, wait_fixed

try:
    import customtkinter as ctk
    ctk.set_default_color_theme("blue")
    GUI_LIB = "customtkinter"
except ImportError:
    import tkinter as ctk
    from tkinter import ttk, scrolledtext, messagebox
    GUI_LIB = "tkinter"

# Configuration & Constants
load_dotenv() 

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CUSTOM_SEARCH_ENGINE_ID = os.getenv("CUSTOM_SEARCH_ENGINE_ID")

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

# Utility Functions
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_page(url: str) -> str:
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

def google_custom_search(query: str, start: int = 1) -> list[str]:
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    
    try:
        result = service.cse().list(
            q=query,
            cx=CUSTOM_SEARCH_ENGINE_ID,
            start=start,
            num=RESULTS_PER_PAGE
        ).execute()
        
        items = result.get('items', [])
        return [item.get('link') for item in items if item.get('link')]
    except Exception as e:
        print(f"Search error: {e}")
        return []

def generate_text_report(company: str, flagged_links: list, clean_links: list, total_links: int) -> str:
    report = []
    report.append("=" * 60)
    report.append("VENDOR DUE DILIGENCE REPORT")
    report.append("=" * 60)
    report.append(f"Company: {company}")
    report.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Search Engine: Google Custom Search API")
    report.append("")
    
    # Search methodology
    report.append("SEARCH METHODOLOGY:")
    report.append("-" * 20)
    report.append(f"Search Query: \"{company}\" + risk keywords")
    report.append(f"Search Depth: First {MAX_GOOGLE_PAGES} pages of Google results")
    report.append(f"Risk Keywords: Financial crimes, legal issues, regulatory violations")
    report.append("")
    
    # Analysis results
    risk_count = len(flagged_links)
    clean_count = len(clean_links)
    risk_percentage = (risk_count / total_links * 100) if total_links > 0 else 0
    
    report.append("ANALYSIS RESULTS:")
    report.append("-" * 20)
    report.append(f"Total Pages Analyzed: {total_links}")
    report.append(f"Risk Findings: {risk_count} ({risk_percentage:.1f}%)")
    report.append(f"Clean Results: {clean_count} ({(clean_count/total_links*100):.1f}%)")
    report.append("")
    
    # Risk assessment
    if risk_count > 0:
        risk_level = "HIGH RISK" if risk_percentage > 20 else "MEDIUM RISK" if risk_percentage > 10 else "LOW RISK"
    else:
        risk_level = "LOW RISK"
    
    report.append(f"Risk Assessment: {risk_level}")
    report.append("")
    
    # Detailed findings
    if flagged_links:
        report.append("RISK FINDINGS:")
        report.append("-" * 20)
        for i, link in enumerate(flagged_links, 1):
            report.append(f"{i}. RISK: {link['title']}")
            report.append(f"   URL: {link['url']}")
            report.append("")
    
    if clean_links:
        report.append("CLEAN RESULTS:")
        report.append("-" * 20)
        for i, title in enumerate(clean_links, 1):
            report.append(f"{i}. CLEAN: {title}")
    
    report.append("")
    report.append("RECOMMENDATIONS:")
    report.append("-" * 20)
    if risk_count == 0:
        report.append("• No immediate risk indicators found in online search")
        report.append("• Proceed with standard due diligence procedures")
    elif risk_percentage > 20:
        report.append("• HIGH RISK: Extensive risk-related mentions found")
        report.append("• Recommend detailed investigation before proceeding")
        report.append("• Consider engaging specialized due diligence firm")
    elif risk_percentage > 10:
        report.append("• MEDIUM RISK: Some risk indicators identified")
        report.append("• Review flagged items in detail")
        report.append("• Obtain additional clarification from vendor")
    else:
        report.append("• LOW RISK: Minimal risk indicators found")
        report.append("• Proceed with standard verification procedures")
    
    report.append("")
    report.append("=" * 60)
    report.append("END OF REPORT")
    report.append("=" * 60)
    
    return "\n".join(report)

# GUI Application Class
class VendorDueDiligenceApp:
    def __init__(self):
        # Initialize root window
        self.root = ctk.CTk() if GUI_LIB == "customtkinter" else ctk.Tk()
        self.root.title("Vendor Due Diligence - Google Custom Search")
        self.root.geometry("900x700")
        
        # Initialize state variables
        self.result_queue: queue.Queue[str] = queue.Queue()
        self.is_running: bool = False
        self.report_content = ""
        
        self._build_gui()
        
        self.root.after(QUEUE_POLL_INTERVAL, self._process_queue)

    # GUI Build 
    def _build_gui(self):
        # Title label
        title_font = ctk.CTkFont(size=20, weight="bold") if GUI_LIB == "customtkinter" else ("Arial", 16, "bold")
        title_label = ctk.CTkLabel(self.root, text="Vendor Due Diligence ", font=title_font) if GUI_LIB == "customtkinter" else ctk.Label(self.root, text="Vendor Due Diligence ", font=title_font)
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
        self.run_button = button_cls(input_frame, text="Run", command=self._on_run)
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
        self.status_label = label_cls(self.root, text="Ready - Using Google Custom Search API")
        self.status_label.pack(pady=5)

        textbox_cls = ctk.CTkTextbox if GUI_LIB == "customtkinter" else scrolledtext.ScrolledText
        self.results_text = textbox_cls(self.root, wrap="word")
        self.results_text.pack(fill="both", expand=True, padx=20, pady=20)
        
        #color tags
        if GUI_LIB == "tkinter":
            self.results_text.tag_config("risk", foreground="red", background="#ffe6e6")
            self.results_text.tag_config("clean", foreground="green", background="#e6ffe6")
            self.results_text.tag_config("info", foreground="blue")
        
        self._set_text_state("disabled")

    # GUI Utilities
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

    #Event Handlers
    def _on_run(self):
        if self.is_running:
            return  # Prevent multiple runs

        company = self.company_entry.get().strip()
        if not company:
            message = "Company Name: "
            if GUI_LIB == "tkinter":
                messagebox.showwarning("Input Required", message)
            else:
                print(message)
            return

        if not GOOGLE_API_KEY or not CUSTOM_SEARCH_ENGINE_ID:
            error_msg = "Google API credentials not set. Please check your .env file."
            self._update_status(error_msg)
            return

        # UI
        self.is_running = True
        self.run_button.configure(state="disabled")
        self._update_status(f"Running due diligence for '{company}' using Google Custom Search...")
        self._clear_log()
        
        self._log(f" ** VENDOR DUE DILIGENCE REPORT ** ", "info")
        self._log(f"Company: {company}", "info")
        self._log(f"Search Engine: Google Custom Search API", "info")
        self._log(f"Start Time: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}", "info")
        self._log("", "info")

        if GUI_LIB == "customtkinter":
            self.progress.set(0)
        else:
            self.progress.configure(maximum=1.0, value=0)

        threading.Thread(target=self._worker, args=(company,), daemon=True).start()

    # Background
    def _worker(self, company: str):
        try:
            # Collect Google links using Custom Search API
            all_links: list[str] = []
            search_query = f'"{company}" {RISK_KEYWORDS}'
            
            for page in range(MAX_GOOGLE_PAGES):
                start_index = page * RESULTS_PER_PAGE + 1
                new_links = google_custom_search(search_query, start=start_index)
                all_links.extend(new_links)
                self.result_queue.put(f"📄 Retrieved page {page + 1} from Google Custom Search API")
                time.sleep(1)  

            # Remove duplicates
            all_links = list(dict.fromkeys(all_links))
            total_links = len(all_links)
            self.result_queue.put(f"🔍 Collected {total_links} unique links from Google Custom Search.")

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
                        self.result_queue.put((f"🚨 RISK: {title}", "risk"))
                    else:
                        with lock:
                            clean_links.append(title)
                        self.result_queue.put((f"✅ CLEAN: {title}", "clean"))

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

            # Generate final results
            risk_count = len(flagged_links)
            clean_count = len(clean_links)
            
            self.result_queue.put("")
            self.result_queue.put("=== FINAL SUMMARY ===")
            if risk_count > 0:
                self.result_queue.put((f"🚨 RISK DETECTED: {risk_count} pages with risk mentions", "risk"))
                self.result_queue.put((f"✅ CLEAN RESULTS: {clean_count} pages clean", "clean"))
                self.result_queue.put((f"📊 RISK RATIO: {risk_count}/{total_links} ({risk_count/total_links*100:.1f}%)", "info"))
            else:
                self.result_queue.put((f"✅ NO RISK DETECTED: All {clean_count} pages clean", "clean"))
                self.result_queue.put(("📊 RISK RATIO: 0% - Low risk profile", "info"))

            # Generate and save text report
            self.report_content = generate_text_report(company, flagged_links, clean_links, total_links)
            txt_filename = f"VDD_{company}_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt"
            
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(self.report_content)
            
            self.result_queue.put("")
            self.result_queue.put((f"📄 TEXT REPORT SAVED: {txt_filename}", "info"))
            self.result_queue.put(("✨ Report generation completed successfully!", "info"))

        except Exception as e:
            self.result_queue.put(f"❌ Search failed: {str(e)}")
        finally:
            self.result_queue.put("DONE")

    # Queue Processing 
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
                    self._update_status("✅ Completed - Text report generated!")
                    if GUI_LIB == "customtkinter":
                        self.progress.set(1)
                    else:
                        self.progress.configure(value=1)
                else:
                    if isinstance(item, tuple) and len(item) == 2:
                        message, tag = item
                        self._log(message, tag)
                    else:
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

    # Run Application  
    def run(self):
        self.root.mainloop()

# Entrypoint
def main():
    if not GOOGLE_API_KEY or not CUSTOM_SEARCH_ENGINE_ID:
        print("ERROR: Google API credentials not found in environment variables.")
        print("Please create a .env file with:")
        print("GOOGLE_API_KEY=your_api_key_here")
        print("CUSTOM_SEARCH_ENGINE_ID=your_search_engine_id_here")
        return

    app = VendorDueDiligenceApp()
    app.run()

if __name__ == "__main__":
    main()
