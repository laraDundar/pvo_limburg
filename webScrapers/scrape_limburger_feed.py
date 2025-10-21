#!/usr/bin/env python3
"""
scrape_limburger_feed.py
Scrapes a single De Limburger RSS feed and extracts article content.

Usage:
  python scrape_limburger_feed.py \
      --feed https://www.limburger.nl/extra/rssfeed/22594085.html \
      --out scrapedArticles/limburger.json \
      --max-items 30 --pretty
"""

import argparse
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
import sys
import requests
import feedparser
from bs4 import BeautifulSoup

try:
    from readability import Document
except ImportError:
    Document = None  # fallback if readability isn't installed

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PVO-Limburg/1.0)"}
REQ_TIMEOUT = 12
REQUEST_SLEEP = 0.3


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_whitespace(s: str) -> str:
    return " ".join(s.split()) if s else ""


def extract_main_text(html: str) -> str:
    """
    Extract main article text using readability -> fallback to <p> tags.
    """
    if not html:
        return ""
    text = ""
    try:
        if Document is not None:
            doc = Document(html)
            soup = BeautifulSoup(doc.summary(), "html.parser")
            text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
        else:
            soup = BeautifulSoup(html, "html.parser")
            text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
    except Exception:
        pass
    return clean_whitespace(text)


def fetch_article(url: str) -> str:
    """
    Download article HTML and extract text.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT)
        if resp.status_code == 200:
            return extract_main_text(resp.text)
    except Exception as e:
        print(f"[WARN] Failed to fetch {url}: {e}")
    return ""


def scrape_feed(feed_url: str, max_items: int = 30) -> List[Dict[str, Any]]:
    print(f"🔍 Fetching feed: {feed_url}")
    feed = feedparser.parse(feed_url)
    entries = feed.entries[:max_items]
    results = []

    for entry in entries:
        url = entry.get("link", "")
        title = clean_whitespace(entry.get("title", ""))
        summary = clean_whitespace(entry.get("summary", ""))
        published = entry.get("published", "")
        print(f"📰 Scraping: {title[:80]}...")
        full_text = fetch_article(url)
        results.append({
            "feed": "De Limburger",
            "title": title,
            "url": url,
            "published": published,
            "summary": summary,
            "full_text": full_text,
            "scraped_at": now_utc_iso(),
        })
        time.sleep(REQUEST_SLEEP)
    return results


def save_json(data: List[Dict[str, Any]], out_path: str, pretty: bool = False):
    with open(out_path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            json.dump(data, f, ensure_ascii=False)
    print(f"✅ Saved {len(data)} articles to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape De Limburger RSS feed")
    parser.add_argument("--feed", required=True, help="RSS feed URL")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--max-items", type=int, default=30, help="Maximum items to fetch")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    articles = scrape_feed(args.feed, max_items=args.max_items)
    save_json(articles, args.out, pretty=args.pretty)
