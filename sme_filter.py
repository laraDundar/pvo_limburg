## After some attempts of applying general NLP methods to the articles that we got from
#  RSS-feed of the NOS(I believe any generic news website would give similar results)
#  it is visible that there is some issues when it comes to filtering the news about SMEs.
#  To solve this issue, we used Snorkel, a weak supervision framework, to build a 
#  label model for classifying whether a text refers to an SME (small/medium enterprise) or not.
#  Maybe after building the prototype to improve the filtering, we can:
#  1) Add more LFs (having 15-25 is ideal).
#  2) Train a classifier (e.g., TF-IDF + LogisticRegression) to generalize beyond the LFs.

#  The methods on this file(filtering) are used:
#  AFTER the geo_filtering step and
#  BEFORE the word-tokenization step at the pre-processing file. ####

## -------------------------------------------------------------- ##

## Here we define the label constants. ##
import re
from snorkel.labeling import labeling_function, PandasLFApplier
from snorkel.labeling.model.label_model import LabelModel

ABSTAIN = -1 # Meaning this LF(labeling function) cannot decide for this example.
SME = 1 # Meaning this LF(labeling function) believes the article is about an SME.
NOT_SME = 0 # Meaning this LF(labeling function) believes the article is not about an SME.
            # (maybe a big company, or not a company at all).
## -------------------------------------------------------------- ##

## Here we have the labeling functions (LFs). They are small, user-written rules that are used to detect: 
#  (keywords, regex, patterns, external lookups, etc.).
#  They all take a row x as an input (a dictionary-like object),
#  look at the "clean" column, and finally return SME, NOT_SME, or ABSTAIN. ##

# Explicit SME mentions → mkb, midden- en kleinbedrijf.
@labeling_function()
def lf_explicit_sme(x):
    text = (x.get("clean_geo") or "").lower()
    return SME if re.search(
        r"\b("
        r"mkb|midden- en kleinbedrijf|kmo|kleine onderneming|kleine bedrijven|"
        r"small and medium enterprise|"
        r"mkb-ondernemers?|mkb-bedrijven?|mkb-sector|mkb'er(s)?|"
        r"ondernemersvereniging|ondernemersloket"
        r")\b",
        text
    ) else ABSTAIN

# Generic "bedrijf" mentions → captures generic “bedrijf/onderneming” references.
@labeling_function()
def lf_generic_bedrijf(x):
    text = (x.get("clean_geo") or "").lower()
    return SME if re.search(
        r"\b("
        r"(klein(e|er)e?\s+)?bedrijf(fen)?|onderneming(en)?|zaak|zaken|"
        r"ondernemingshuis|ondernemersloket|bedrijfsleven|"
        r"organisatie(s)?\s+(in\s+de\s+)?(regio|provincie|gemeente)|"
        r"bedrijfstak|bedrijfssector"
        r")\b",
        text
    ) else ABSTAIN

# General sector terms → horeca, winkel, bouwbedrijf, transport, etc. (from CBS)
@labeling_function()
def lf_general_sector_terms(x):
    text = (x.get("clean_geo") or "").lower()
    return SME if re.search(
        r"\b("
        # Agriculture
        r"landbouw|akkerbouw|tuinbouw|bosbouw|visserij|fishing|forestry|agriculture|farm(er|ing)|greenhouse|kwekerij|veeteelt|pluimvee"
        r"|"
        # Mining
        r"delfstoffenwinning|mining|mijnbouw|groeve"
        r"|"
        # Industry / Energy / Water / Waste
        r"industrie|fabriek(en)?|manufacturing|produceren|productiebedrijf|energievoorziening|energy supply|energiebedrijf"
        r"|waterbedrijf|watermaatschappij|afvalbeheer|waste management|recycling|milieudienst"
        r"|"
        # Construction
        r"bouwnijverheid|bouwbedrijf|aannemer(s)?|installatiebedrijf|constructie|bouwsector|bouwvakker"
        r"|"
        # Trade / Retail
        r"handel|detailhandel|groothandel|winkel|shop|store|supermarkt|bakker(ij)?|slager(ij)?|kapsalon|drogisterij|webwinkel|e-commerce"
        r"|"
        # Transport / Storage
        r"vervoer|transport(bedrijf)?|logistiek|opslag|magazijn|koerier(s)?|distributiecentrum|transport and storage"
        r"|"
        # Hospitality
        r"horeca|restaurant|café|bar|hotel|snackbar|catering|hospitality"
        r"|"
        # Info & Communication + Cybersecurity extensions
        r"informatie en communicatie|ict|it|softwarebedrijf|software company|telecom|mediabedrijf|uitgeverij|communicatiebureau"
        r"|cyberbedrijf|cybersecurity|cyberweerbaarheid|digitale weerbaarheid|digitale veiligheid|informatiebeveiliging|"
        r"beveiligingsbedrijf|veilig ondernemen|cybercrime|phishing|ransomware"
        r"|"
        # Financial
        r"financiële dienstverlening|boekhoud(kantoor)?|accountantskantoor|administratiekantoor|verzekeringskantoor"
        r"|"
        # Real Estate
        r"makelaar|vastgoed|real estate|woningcorporatie|property rental|onroerend goed"
        r"|"
        # Specialist Business Services
        r"adviesbureau|consultancy|marketingbureau|ingenieursbureau|juridisch advies|advocatenkantoor|specialist business services"
        r"|"
        # Rental & Other Biz Services
        r"uitzendbureau|detacheringsbureau|schoonmaakbedrijf|beveiligingsbedrijf|facility services"
        r"|"
        # Education / Health / Culture
        r"onderwijsinstelling|basisschool|middelbare school|kinderopvang|school|training|opleidingsinstituut"
        r"|gezondheidszorg|welzijnszorg|praktijk|kliniek|ziekenhuis|fysiotherapie|zorginstelling"
        r"|sportschool|fitnesscentrum|theater|museum|vereniging|cultureel centrum|recreatiebedrijf"
        r")\b",
        text
    ) else ABSTAIN


# Generic entrepreneurship terms → ondernemer, zelfstandige, start-up, zzp.
@labeling_function()
def lf_generic_entrepreneurship(x):
    text = (x.get("clean_geo") or "").lower()
    return SME if re.search(
        r"\b(ondernemer|ondernemers|zelfstandige|zelfstandigen|zzp|start-?up|startups?|ondernemerschap|freelancer|freelancers|bedrijf starten|bedrijf oprichten)\b",
        text
    ) else ABSTAIN

@labeling_function()
def lf_international_politics(x):
    text = (x.get("clean_geo") or "").lower()
    # Matches words indicating international politics or wars
    return NOT_SME if re.search(
        r"\b(uk|starmer|russische aanval|v.n.|trump|europa|oorlog|russia|usa|united states|nato)\b", 
        text
    ) else ABSTAIN

@labeling_function()
def lf_politics_domestic(x):
    text = (x.get("clean_geo") or "").lower()
    return NOT_SME if re.search(
        r"\b(politiek|partij|stemmen|verkiezing|minister|parlement|partijleider|raad|gemeente|beleid)\b", 
        text
    ) else ABSTAIN

# Government or personnel appointment news → not relevant for SMEs
@labeling_function()
def lf_government_only(x):
    text = (x.get("clean_geo") or "").lower()
    return NOT_SME if re.search(
        r"\b("
        r"ministerie|departement|justitie|veiligheid|algemene\s+bestuursdienst|"
        r"directeur|directie|benoemd|benoeming|aanstelling|"
        r"functie|carrière|vacature|nieuwe\s+positie|chief|officer|"
        r"bestuurder|leidinggevende|manager|plaatsvervangend"
        r")\b",
        text
    ) else ABSTAIN

@labeling_function()
def lf_accidents_crime(x):
    text = (x.get("clean_geo") or "").lower()
    return NOT_SME if re.search(
        r"\b(ongeluk|drama|ramp|brand|dood|moord|criminaliteit|aanrijding|botsing|explosie|verkrachting|rellen)\b", 
        text
    ) else ABSTAIN

@labeling_function()
def lf_sme_cybercrime(x):
    text = (x.get("clean_geo") or "").lower()
    if re.search(r"\b(mkb|bedrijf|ondernemer|zaak|organisatie)\b", text) and \
       re.search(r"\b(cyber|digitale|phishing|ransomware|weerbaarheid|veiligheid|cybercrime|hack)\b", text):
        return SME
    return ABSTAIN

@labeling_function()
def lf_sports_entertainment(x):
    text = (x.get("clean_geo") or "").lower()
    return NOT_SME if re.search(
        r"\b(honkbal|voetbal|sport|theater|film|serie|muziek|concert|festival|wedstrijden)\b", 
        text
    ) else ABSTAIN


## -------------------------------------------------------------- ##

## This function applies the whole weak supervision pipeline. ##
def run_snorkel(df, lfs=None, min_conf=0.6):
    """
    Apply Snorkel LabelModel using defined labeling functions.
    Adds `sme_probability` and `sme_label` columns to df.
    """
    if lfs is None:
        lfs = [
    lf_explicit_sme,
    lf_generic_bedrijf,
    lf_general_sector_terms,
    lf_generic_entrepreneurship,
    lf_international_politics,
    lf_accidents_crime,
    lf_politics_domestic,
    lf_sme_cybercrime,
    lf_sports_entertainment,
    lf_government_only
]

    # 1) Apply LFs:
    applier = PandasLFApplier(lfs=lfs)
    L = applier.apply(df=df)

    # Debug: check LF coverage / overlap / conflicts
    debug_lf_coverage(df, lfs)

    # 2) Train LabelModel (LabelModel learns how to combine noisy LF votes into one probabilistic label.):
    label_model = LabelModel(cardinality=2, verbose=True)
    label_model.fit(L_train=L, n_epochs=200, log_freq=50, seed=123)

    # 3) Get probabilistic labels:
    probs = label_model.predict_proba(L=L)  # shape (n,2)
    df["sme_probability"] = probs[:, 1]
    df["sme_label"] = (df["sme_probability"] >= min_conf).astype(int)

    return df, label_model
## -------------------------------------------------------------- ##

def debug_lf_coverage(df, lfs):
    for lf in lfs:
        votes = df.apply(lf, axis=1)
        coverage = (votes != -1).mean()
        pos = (votes == 1).mean()
        neg = (votes == 0).mean()
        print(f"{lf.name:<30} coverage={coverage:.2f}, SME={pos:.2f}, NOT_SME={neg:.2f}")