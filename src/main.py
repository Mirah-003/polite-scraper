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
from datetime import datetime, timezone

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

def parse_book_detail(book_info: dict) -> dict:
    """
    Fetches and parses a single book detail page.
    Extracts 8 raw fields including data provenance (source_page, fetched_at).
    Handles missing descriptions gracefully by returning None.
    """
    url = book_info["product_url"]
    source_page = book_info["source_page"]
    
    # Generate clean cache filename from URL slug (e.g., detail-a-light-in-the-attic_1000.html)
    url_slug = url.split("/")[-2] if url.endswith("/") or url.endswith(".html") else url.split("/")[-1]
    cache_filename = f"detail-{url_slug}.html"
    
    # Fetch detail page HTML (uses local cache if already downloaded)
    html_content, is_cache_hit = fetch_page(url=url, cache_filename=cache_filename)
    
    # Apply 0.5s politeness delay on real network calls
    if not is_cache_hit:
        time.sleep(0.5)
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 1. Target main product container for core fields
    product_main = soup.find("div", class_="product_main")
    if not product_main:
        raise RuntimeError(f"Could not find product_main container on {url}")
    title = product_main.find("h1").text.strip()
    price_text = product_main.find("p", class_="price_color").text.strip()
    
    availability_elem = product_main.find("p", class_="instock availability")
    availability_text = availability_elem.text.strip() if availability_elem else ""
    # Star rating: extracted from class list (e.g. ['star-rating', 'Three'] -> 'Three')
    rating_elem = product_main.find("p", class_="star-rating")
    rating_text = rating_elem["class"][1] if rating_elem and len(rating_elem["class"]) > 1 else "Unknown"
    # 2. Extract description (Find #product_description heading -> next sibling <p>)
    desc_heading = soup.find("div", id="product_description")
    if desc_heading and desc_heading.find_next_sibling("p"):
        description = desc_heading.find_next_sibling("p").text.strip()
    else:
        description = None
    # 3. Provenance receipt timestamp (UTC ISO 8601 string)
    fetched_at = datetime.now(timezone.utc).isoformat()
    return {
        "title": title,
        "product_url": url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at
    }

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
    
    # Stage 2: Discover 60 book URLs across 3 catalogue pages
    discovered_books = discover_book_urls(start_url=start_catalogue_url, max_pages=3)
    
    # Stage 3: Extract raw records from all 60 book pages
    raw_records = []
    print("\nFetching and extracting book detail pages...")
    
    for book_info in discovered_books:
        raw_record = parse_book_detail(book_info)
        raw_records.append(raw_record)
    # Print Stage 3 Checkpoint output
    print(f"\nCHECKPOINT — detail_pages={len(raw_records)}")
    print("\nSample Raw Record (All 8 keys):")
    import json
    print(json.dumps(raw_records[0], indent=2))

if __name__ == "__main__":
    main()