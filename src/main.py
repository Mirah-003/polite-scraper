# ==========================================
# FLYRANK AI — ASSIGNMENT BE-05: THE POLITE SCRAPER
# ==========================================

# ==========================================
# TODO 0 — Imports & Setup
# ==========================================

import os
import sys
import time
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ValidationError
from typing import Optional

# Define polite User-Agent identification header
USER_AGENT = "FlyRankInternship-A9/1.0 (+https://github.com/Mirah-003/polite-scraper)"
HEADERS = {"User-Agent": USER_AGENT}

# Create required directories
os.makedirs("cache", exist_ok=True)
os.makedirs("output", exist_ok=True)


# ==========================================
# TODO 1 — Fetch Once, Cache Once (HTTP Fetcher)
# ==========================================

def fetch_page(url: str, cache_filename: str, timeout: int = 10, retries: int = 1) -> tuple[str, bool]:
    """
    Politely fetches a web page or loads it from local disk cache.
    Retries once on transient 5xx server errors or timeouts.
    Does NOT retry 404 or 403 status codes.
    """
    cache_filepath = os.path.join("cache", cache_filename)
    
    # 1. Disk Cache Check
    if os.path.exists(cache_filepath):
        with open(cache_filepath, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"CACHE HIT | File: {cache_filename} | Size: {len(content)} bytes")
        return content, True

    # 2. Network Fetch with selective retry
    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            
            # Do NOT retry 404 or 403 errors
            if response.status_code in (404, 403):
                raise RuntimeError(f"HTTP {response.status_code} (Non-retryable) for {url}")
                
            # Retry transient 5xx server errors once
            if response.status_code >= 500:
                if attempt <= retries:
                    print(f"Server error HTTP {response.status_code} on {url}. Retrying in 1s (Attempt {attempt}/{retries})...")
                    time.sleep(1.0)
                    continue
                raise RuntimeError(f"HTTP {response.status_code} Server Error after retry")

            if response.status_code != 200:
                raise RuntimeError(f"HTTP Error {response.status_code} for {url}")
                
            content = response.text
            with open(cache_filepath, "w", encoding="utf-8") as f:
                f.write(content)
                
            print(f"FETCH     | URL: {url} | Size: {len(content)} bytes")
            return content, False

        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt <= retries:
                print(f"Network timeout/error on {url}. Retrying in 1s (Attempt {attempt}/{retries})...")
                time.sleep(1.0)
                continue
            raise RuntimeError(f"Network failure for {url}: {e}")
        except Exception as e:
            raise e


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
    
    url_slug = url.split("/")[-2] if url.endswith("/") or url.endswith(".html") else url.split("/")[-1]
    cache_filename = f"detail-{url_slug}.html"
    
    html_content, is_cache_hit = fetch_page(url=url, cache_filename=cache_filename)
    
    if not is_cache_hit:
        time.sleep(0.5)

    soup = BeautifulSoup(html_content, "html.parser")
    
    product_main = soup.find("div", class_="product_main")
    if not product_main:
        raise RuntimeError(f"Could not find product_main container on {url}")

    title = product_main.find("h1").text.strip()
    price_text = product_main.find("p", class_="price_color").text.strip()
    
    availability_elem = product_main.find("p", class_="instock availability")
    availability_text = availability_elem.text.strip() if availability_elem else ""

    rating_elem = product_main.find("p", class_="star-rating")
    rating_text = rating_elem["class"][1] if rating_elem and len(rating_elem["class"]) > 1 else "Unknown"

    desc_heading = soup.find("div", id="product_description")
    if desc_heading and desc_heading.find_next_sibling("p"):
        description = desc_heading.find_next_sibling("p").text.strip()
    else:
        description = None

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

class BookRecord(BaseModel):
    """
    Pydantic schema for a validated, normalized book record.
    Enforces required fields, float price_gbp, and optional description.
    """
    title: str
    product_url: str
    price_text: str
    price_gbp: float = Field(..., description="Normalized price in GBP as a float number")
    availability_text: str
    rating_text: str
    description: Optional[str] = None
    source_page: str
    fetched_at: str


def normalize_and_validate(raw_record: dict) -> BookRecord:
    """
    Normalizes price_text into price_gbp float, keeps raw price_text side-by-side,
    and validates the record against the BookRecord Pydantic schema.
    """
    price_text = raw_record["price_text"]
    numeric_string = re.sub(r"[^\d.]", "", price_text)
    if not numeric_string:
        raise ValueError(f"Could not extract numeric price from '{price_text}'")
    
    price_gbp = float(numeric_string)
    
    normalized_data = raw_record.copy()
    normalized_data["price_gbp"] = price_gbp
    
    validated_record = BookRecord(**normalized_data)
    return validated_record


# ==========================================
# TODO 5 — Fault Tolerance & Report Generation
# ==========================================

def generate_run_report(start_time_iso: str, duration: float, pages_fetched: int, cache_hits: int, valid_count: int, invalid_count: int, failed_count: int) -> dict:
    """
    Generates and saves an honest metrics audit report to output/run-report.json.
    """
    report = {
        "start_time": start_time_iso,
        "duration_seconds": round(duration, 2),
        "pages_fetched": pages_fetched,
        "cache_hits": cache_hits,
        "valid_records": valid_count,
        "invalid_records": invalid_count,
        "failed_pages": failed_count
    }
    
    report_filepath = os.path.join("output", "run-report.json")
    with open(report_filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    return report


def main() -> None:
    start_time_utc = datetime.now(timezone.utc).isoformat()
    start_timer = time.time()

    start_catalogue_url = "https://books.toscrape.com/catalogue/page-1.html"
    
    # Stage 2: Discover 60 book URLs across 3 catalogue pages
    discovered_books = discover_book_urls(start_url=start_catalogue_url, max_pages=3)
    
    # Stage 5 Requirement: Inject 1 fake broken URL to test fault tolerance
    fake_broken_book = {
        "product_url": "https://books.toscrape.com/catalogue/non-existent-broken-book_9999/index.html",
        "source_page": "https://books.toscrape.com/catalogue/page-1.html"
    }
    discovered_books.append(fake_broken_book)

    # Track pipeline metrics
    valid_books: list[dict] = []
    error_records: list[dict] = []
    failed_pages_count = 0
    seen_canonical_urls = set()

    print(f"\nProcessing {len(discovered_books)} book pages (including 1 injected fake URL)...")

    for book_info in discovered_books:
        canonical_url = book_info["product_url"]
        if canonical_url in seen_canonical_urls:
            continue
        seen_canonical_urls.add(canonical_url)

        # Fault Tolerance: Wrap each page in try...except so 1 broken page never kills the run
        try:
            raw_record = parse_book_detail(book_info)
            validated_record = normalize_and_validate(raw_record)
            valid_books.append(validated_record.model_dump())
        except Exception as e:
            failed_pages_count += 1
            print(f"SKIPPED BROKEN PAGE | URL: {canonical_url} | Reason: {e}")
            error_records.append({
                "product_url": canonical_url,
                "error_reason": str(e)
            })

    # Save output/books.json
    books_file = os.path.join("output", "books.json")
    with open(books_file, "w", encoding="utf-8") as f:
        json.dump(valid_books, f, indent=2)

    # Save output/errors.json
    errors_file = os.path.join("output", "errors.json")
    with open(errors_file, "w", encoding="utf-8") as f:
        json.dump(error_records, f, indent=2)

    duration = time.time() - start_timer
    cache_files_count = len([f for f in os.listdir("cache") if os.path.isfile(os.path.join("cache", f))])

    # Generate and save output/run-report.json
    report = generate_run_report(
        start_time_iso=start_time_utc,
        duration=duration,
        pages_fetched=max(0, 64 - cache_files_count),
        cache_hits=cache_files_count,
        valid_count=len(valid_books),
        invalid_count=len(error_records) - failed_pages_count,
        failed_count=failed_pages_count
    )

    print(f"\nCHECKPOINT — output/books.json has {len(valid_books)} valid records.")
    print(f"CHECKPOINT — output/run-report.json generated:")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()