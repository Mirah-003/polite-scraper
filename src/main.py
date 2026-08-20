# ==========================================
# FLYRANK AI — ASSIGNMENT BE-05: THE POLITE SCRAPER
# ==========================================

# ==========================================
# TODO 0 — Imports & Setup
# ==========================================

import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Define polite User-Agent identification header
USER_AGENT = "FlyRankInternship-A9/1.0 (+https://github.com/Mirah-003/polite-scraper)"
HEADERS = {"User-Agent": USER_AGENT}

# Create required directories
os.makedirs("cache", exist_ok=True)
os.makedirs("output", exist_ok=True)

# ==========================================
# TODO 1 — Fetch Once, Cache Once (HTTP Fetcher)
# ==========================================

def fetch_page(url: str, cache_filename: str, timeout: int = 10) -> tuple[str, bool]:
    """
    Politely fetches a web page or loads it from local disk cache.
    Returns: (html_content, is_cache_hit)
    """
    cache_filepath = os.path.join("cache", cache_filename)
    
    # 1. Disk Cache Check
    if os.path.exists(cache_filepath):
        with open(cache_filepath, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"CACHE HIT | File: {cache_filename} | Size: {len(content)} bytes")
        return content, True
    # 2. Network Fetch (If missing from cache)
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        
        if response.status_code != 200:
            raise RuntimeError(f"HTTP Error {response.status_code} when fetching {url}")
            
        content = response.text
        
        with open(cache_filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"FETCH     | URL: {url} | Size: {len(content)} bytes")
        return content, False
    except requests.RequestException as e:
        raise RuntimeError(f"Network failure for {url}: {e}")


# ==========================================
# TODO 2 — Find All Three Pages (Pagination Crawler)
# ==========================================

def discover_book_urls(start_url: str, max_pages: int = 3) -> list[dict]:
    """
    Crawls catalogue pagination starting from start_url up to max_pages.
    Extracts book detail links, resolves them to absolute URLs using urljoin,
    and returns a list of dictionaries with product_url and source_page.
    """
    discovered_books: list[dict] = []
    current_url = start_url
    page_count = 0
    while current_url and page_count < max_pages:
        page_count += 1
        cache_file = f"catalogue-page-{page_count}.html"
        
        # Fetch page HTML
        html_content, is_cache_hit = fetch_page(url=current_url, cache_filename=cache_file)
        
        # Apply 0.5s politeness delay ONLY if fetched over network
        if not is_cache_hit:
            time.sleep(0.5)
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        # Extract book links from article.product_pod containers
        articles = soup.find_all("article", class_="product_pod")

        for article in articles:
            h3_tag = article.find("h3")
            if h3_tag and h3_tag.find("a"):
                relative_href = h3_tag.find("a")["href"]
                # Safe URL resolution using urljoin
                abs_product_url = urljoin(current_url, relative_href)
                
                discovered_books.append({
                    "product_url": abs_product_url,
                    "source_page": current_url
                })

        # Follow pagination "next" button if present
        next_li = soup.find("li", class_="next")
        if next_li and next_li.find("a"):
            next_relative_href = next_li.find("a")["href"]
            current_url = urljoin(current_url, next_relative_href)
        else:
            current_url = None

    # Deduplicate books while preserving order
    seen_urls = set()
    unique_books = []
    for book in discovered_books:
        if book["product_url"] not in seen_urls:
            seen_urls.add(book["product_url"])
            unique_books.append(book)
    print(f"\nCHECKPOINT — catalogue_pages={page_count}, discovered={len(discovered_books)}, unique_urls={len(unique_books)}")
    return unique_books

# ==========================================
# TODO 3 — Extract Raw Book Records
# ==========================================

# PSEUDOCODE & VISUAL MECHANICS:
# Function parse_book_detail(book_info: dict) -> dict:
#   """
#   Extracts 8 raw fields + provenance receipts (source_page, fetched_at).
#   Handles missing description cleanly as None instead of crashing.
#   """
#   Generate cache_filename = "detail-" + slug_from_url + ".html"
#   Fetch detail HTML via fetch_page()
#   Parse HTML with BeautifulSoup
#
#   Locate product container (div.product_main):
#     title = h1 text
#     price_text = p.price_color text (e.g. "£51.77")
#     availability_text = p.instock.availability text (e.g. "In stock (22 available)")
#     rating_text = p.star-rating class name (e.g. "Three")
#
#   Locate description:
#     Find #product_description tag -> sibling <p> text, or None if missing.
#
#   Return raw_record dict with 8 fields:
#     {title, product_url, price_text, availability_text, rating_text, description, source_page, fetched_at}


# ==========================================
# TODO 4 — Pydantic Schema & Normalization
# ==========================================

# PSEUDOCODE & VISUAL MECHANICS:
# Define Pydantic Schema:
# Class BookRecord(BaseModel):
#     title: str
#     product_url: str
#     price_text: str
#     price_gbp: float          # Normalized numeric value
#     availability_text: str
#     rating_text: str
#     description: Optional[str] = None
#     source_page: str
#     fetched_at: str

# Function normalize_record(raw_record: dict) -> BookRecord:
#   price_numeric = float(raw_record["price_text"].replace("£", "").strip())
#   normalized_dict = raw_record.copy()
#   normalized_dict["price_gbp"] = price_numeric
#   Return BookRecord(**normalized_dict)


# ==========================================
# TODO 5 — Fault Tolerance & Report Generation
# ==========================================

# PSEUDOCODE & VISUAL MECHANICS:
# Main Pipeline Runner:
#   Track counters: pages_fetched, cache_hits, valid_count, invalid_count, failed_count
#   Start timer: start_time = time.time()
#
#   For each book_info in discovered_books:
#     Try:
#       Parse detail page
#       Normalize and validate against BookRecord
#       Save to valid_books list
#     Except Exception as e:
#       If 5xx/Timeout -> retry once after 1s
#       Else -> log to error_records list, increment failed_count
#
#   Write valid_books to output/books.json
#   Write error_records to output/errors.json
#   Write metrics to output/run-report.json

def main() -> None:
    start_catalogue_url = "https://books.toscrape.com/catalogue/page-1.html"
    
    # Run Stage 2 Crawler
    discovered = discover_book_urls(start_url=start_catalogue_url, max_pages=3)
if __name__ == "__main__":
    main()