# Polite Scraper — Books to Scrape

A polite, resilient web scraping pipeline built in Python to collect, normalize, validate, and audit book data from the Books to Scrape practice sandbox.

---

## 🎯 Target Classification

- **Target Site**: [Books to Scrape](https://books.toscrape.com/)
- **Site Type**: Sandbox (A practice website built specifically for web scraping practice).
- **Scope**: First 3 catalogue pages only (60 book items total).
- **Data Fields Collected**: Title, Product URL, Price Text, Price GBP (normalized), Availability, Star Rating, Description, Source Page (provenance), and Fetched At (timestamp).
- **Robots.txt Status**: `no robots file found` (HTTP 404 on `https://books.toscrape.com/robots.txt`).

> **Mandatory Compliance Statement**:
> I will not reuse this code on another site without checking its rules and terms first.

---

## 🛠️ Setup & Running

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run scraper pipeline
python src/main.py