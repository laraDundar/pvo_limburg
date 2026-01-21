## This file is for experimenting with the pre-processing pipeline without caching ##

import pandas as pd
import json
from geo_filter import build_geo_df
from layered_filter import run_crime_snorkel, run_sme_snorkel
from narrow_locations import apply_location_narrowing
from sector_classifier import add_sector_classification
import sys

print("=" * 80)
print("EXPERIMENTAL PRE-PROCESSING - NO CACHING")
print("=" * 80)

# Load the example data
with open("all_articles_sme_ex.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"\nLoaded {len(data)} articles from all_articles_sme_ex.json")

# Process all articles without caching
processed_rows = []

for idx, art in enumerate(data, 1):
    print(f"\nProcessing article {idx}/{len(data)}: {art.get('title', 'No title')[:50]}...")
    
    # Save single article to temp JSON (build_geo_df requires a file path)
    temp_path = "_temp_single.json"
    with open(temp_path, "w", encoding="utf-8") as tf:
        json.dump([art], tf, ensure_ascii=False, indent=2)

    # GEO FILTER
    single_df = build_geo_df(temp_path, min_conf=0.6)
    if len(single_df) == 0:
        print(f"  ✗ Filtered out: No geo info")
        continue

    # CRIME FILTER
    single_df = run_crime_snorkel(single_df)
    if len(single_df) == 0:
        print(f"  ✗ Filtered out: Crime-related")
        continue

    # SME FILTER
    single_df = run_sme_snorkel(single_df)
    if len(single_df) == 0:
        print(f"  ✗ Filtered out: Not SME-related")
        continue

    # LOCATION NARROWING
    if len(single_df) > 0:
        single_df = apply_location_narrowing(single_df)
    if len(single_df) == 0:
        print(f"  ✗ Filtered out: Location narrowing")
        continue

    # SECTOR CLASSIFICATION
    if len(single_df) > 0:
        single_df = add_sector_classification(single_df)
    if len(single_df) == 0:
        print(f"  ✗ Filtered out: Sector classification")
        continue

    # Keep result
    if len(single_df) > 0:
        result = single_df.to_dict(orient="records")[0]
        processed_rows.append(result)
        print(f"  ✓ PASSED all filters!")

# Create final filtered DataFrame
sme_filtered = pd.DataFrame(processed_rows)

print("\n" + "=" * 80)
print(f"FILTERING RESULTS:")
print(f"  Total input articles: {len(data)}")
print(f"  Articles passing all filters: {len(sme_filtered)}")
print(f"  Filter rate: {len(sme_filtered)/len(data)*100:.1f}%")
print("=" * 80)

# CLUSTERING - Higher threshold + stricter temporal proximity
from article_clustering import cluster_articles
if len(sme_filtered) > 0:
    print("\nRunning clustering...")
    sme_filtered = cluster_articles(
        sme_filtered,
        threshold=0.75,
        max_hours=72,
        verbose=True
    )
    
    # Get detailed statistics
    from article_clustering import get_clustering_stats
    stats = get_clustering_stats(sme_filtered)
    print("\nClustering statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

# Display results
print("\n" + "=" * 80)
print("FINAL DATAFRAME:")
print("=" * 80)
print(sme_filtered)

# Show some sample columns if available
if len(sme_filtered) > 0:
    available_cols = sme_filtered.columns.tolist()
    print(f"\nAvailable columns: {', '.join(available_cols)}")
    
    if 'sme_probability' in available_cols and 'sme_label' in available_cols:
        print("\nSME Classification Preview:")
        print(sme_filtered[["title", "sme_probability", "sme_label"]].head())

## -------------------------------------------------------------- ##
## Text cleaning function ##
import re
import wordninja
import unicodedata
from bs4 import BeautifulSoup

def clean_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""

    # 1) Stripping HTML to plain text:
    text = BeautifulSoup(text, "html.parser").get_text(separator=" ")

    # 2) Normalizing whitespace/dashes/quotes:
    text = unicodedata.normalize("NFKC", text)

    # 3) Removing leading podcast/article number headers like "#202 - ":
    text = re.sub(r"^\s*#?\d+\s*[-–—:]\s*", "", text)

    # 4) Splitting #Hashtag/@Mentions into words (keeping the content, but not the symbol):
    def tag_handler(m):
        return " ".join(wordninja.split(m.group(1)))
    text = re.sub(r"[@#](\w+)", tag_handler, text)
    text = re.sub(r"[@#]", " ", text)  # leftover symbols

    # 5) Replacing punctuation with space (keeping letters incl. accents + digits):
    text = re.sub(r"[^0-9A-Za-zÀ-ÿ\s]", " ", text)

    # 6) Collapsing multiple spaces and lowercase:
    text = re.sub(r"\s+", " ", text).strip().lower()

    return text

## -------------------------------------------------------------- ##
## Vocabulary building function ##
from collections import Counter

def build_vocabulary(dataset):
    vocab = Counter()

    for example in dataset:
        text = example['clean']
        words = text.split()
        vocab.update(words)

    return vocab

## -------------------------------------------------------------- ##
## Word tokenizer function ##
def word_tokenizer(example, vocab, unknown_token='<unk>'):
    text = example['clean']
    tokens = None

    words = text.split()
    tokens = [word if word in vocab else unknown_token for word in words]

    example['tokens'] = tokens
    return example

## -------------------------------------------------------------- ##
## Train/Test split + vocab + word tokenization ##
from sklearn.model_selection import train_test_split

# Check if we have enough data
if len(sme_filtered) == 0:
    print("\n⚠️ No SME articles found — skipping train/test split.")
    sys.exit(0)
elif len(sme_filtered) < 3:
    print(f"\n⚠️ Only {len(sme_filtered)} SME article(s) found — skipping train/test split.")
    sys.exit(0)

print("\n" + "=" * 80)
print("TEXT PROCESSING & TOKENIZATION")
print("=" * 80)

# 1) Split the DataFrame into train/test
train_df, test_df = train_test_split(sme_filtered, test_size=0.2, random_state=42)

news_ds = {
    "train": train_df.to_dict(orient="records"),
    "test": test_df.to_dict(orient="records"),
}

print(f"\nTrain set: {len(news_ds['train'])} articles")
print(f"Test set: {len(news_ds['test'])} articles")

# 2) Make sure each row has a 'clean' field
def get_raw_text(row):
    if "full_text" in row and isinstance(row["full_text"], str) and row["full_text"].strip():
        return row["full_text"]
    # If full_text is missing, then title + summary:
    title = row.get("title", "") or ""
    summary = row.get("summary", "") or ""
    return f"{title} {summary}".strip()

for split in ["train", "test"]:
    for row in news_ds[split]:
        row["clean"] = clean_text(get_raw_text(row))

# 3) Build vocabulary from TRAIN only
vocab_counter = build_vocabulary(news_ds["train"])
print(f"\nSize of the vocabulary: {len(vocab_counter)}")

# 4) Limit vocab to top-10000 most frequent terms
max_vocab_size = 10000
vocab = vocab_counter.most_common(max_vocab_size)

# 5) Cast to a plain list of words (dropping their counts)
vocab = [word for word, _ in vocab]
print(f"Final vocab size (after cutoff): {len(vocab)}")

# 6) Tokenize TRAIN set
for i in range(len(news_ds["train"])):
    news_ds["train"][i] = word_tokenizer(news_ds["train"][i], vocab)

# 7) Check the OOV rate for the TRAIN set
total = 0
oov = 0
for row in news_ds["train"]:
    toks = row.get("tokens", [])
    total += len(toks)
    oov += sum(1 for t in toks if t == "<unk>")

print(f"\nOOV rate: {oov}/{total} = {oov/total:.2%}")

# 8) Show first 3 examples from TRAIN set
print("\n" + "=" * 80)
print("SAMPLE TOKENIZED ARTICLES:")
print("=" * 80)
for i in range(min(3, len(news_ds["train"]))):
    print(f"\n--- Article {i+1} ---")
    print("Original article (first 200 chars):")
    print(get_raw_text(news_ds["train"][i])[:200] + "...")
    print("\nTokenized (first 30 tokens):")
    print(news_ds["train"][i]["tokens"][:30])
    print("-" * 80)

## -------------------------------------------------------------- ##
## TF-IDF Keyword Extraction ##
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from nltk.corpus import stopwords
import nltk

print("\n" + "=" * 80)
print("TF-IDF KEYWORD EXTRACTION")
print("=" * 80)

# Download and load Dutch stopwords
nltk.download('stopwords', quiet=True)
stopword_list = stopwords.words('dutch')

# Build corpus from 'clean' column
corpus = [row["clean"] for row in news_ds["train"] if row.get("clean", "").strip()]

# Build Bag-of-Words with stopword filtering
vectorizer = CountVectorizer(
    max_features=10000,
    stop_words=stopword_list,
)
bows = vectorizer.fit_transform(corpus).toarray()
vocab_array = np.array(vectorizer.get_feature_names_out())

# Calculate IDF
def calculate_idf(bows):
    N = bows.shape[0]
    df = np.count_nonzero(bows, axis=0)
    df = np.where(df == 0, 1, df)  # avoid division by zero
    idf = np.log10(N / df)
    return idf

idf = calculate_idf(bows)

# Compute TF-IDF for each document
def compute_tfidf_matrix(bows, idf):
    tfidf_matrix = bows * idf
    norms = np.linalg.norm(tfidf_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return tfidf_matrix / norms

tfidf_matrix = compute_tfidf_matrix(bows, idf)

# Extract top-k keywords per document
def extract_keywords(tfidf_matrix, vocab, top_k=10):
    keywords = []
    for row in tfidf_matrix:
        top_indices = row.argsort()[-top_k:][::-1]
        top_words = vocab[top_indices]
        top_scores = row[top_indices]
        keywords.append(list(zip(top_words, top_scores)))
    return keywords

article_keywords = extract_keywords(tfidf_matrix, vocab_array, top_k=10)

# Attach top keywords back to the training DataFrame
train_df_with_keywords = pd.DataFrame(news_ds["train"]).copy()
train_df_with_keywords["keywords"] = [
    [{"word": w, "score": float(s)} for w, s in kws] for kws in article_keywords
]

# Save results to JSON
import os
os.makedirs("keywords", exist_ok=True)

train_df_with_keywords.to_json(
    "keywords/experiment_articles_keywords.json",
    orient="records",
    indent=2,
    force_ascii=False,
)

print("\nTF-IDF keyword extraction completed.")
print(f"Saved to: keywords/experiment_articles_keywords.json")

# Show sample
if len(train_df_with_keywords) > 0:
    print("\nSample article with keywords:")
    print(train_df_with_keywords[["title", "keywords"]].head(1))

# Aggregate scores for top keywords
from collections import Counter

global_keywords = Counter()
for kws in article_keywords:
    for w, s in kws:
        global_keywords[w] += float(s)

# Get top 20 keywords
top_keywords = global_keywords.most_common(20)

print("\n" + "=" * 80)
print("TOP 20 OVERALL SME KEYWORDS:")
print("=" * 80)
for word, score in top_keywords:
    print(f"{word:<20} {score:.3f}")

# Save top keywords to JSON
output_file = "keywords/experiment_top_keywords.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(dict(top_keywords), f, ensure_ascii=False, indent=2)

print(f"\nSaved top 20 keywords to: {output_file}")

print("\n" + "=" * 80)
print("EXPERIMENT COMPLETED SUCCESSFULLY!")
print("=" * 80)