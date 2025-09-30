## The pre-trained NER(Named Entity Recognition) model in geo_reslutiom.py looks at the article text and finds a place name. 
#  But just knowing the string example: "Maastricht" isn’t useful by itself — we need to know which country it belongs etc.
#  So we use gazetteers as lookup list (dictionary) of detailed place names.
#  This method is just to parse .txt gazetters and turn them into dictionaries. ##

## --------------------------------------------------------------##
import csv
import re

LATIN_ONLY = re.compile(r"^[0-9A-Za-zÀ-ÿ\s\-\']+$")
HAS_VOWEL = re.compile(r"[aeiouyà-ÿ]", re.IGNORECASE)

def load_geonames_file(path, keep_countries={"NL","BE","DE"}, keep_classes={"P","A"}, keep_alternates=True):
    """
    Parse a GeoNames .txt file into {name_lower: country_code}.

    """
    gazetteer = {}

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 9:
                continue

            name = row[1]
            alt_names = row[3].split(",") if (row[3] and keep_alternates) else []
            feature_class = row[6]
            country_code = row[8]

            if country_code not in keep_countries:
                continue
            if feature_class not in keep_classes:
                continue

            main = name.strip().lower()
            if main and LATIN_ONLY.match(main):
                gazetteer[main] = country_code

            for alt in alt_names:
                alt = alt.strip().lower()
                if not alt:
                    continue
                if not LATIN_ONLY.match(alt): 
                    continue
                if len(alt) < 3:             
                    continue
                if not HAS_VOWEL.search(alt): 
                    continue
                gazetteer[alt] = country_code

    return gazetteer
