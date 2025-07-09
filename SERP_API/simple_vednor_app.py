#!/usr/bin/env python3
"""
SIMPLIFIED Vendor Due Diligence Application
This version removes complex features to help identify issues
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import queue
import datetime

# Try to load dotenv - if it fails, ask for API key directly
try:
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv('SERPAPI_KEY')
except ImportError:
    print("python-dotenv not installed - will ask for API key directly")
    API_KEY = None

# Try to import SERP API
try:
    from serpapi import GoogleSearch
    SERPAPI_AVAILABLE = True
except ImportError:
    print("google-search-results not installed - using mock search")
    SERPAPI_AVAILABLE = False

class SimpleVDDApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Vendor Due Diligence - Simple Version")
        self.root.geometry("800x600")

        # Get API key if not available
        if not API_KEY and SERPAPI_AVAILABLE:
            self.api_key = self.get_api_key()
        else:
            self.api_key = API_KEY

        self.result_queue = queue.Queue()
        self.setup_gui()
        self.check_queue()

    def get_api_key(self):
        """Get API key from user if not in .env file"""
        root = tk.Tk()
        root.withdraw()  # Hide the main window

        api_key = tk.simpledialog.askstring(
            "API Key Required", 
            "Enter your SERP API key:",
            show='*'
        )
        root.destroy()
        return api_key

    def setup_gui(self):
        """Create simple GUI"""
        # Title
        title = tk.Label(self.root, text="Vendor Due Diligence Checker", 
                        font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Input frame
        input_frame = tk.Frame(self.root)
        input_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(input_frame, text="Company Name:").pack(side="left")
        self.company_entry = tk.Entry(input_frame, width=30)
        self.company_entry.pack(side="left", padx=10)

        self.search_btn = tk.Button(input_frame, text="Search", 
                                   command=self.start_search, bg="lightblue")
        self.search_btn.pack(side="left")

        # Status
        self.status_label = tk.Label(self.root, text="Ready", fg="green")
        self.status_label.pack(pady=5)

        # Results
        self.results_text = scrolledtext.ScrolledText(self.root, wrap="word")
        self.results_text.pack(fill="both", expand=True, padx=20, pady=20)

        # Test button
        test_btn = tk.Button(self.root, text="Test Application", 
                           command=self.test_app, bg="lightgreen")
        test_btn.pack(pady=5)

    def start_search(self):
        """Start the search process"""
        company_name = self.company_entry.get().strip()
        if not company_name:
            messagebox.showwarning("Input Required", "Please enter a company name")
            return

        self.status_label.config(text=f"Searching for: {company_name}", fg="blue")
        self.search_btn.config(state="disabled")
        self.results_text.delete("1.0", tk.END)

        # Start search in thread
        thread = threading.Thread(target=self.search_worker, args=(company_name,))
        thread.daemon = True
        thread.start()

    def search_worker(self, company_name):
        """Simple search worker"""
        try:
            self.result_queue.put(f"=== VENDOR DUE DILIGENCE REPORT ===\n")
            self.result_queue.put(f"Company: {company_name}\n")
            self.result_queue.put(f"Started: {datetime.datetime.now()}\n")
            self.result_queue.put("="*50 + "\n\n")

            if SERPAPI_AVAILABLE and self.api_key:
                # Real search
                self.result_queue.put("🔍 Performing real SERP API search...\n")

                try:
                    params = {
                        "engine": "google",
                        "q": f'"{company_name}" (fraud OR corruption OR crime)',
                        "api_key": self.api_key,
                        "num": 5  # Just 5 results for testing
                    }

                    search = GoogleSearch(params)
                    results = search.get_dict()

                    organic_results = results.get("organic_results", [])

                    if organic_results:
                        self.result_queue.put(f"📄 Found {len(organic_results)} search results:\n\n")

                        for i, result in enumerate(organic_results, 1):
                            title = result.get("title", "No title")
                            link = result.get("link", "No link")
                            snippet = result.get("snippet", "No snippet")

                            self.result_queue.put(f"{i}. {title}\n")
                            self.result_queue.put(f"   URL: {link}\n")
                            self.result_queue.put(f"   Snippet: {snippet}\n\n")
                    else:
                        self.result_queue.put("No search results found.\n")

                except Exception as e:
                    self.result_queue.put(f"❌ SERP API Error: {str(e)}\n")
                    self.result_queue.put("This might be an API key issue or quota exceeded.\n")

            else:
                # Mock search for testing
                self.result_queue.put("🔍 Running mock search (SERP API not available)...\n")
                self.result_queue.put("📄 Mock Results:\n\n")

                mock_results = [
                    f"1. {company_name} - Company Profile",
                    f"2. {company_name} - Recent News",
                    f"3. {company_name} - Financial Reports",
                    f"4. {company_name} - Industry Analysis",
                    f"5. {company_name} - Regulatory Filings"
                ]

                for result in mock_results:
                    self.result_queue.put(result + "\n")
                    self.result_queue.put("   URL: https://example.com/mock-url\n")
                    self.result_queue.put("   Status: Mock data for testing\n\n")

            self.result_queue.put("\n" + "="*50)
            self.result_queue.put("\n✅ Search completed successfully!")

        except Exception as e:
            self.result_queue.put(f"❌ Unexpected error: {str(e)}")
        finally:
            self.result_queue.put("SEARCH_COMPLETE")

    def test_app(self):
        """Test basic application functionality"""
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert(tk.END, "🧪 APPLICATION TEST\n")
        self.results_text.insert(tk.END, "="*30 + "\n\n")

        # Test Python version
        self.results_text.insert(tk.END, f"Python version: {sys.version}\n")

        # Test imports
        try:
            import requests
            self.results_text.insert(tk.END, "✅ requests - OK\n")
        except ImportError:
            self.results_text.insert(tk.END, "❌ requests - MISSING\n")

        try:
            from dotenv import load_dotenv
            self.results_text.insert(tk.END, "✅ python-dotenv - OK\n")
        except ImportError:
            self.results_text.insert(tk.END, "❌ python-dotenv - MISSING\n")

        try:
            from serpapi import GoogleSearch
            self.results_text.insert(tk.END, "✅ google-search-results - OK\n")
        except ImportError:
            self.results_text.insert(tk.END, "❌ google-search-results - MISSING\n")

        # Test .env file
        if os.path.exists('.env'):
            self.results_text.insert(tk.END, "✅ .env file - EXISTS\n")
        else:
            self.results_text.insert(tk.END, "❌ .env file - MISSING\n")

        # Test API key
        if self.api_key:
            self.results_text.insert(tk.END, f"✅ API key - LOADED ({len(self.api_key)} chars)\n")
        else:
            self.results_text.insert(tk.END, "❌ API key - MISSING\n")

        self.results_text.insert(tk.END, "\n🎉 Test completed!\n")

    def check_queue(self):
        """Check for messages from worker thread"""
        try:
            while True:
                message = self.result_queue.get_nowait()

                if message == "SEARCH_COMPLETE":
                    self.status_label.config(text="Search completed!", fg="green")
                    self.search_btn.config(state="normal")
                else:
                    self.results_text.insert(tk.END, message)
                    self.results_text.see(tk.END)

        except queue.Empty:
            pass

        self.root.after(100, self.check_queue)

    def run(self):
        """Start the application"""
        print("🚀 Starting Simple Vendor Due Diligence App...")
        self.root.mainloop()

def main():
    """Main function with error handling"""
    try:
        app = SimpleVDDApp()
        app.run()
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        print("\nTroubleshooting steps:")
        print("1. Run diagnostic_check.py first")
        print("2. Install missing packages")
        print("3. Check your .env file")
        print("4. Verify your Python version")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
