## After some attempts of applying general NLP methods to the articles that we got from
#  RSS-feed of the NOS(I believe any generic news website would give similar results)
#  it is visible that there is some issues when it comes to filtering the location.
#  To solve this issue, we used a pre-trained NER(Named Entity Recognition) model to extract
#  locations from the articles.
#  We sum up the votes per country, then return country, country_score,
#  and evidence (matched city, postal code, etc.) and finally produce a country probability.
#  If the probability score is less than the threshold, then it gets marked “uncertain”.
# 
#  For these uncertain articles(IF they increase in number as we keep on collecting data), 
#  we can train a small disambiguation model(logistic regression (maybe?)) to review them.
#  
# The methods on this file(filtering) are used BEFORE the word-tokenization step at the pre-processing file. ##

## --------------------------------------------------------------##

## This is the method to clean the cell contents in each row of the chosen column.
#  It is slightly different than the clean_text method in pre_processing.py file,
#  Because it keeps original casing and punctuation, so we don't break spaCy’s ability to detect place names. ##
import unicodedata
from bs4 import BeautifulSoup

def clean_text_geo(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""

    # 1) Stripping HTML to plain text:
    text = BeautifulSoup(text, "html.parser").get_text(separator=" ")

    # 2) Normalizing whitespace/dashes/quotes:
    text = unicodedata.normalize("NFKC", text)

    return text

# Making sure that each row has a 'clean' field (uses 'full_text' if present, otherwise title+summary).
def get_raw_text_geo(row):
    if row.get("full_text") and isinstance(row["full_text"], str) and row["full_text"].strip():
        return row["full_text"]
    # If full_text is missing, then title + summary:
    title = row.get("title", "") or ""
    summary = row.get("summary", "") or ""
    return f"{title} {summary}".strip()

## -------------------------------------------------------------- ##

## We will use spaCy to detect candidate location names. ##
import spacy

nlp = spacy.load('nl_core_news_sm')

def detect_candidate_locations(text):
    doc = nlp(text)
    return [ent.text for ent in doc.ents if ent.label_ in {"LOC","GPE"}]

## -------------------------------------------------------------- ##

## We use the gazetteer_parser.py to create a dictionary of place names. ##
from geoNames.gazetteer_parser import load_geonames_file

# Load dictionaries
nl_gaz = load_geonames_file("geoNames/NL.txt", keep_countries={"NL"})
be_gaz = load_geonames_file("geoNames/BE.txt", keep_countries={"BE"})
de_gaz = load_geonames_file("geoNames/DE.txt", keep_countries={"DE"})

# Merge into one
gazetteer = {}
for g in (nl_gaz, be_gaz, de_gaz):
    gazetteer.update(g)

print("Total entries in gazetteer:", len(gazetteer))
print(list(gazetteer.items())[:20]) # peek
## -------------------------------------------------------------- ##

## This is the voting method to know if the places mentioned in the articles are around the NL/BE/DE or not. ##
def voting_country_from_locations(locations, gazetteer, threshold=0.6):
    # 1) Initializing a vote counter
    votes = {"NL": 0, "BE": 0, "DE": 0}
    evidence = [] # Evidence will store which place name matched which country.

    # 2) It loops through all places spaCy found, and if the place is in the gazetteer:
    # it gets its country code (cc)
    # adds +1 to that country’s votes
    # and saves evidence.
    for loc in locations:
        cc = gazetteer.get(loc.lower())
        if cc in votes:
            votes[cc] += 1
            evidence.append((loc, cc))

    total = sum(votes.values())
    if total == 0:
        return "uncertain", 0.0, [] # If no place matched NL/BE/DE, then returns "uncertain".

    # 3) Picks the country with the highest number of votes.
    # Confidence = proportion of votes for that winner.
    best_cc, best_val = max(votes.items(), key=lambda kv: kv[1])
    confidence = best_val / total

    if confidence < threshold:
        return "uncertain", confidence, evidence
    
    return best_cc, confidence, evidence

## -------------------------------------------------------------- ##

## This is the method to filter out articles that aren't from the region. ##
TARGET_COUNTRIES = {"NL", "BE", "DE"}

def filtering_articles_by_country(df, min_conf: float = 0.6):
    """
    Keep only rows confidently resolved to NL/BE/DE.
    Drops 'uncertain' and low-confidence rows.
    Returns a *copy* so the original df stays intact.
    """
    if "country" not in df.columns or "country_score" not in df.columns:
        raise ValueError("Missing required columns: 'country' and 'country_score'.")

    mask = (df["country"].isin(TARGET_COUNTRIES)) & (df["country_score"] >= min_conf)
    df_filtered_by_country = df.loc[mask].copy()

    kept = len(df_filtered_by_country)
    total = len(df)
    print(f"[geo_resolution] kept {kept}/{total} rows ({kept/total:.1%}) with country in {TARGET_COUNTRIES} and score ≥ {min_conf}") # peek

    return df_filtered_by_country

## -------------------------------------------------------------- ##

## This is the method that needs to be called from pre_processing.py file. ##
def build_geo_df(json_path="nos_articles.json", min_conf=0.6):
    """
    Load NOS articles, enrich them with geo info, 
    and return only rows confidently resolved to NL/BE/DE.
    """
    import pandas as pd, json
    # 1) I will load the nos_articles JSON file into a DataFrame:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)

    # 2) Clean the JSON file:
    df["clean_geo"] = df.apply(lambda r: clean_text_geo(get_raw_text_geo(r)), axis=1)

    # 3) Detect candidate locations for all articles:
    df["locations"] = df["clean_geo"].apply(detect_candidate_locations)

    # 4) Get the voting per article:
    results = df["locations"].apply(lambda locs: voting_country_from_locations(locs, gazetteer))
    df[["country", "country_score", "country_evidence"]] = pd.DataFrame(results.tolist(), index=df.index)

    # 5) Filter only the rows around the region:
    return filtering_articles_by_country(df, min_conf=min_conf)
## -------------------------------------------------------------- ##

