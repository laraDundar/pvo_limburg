import argparse
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
import sys
import time

import feedparser
import requests
from bs4 import BeautifulSoup

try:
    from readability import Document
except Exception:
    Document = None  # fallback if readability isn't available

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PVO-Limburg/1.0)"}
REQ_TIMEOUT = 12  # seconds
REQUEST_SLEEP = 0.3  # polite delay between article fetches


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_whitespace(s: str) -> str:
    return " ".join(s.split()) if s else s


def extract_main_text(html: str) -> str:
    """
    Try Readability first (article-like text), then fallback to <p> aggregation.
    Returns plain text.
    """
    if not html:
        return ""

    # Try Readability if available
    if Document is not None:
        try:
            doc = Document(html)
            summary_html = doc.summary(html_partial=True)
            soup = BeautifulSoup(summary_html, "lxml")
            text = soup.get_text(" ", strip=True)
            text = clean_whitespace(text)
            if text and len(text.split()) > 40:  # sanity check: looks like an article
                return text
        except Exception:
            pass

    # Fallback: collect all <p> text
    try:
        soup = BeautifulSoup(html, "lxml")
        ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = clean_whitespace(" ".join([t for t in ps if t]))
        return text
    except Exception:
        return ""


def fetch_url(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or r.encoding
        return r.text
    except Exception:
        return ""


def entry_to_record(feed_title: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    url = entry.get("link") or entry.get("id") or ""
    published = entry.get("published") or entry.get("updated") or ""
    summary_html = entry.get("summary") or entry.get("description") or ""

    full_text = ""
    if url:
        html = fetch_url(url)
        full_text = extract_main_text(html)
        time.sleep(REQUEST_SLEEP)

    record = {
        "feed": feed_title,
        "title": entry.get("title", "").strip(),
        "url": url,
        "published": published,
        "summary": summary_html,   # keep HTML as-is
        "full_text": full_text,    # plain text
        "scraped_at": now_utc_iso(),
    }

    # Optional light cleanup
    for k in ("feed", "title", "url", "published", "full_text"):
        if isinstance(record[k], str):
            record[k] = record[k].strip()

    return record


def gather_feed(feed_url: str, max_items: int) -> List[Dict[str, Any]]:
    fp = feedparser.parse(feed_url)
    feed_title = fp.feed.get("title", feed_url)
    entries = fp.entries[:max_items] if max_items else fp.entries
    results = []
    seen_links = set()

    for e in entries:
        link = e.get("link") or e.get("id") or ""
        if link and link in seen_links:
            continue
        seen_links.add(link)
        results.append(entry_to_record(feed_title, e))
    return results


def main():
    parser = argparse.ArgumentParser(description="Fetch RSS/Atom feeds to JSON.")
    parser.add_argument("--feeds", nargs="+", required=True,
                        help="One or more feed URLs.")
    parser.add_argument("--out", required=True, help="Output JSON file path.")
    parser.add_argument("--max-items", type=int, default=0,
                        help="Max items per feed (0 = all).")
    parser.add_argument("--pretty", action="store_true",
                        help="Pretty-print JSON.")
    args = parser.parse_args()

    all_records: List[Dict[str, Any]] = []
    for f in args.feeds:
        try:
            print(f"[INFO] Fetching: {f}", file=sys.stderr)
            recs = gather_feed(f, args.max_items)
            print(f"[INFO]  -> {len(recs)} items", file=sys.stderr)
            all_records.extend(recs)
        except Exception as exc:
            print(f"[WARN] Failed feed {f}: {exc}", file=sys.stderr)

    # You can sort by published if needed, but RSS date formats vary widely.
    # Here we just keep the feed order as parsed.

    with open(args.out, "w", encoding="utf-8") as f:
        if args.pretty:
            json.dump(all_records, f, ensure_ascii=False, indent=2)
        else:
            json.dump(all_records, f, ensure_ascii=False)

    print(f"[DONE] Saved {len(all_records)} records to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()