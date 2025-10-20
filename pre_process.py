## This file is for pre-processing the scrapped nos_articles.json file. ##

## -------------------------------------------------------------- ##

## First I will load the nos_articles JSON file into a DataFrame. ##
import pandas as pd
import json
from geo_filter import build_geo_df
from sme_filter import run_snorkel


with open("ncsc.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# We filter out the articles that are not from the region before pre-processing.
df = build_geo_df("ncsc.json", min_conf=0.6)

# We filter out the articles that are not about SMEs before pre-processing.
df, label_model = run_snorkel(df, min_conf=0.5)

sme_filtered = df[df["sme_probability"] > 0.6]
print(sme_filtered)
#print(df[["title", "sme_probability", "sme_label"]].head()) # peek

## -------------------------------------------------------------- ##

## This is the method to clean the cell contents in each row of the chosen column. ##
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

## This is a method that returns vocab (a collections.Counter object, which is a special kind of dictionary). ##
## Keys = words (tokens from the dataset) and Values = counts (how many times each word appeared) ##
from collections import Counter

def build_vocabulary(dataset):
    vocab = Counter()

    for example in dataset:
        text = example['clean']
        words = text.split()
        vocab.update(words)

    return vocab
## -------------------------------------------------------------- ##

## This method returns a row with an added list of tokens (words or <unk>) ##
def word_tokenizer(example, vocab, unknown_token='<unk>'):
    text = example['clean']
    tokens = None

    words = text.split()

    tokens = [word if word in vocab else unknown_token for word in words]

    example['tokens'] = tokens
    return example
## -------------------------------------------------------------- ##

## TESTING AREA ##
## This is the where Train/Test split + vocab + word tokenization for NOS articles is being done. ##
from sklearn.model_selection import train_test_split

# 1) I split the DataFrame into train/test.
train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)

news_ds = {
    "train": train_df.to_dict(orient="records"),
    "test": test_df.to_dict(orient="records"),
}

# 2) Making sure that each row has a 'clean' field (uses 'full_text' if present, otherwise title+summary).
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

# 3) Building vocabulary from TRAIN only:
vocab_counter = build_vocabulary(news_ds["train"])
#print("Size of the vocabulary:", len(vocab_counter))

# 4) Limiting vocab to top-10000 most frequent terms:
max_vocab_size = 10000
vocab = vocab_counter.most_common(max_vocab_size)

# 5) Casting to a plain list of words (droping their counts):
vocab = [word for word, _ in vocab]
#print("Final vocab size (after cutoff):", len(vocab))

# 6) Tokenizing TRAIN set:
for i in range(len(news_ds["train"])):
    news_ds["train"][i] = word_tokenizer(news_ds["train"][i], vocab)

# 6) Checking the OOV rate for the TRAIN set:
total = 0
oov = 0
for row in news_ds["train"]:
    toks = row.get("tokens", [])
    total += len(toks)
    oov += sum(1 for t in toks if t == "<unk>")
#print(f"OOV rate: {oov}/{total} = {oov/total:.2%}")


# 7) Shows first 10 examples from TRAIN set:
#for i in range(min(10, len(news_ds["train"]))):
    #print("Original article:")
    #print(get_raw_text(news_ds["train"][i]))
    #print("Tokenized article:")
    #print(news_ds["train"][i]["tokens"])
    #print("-" * 40)
## -------------------------------------------------------------- ##
