# Vendor Due Diligence Platform

A robust, production-ready Python application for automated vendor due diligence. This project provides **two fully supported builds**—one using the Google Custom Search API and one using SERP API. Both versions offer contextual risk analysis, PDF archiving of web evidence, and detailed compliance-ready reports with a modern GUI.

## 🚀 Features

- **Automated Search**: Scan the first 3 pages of Google results for risk signals using either Google Custom Search API or SERP API.
- **Contextual Risk Analysis**: NLP-powered flagging of links where the company is contextually associated with risk keywords.
- **Web-to-PDF Archival**: Save a PDF snapshot of every analyzed link in a dedicated folder for audit/compliance.
- **Comprehensive Reports**: Generate a detailed `.txt` report with risk findings, scoring, recommendations, and links to all PDFs.
- **Modern GUI**: CustomTkinter-based interface with color-coded results and real-time progress.
- **Enterprise Security**: All credentials/settings managed via `.env` file; logs and artifacts organized for auditability.
- **Scalable & Maintainable**: Async processing, modular code, robust error handling, and ready for real-world deployment.


## 🔑 Environment Configuration

Create a `.env` file in the project root.

### For Google Custom Search API Build (`main.py`):

```env
GOOGLE_API_KEY=your_google_api_key_here
CUSTOM_SEARCH_ENGINE_ID=your_custom_search_engine_id_here
```

- Get your API key from [Google Cloud Console](https://console.cloud.google.com/).
- Get your Search Engine ID from [Google Custom Search Engine](https://cse.google.com/cse/).

### For SERP API Build (`production_vendor_dd.py`):

```env
SERPAPI_KEY=your_serp_api_key_here
```

- Get your API key from [SERP API Dashboard](https://serpapi.com/dashboard).

## 🏗️ Running the Application

### Google Custom Search API Build

```bash
python main.py
```

### SERP API Build

```bash
python production_vendor_dd.py
```

## 🖥️ Usage

1. **Enter the company name** in the GUI.
2. **Click "Start Analysis"**.
3. The app will:
   - Search Google for risk-related news and documents.
   - Download and analyze each link for contextual risk.
   - Save a PDF of each page in `vendor_intelligence/pdf_archive/`.
   - Generate a detailed text report in `vendor_intelligence/reports/`.
4. **Review the results** in the GUI and open the generated `.txt` report for a summary and recommendations.

## 📝 Output Structure

- `vendor_intelligence/pdf_archive/` — PDF snapshots of all analyzed links.
- `vendor_intelligence/reports/` — Text reports for each company.
- `vendor_intelligence/logs/` — Application and error logs.

## ⚡ Risk Analysis Approach

- **NLP Contextual Matching**: Flags a link as "risk" only if the company is mentioned in a context with risk keywords (e.g., lawsuits, fines, fraud, breaches).
- **Entity Extraction**: Named entities and context snippets are included in the report for human review.
- **Scoring**: Each report summarizes the number of risk vs. clean findings and provides a risk level (Minimal/Low/Medium/High).

## 🧩 Dependencies

- [Stanford Stanza](https://stanfordnlp.github.io/stanza/) (Google API build)
- [Google API Python Client](https://github.com/googleapis/google-api-python-client)
- [SERP API Python Client](https://github.com/serpapi/google-search-results-python) (SERP API build)
- [Playwright](https://playwright.dev/python/)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)
- [Tenacity](https://tenacity.readthedocs.io/)
- [python-dotenv](https://github.com/theskumar/python-dotenv)
- [aiofiles](https://github.com/Tinche/aiofiles)
- [requests](https://docs.python-requests.org/)

## 🩺 Troubleshooting

- **Stanza Model Issues**: If you see errors about missing models, run `python -c "import stanza; stanza.download('en')"` in your virtual environment.
- **Playwright Browser Issues**: If PDF generation fails, ensure Chromium is installed with `playwright install chromium`.
- **API Errors**: Check your `.env` file and API quota.
- **GUI Issues**: The app falls back to Tkinter if CustomTkinter is not available.

## 🔒 Security & Compliance

- **Credentials** are never hardcoded—always use `.env`.
- **All artifacts** (PDFs, logs, reports) are stored in organized, reviewable folders.
- **Comprehensive logs** for audit and debugging.

## 📝 License

This project is released under the MIT License.

## 🤝 Contribution

Pull requests and issues are welcome! Please open an issue for feature requests or bug reports.

## 🙏 Acknowledgements

- Stanford NLP Group for Stanza
- Google for Custom Search API
- SERP API for search infrastructure
- Microsoft for Playwright
- The open-source Python community

## 📬 Contact

For support or enterprise inquiries, contact [vasishtavj@gmail.com].
