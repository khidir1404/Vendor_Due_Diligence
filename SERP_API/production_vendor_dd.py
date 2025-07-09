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

try:
    import customtkinter as ctk
    ctk.set_default_color_theme("blue")
    GUI_LIB = "customtkinter"
except ImportError:
    import tkinter as ctk
    from tkinter import ttk, scrolledtext, messagebox
    GUI_LIB = "tkinter"

# Configuration & Constants
load_dotenv()  # Load environment variables from .env file
SERP_API_KEY = os.getenv("SERPAPI_KEY")

RISK_KEYWORDS = (
    "& (crime OR bribe OR fraud OR condemn OR accuse OR implicate OR \"grease payment\" "
    "OR \"facilitation payment\" OR litigation OR judicial OR fine OR launder OR OFAC "
    "OR terror OR manipulate OR counterfeit OR traffic OR court OR appeal OR investigate "
    "OR guilty OR illegal OR arrest OR evasion OR sentence OR kickback OR prison OR jail "
    "OR corruption OR corrupt)"
)

MAX_GOOGLE_PAGES = 3  # 3 pages x 10 results = 30 links
RESULTS_PER_PAGE = 10
MAX_THREADS = 10       # Max concurrent scraping threads
HTTP_TIMEOUT = 15      # Timeout per HTTP request (seconds)
QUEUE_POLL_INTERVAL = 100  # GUI queue polling (ms)

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


def google_search(company: str, start: int = 0) -> list[str]:
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

# GUI Application Class

class VendorDueDiligenceApp:
    def __init__(self):
        # Initialize root window
        self.root = ctk.CTk() if GUI_LIB == "customtkinter" else ctk.Tk()
        self.root.title("Vendor Due Diligence")
        self.root.geometry("900x700")

        self.result_queue: queue.Queue[str] = queue.Queue()
        self.is_running: bool = False

        self._build_gui()

        self.root.after(QUEUE_POLL_INTERVAL, self._process_queue)

    # -------------------- GUI Build --------------------
    def _build_gui(self):
        title_font = ctk.CTkFont(size=20, weight="bold") if GUI_LIB == "customtkinter" else ("Arial", 16, "bold")
        title_label = ctk.CTkLabel(self.root, text="Vendor Due Diligence", font=title_font) if GUI_LIB == "customtkinter" else ctk.Label(self.root, text="Vendor Due Diligence Checker", font=title_font)
        title_label.pack(pady=10)

        frame_cls = ctk.CTkFrame if GUI_LIB == "customtkinter" else ctk.Frame
        input_frame = frame_cls(self.root)
        input_frame.pack(fill="x", padx=20, pady=10)

        label_cls = ctk.CTkLabel if GUI_LIB == "customtkinter" else ctk.Label
        label_cls(input_frame, text="Company Name:").pack(side="left", padx=(0, 10))

        entry_cls = ctk.CTkEntry if GUI_LIB == "customtkinter" else ctk.Entry
        self.company_entry = entry_cls(input_frame, placeholder_text="Enter company name" if GUI_LIB == "customtkinter" else None, width=300)
        self.company_entry.pack(side="left", padx=(0, 10))

        button_cls = ctk.CTkButton if GUI_LIB == "customtkinter" else ctk.Button
        self.run_button = button_cls(input_frame, text="Run Due Diligence", command=self._on_run)
        self.run_button.pack(side="left")

        if GUI_LIB == "customtkinter":
            self.progress = ctk.CTkProgressBar(self.root)
            self.progress.pack(fill="x", padx=20, pady=10)
            self.progress.set(0)
        else:
            self.progress = ttk.Progressbar(self.root, mode="determinate")
            self.progress.pack(fill="x", padx=20, pady=10)

        self.status_label = label_cls(self.root, text="Ready")
        self.status_label.pack(pady=5)

        textbox_cls = ctk.CTkTextbox if GUI_LIB == "customtkinter" else scrolledtext.ScrolledText
        self.results_text = textbox_cls(self.root, wrap="word")
        self.results_text.pack(fill="both", expand=True, padx=20, pady=20)
        self._set_text_state("disabled")

    # -------------------- GUI Utilities --------------------
    def _log(self, msg: str):
        self._set_text_state("normal")
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
            return 
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

        self.is_running = True
        self.run_button.configure(state="disabled")
        self._update_status(f"Running due diligence for '{company}'...")
        self._clear_log()
        self._log(f"=== Vendor Due Diligence Report ===\nCompany: {company}\nStart Time: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
        if GUI_LIB == "customtkinter":
            self.progress.set(0)
        else:
            self.progress.configure(maximum=1.0, value=0)

        threading.Thread(target=self._worker, args=(company,), daemon=True).start()

    # -------------------- Background Processing --------------------
    def _worker(self, company: str):
        try:
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
            self.result_queue.put(f"Collected {total_links} unique links from Google.\n")

            # Analyze links with multithreading
            flagged_links: list[str] = []
            progress_count = 0
            lock = threading.Lock()

            def analyze(url: str):
                nonlocal progress_count
                result_flagged = False
                try:
                    html = fetch_page(url)
                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.title.string.strip() if soup.title else urlparse(url).netloc
                    text_content = soup.get_text(" ", strip=True).lower()
                    if company.lower() in text_content:
                        result_flagged = True
                        lock.acquire()
                        flagged_links.append(f"{title} -> {url}")
                        lock.release()
                        self.result_queue.put(f"[RISK] {title} -> {url}")
                    else:
                        self.result_queue.put(f"[CLEAN] {title}")
                except Exception as exc:
                    self.result_queue.put(f"[ERROR] {url}: {exc}")
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

            # Summary
            self.result_queue.put("\n=== SUMMARY ===")
            if flagged_links:
                self.result_queue.put(f"RISK FOUND: {len(flagged_links)} flagged pages.")
                for item in flagged_links:
                    self.result_queue.put(f"- {item}")
            else:
                self.result_queue.put("No risk-related mentions detected.")

            # Save report
            report_filename = f"VDD_{company}_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt"
            self._save_report(report_filename)
            self.result_queue.put(f"\nReport saved as {report_filename}\n")
        except Exception as e:
            self.result_queue.put(f"Unhandled error: {e}")
        finally:
            self.result_queue.put("DONE")

    # -------------------- Report Saving --------------------
    def _save_report(self, filename: str):
        text_content = self.results_text.get("1.0", "end") if GUI_LIB == "customtkinter" else self.results_text.get("1.0", "end")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(text_content)

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
                    self._update_status("Completed.")
                    if GUI_LIB == "customtkinter":
                        self.progress.set(1)
                    else:
                        self.progress.configure(value=1)
                else:
                    self._log(str(item))
        except queue.Empty:
            pass
        self.root.after(QUEUE_POLL_INTERVAL, self._process_queue)

    # -------------------- Run Application --------------------
    def run(self):
        self.root.mainloop()


# Entrypoint

def main():
    if not SERP_API_KEY:
        print("ERROR: SERPAPI_KEY not found in environment variables. Create a .env file with your key.")
        sys.exit(1)
    app = VendorDueDiligenceApp()
    app.run()


if __name__ == "__main__":
    main()


# LINKS 
# https://serpapi.com/dashboard  - GITHUB LOGIN 
