import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time as t
from dateutil import parser
import random


def clean_text_for_csv(text):
    if not text:
        return ""
    # Replace line breaks and tabs with a space
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    # Collapse multiple spaces into one
    text = ' '.join(text.split())
    return text

# scrape security.nl articles up to and including given date
def security_nl_historical(date_str):
    articles = []
    page = 1
    within_date = True
    date = datetime.strptime(date_str, "%d-%m-%Y")
    while within_date:
        
        # dynamically generate page url
        url = f"https://www.security.nl/archive/1/{page}" 
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        print(f"Accessed page {page}")

        # find all the article items
        posts = soup.find_all("div", class_=["posting_list_item first", "posting_list_item"])

        # extract data

        for post in posts:
            date_div = post.find("div", class_="date")
            timestamp_div = post.find("div", class_="timestamp")
            title_div = post.find("div", class_="title")

            if not date_div:
                continue

            try:
                post_date = datetime.strptime(date_div.get_text(strip=True), "%d-%m-%Y")
            except:
                continue

            if post_date < date:
                within_date = False
                print(f"Reached post before cutoff date ({date_str}), stopping.")
                break

            if title_div and title_div.a:
                a_tag = title_div.a
                title = a_tag.get_text(strip=True)
                link = a_tag["href"]

                # check + fix relative urls
                if link.startswith("/"):
                    link = requests.compat.urljoin(url, link)

                    # fetch the article page
                    try:
                        response = requests.get(link)
                        response.raise_for_status()
                        soup = BeautifulSoup(response.text, "html.parser")

                        # find the posting_content div
                        content_div = soup.find("div", class_="posting_content")
                        full_text = ""
                        if content_div:
                            paragraphs = content_div.find_all("p")
                            full_text = "\n".join(p.get_text(strip=True) for p in paragraphs)

                    except Exception as e:
                        print(f"Failed to fetch article {link}: {e}")
                        full_text = ""

                articles.append({
                    "date": date_div.get_text(strip=True),
                    "time": timestamp_div.get_text(strip=True) if timestamp_div else "",
                    "title": title,
                    "url": link,
                    "full_text": clean_text_for_csv(full_text)
                })

        page += 1
        
    return articles

# scrape bleeping computer articles up to and including given date
def bleeping_historical(cutoff_date_str):
    articles = []
    page = 1
    within_date = True
    cutoff_date = datetime.strptime(cutoff_date_str, "%d-%m-%Y")

    while within_date:
        
        # dynamically generate page url
        url = f"https://www.bleepingcomputer.com/news/security/page/{page}"
        
        if page == 1:
            url = "https://www.bleepingcomputer.com/news/security/"
        
        # fake header so script is not blocked
        headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")  # or "html.parser" if lxml not installed

        # find all the article items
        news_items = soup.select("ul#bc-home-news-main-wrap > li")

        # extract data 
        for item in news_items:
            text_div = item.find("div", class_="bc_latest_news_text")
            if not text_div:
                continue  # skip if structure differs

            # title + link
            a_tag = text_div.find("h4").find("a", href=True) if text_div.find("h4") else None
            title = a_tag.get_text(strip=True) if a_tag else ""
            link = a_tag["href"] if a_tag else ""
            if link.startswith("/"):
                base_url = "https://www.bleepingcomputer.com" 
                link = requests.compat.urljoin(base_url, link)
            # summary
            summary_tag = text_div.find("p")
            summary = summary_tag.get_text(strip=True) if summary_tag else ""

            # date + time
            date_tag = text_div.find("li", class_="bc_news_date")
            time_tag = text_div.find("li", class_="bc_news_time")
            if date_tag:
                date_str = date_tag.get_text(strip=True)
            else:
                continue
            time = time_tag.get_text(strip=True) if time_tag else ""

            date = datetime.strptime(date_str, "%B %d, %Y")
            if date < cutoff_date:
                    within_date = False
                    print(f"Reached post before cutoff date ({date_str}), stopping.")
                    break
        
            articles.append({
                "date": date.strftime("%Y-%m-%d"),
                "time": time,
                "title": title,
                "summary": summary,
                "link": link
            })

        print(f"Acessed page {page}")
        page += 1

        t.sleep(random.uniform(1, 5))

    
    return articles

# default date for initial csv set up. can be repeated later
def scrape_1yr():
    date = "01-10-2024"

    # articles = bleeping_historical(date)

    # df = pd.DataFrame(articles)
    # df.to_csv(f"articles\\beeping_articles.csv", index=False, encoding="utf-8")

    # print(f"Saved {len(df)} news items to beeping_articles.csv")

    articles = security_nl_historical(date)

    df = pd.DataFrame(articles)
    df.to_csv("articles\\security_nl_articles.csv", index=False, encoding="utf-8")

    print(f"Saved {len(df)} articles to AAAsecurity_nl_articles.csv")


# update csvs with newly scraped articles
def update_source(filepath, n):
    df = pd.read_csv(filepath)

    if "date" not in df.columns:
        raise ValueError("The CSV does not contain a 'date' column.")
    
    date_str = df.iloc[1]["date"]
    date = parser.parse(date_str, fuzzy=True)

    if n == 0:
        new_articles = bleeping_historical(date.strftime("%d-%m-%Y"))
    elif n == 1:
        new_articles = security_nl_historical(date.strftime("%d-%m-%Y"))
    else:
        print("Error with source scraping method choice.")
    new_df = pd.DataFrame(new_articles)

    merged_df = pd.concat([new_df, df], ignore_index=True).drop_duplicates()
    merged_df.to_csv(filepath, index=False, encoding="utf-8")


def update_csvs():
    update_source("articles\\beeping_articles.csv", 0)
    update_source("articles\\security_nl_articles.csv", 1)


def buh_bye():
    print("Bye.")
    exit(0)

# basic cli
def main():
    while True:
        print("\n=== Main Menu ===")
        print("1) Scrape 1 year")
        print("2) Update")
        print("3) Exit")

        choice = input("Enter your choice (1-3): ").strip()

        if choice == "1":
            scrape_1yr()
        elif choice == "2":
            update_csvs()
        elif choice == "3":
            buh_bye()
        else:
            print("Invalid choice. Please enter a number between 1 and 3.")

if __name__ == "__main__":
    main()