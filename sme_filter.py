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

# Generic business/company mentions → captures generic “bedrijf/onderneming” references.
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
    """
    Returns SME if any of the sector-specific LFs (e.g., horeca, bouw, ict, etc.)
    detect a sector-related term in the text. Acts as a general 'sector mention' flag.
    """
    text = (x.get("clean_geo") or "").lower()

    # List of compiled regex patterns for efficiency
    sector_patterns = [
        # Agriculture
        r"\b(landbouw|akkerbouw|tuinbouw|bosbouw|visserij|kwekerij|veeteelt|pluimvee|fishing|farm(er|ing)|agriculture|greenhouse|forestry)\b",
        # Industry / Energy / Utilities
        r"\b(industrie|fabriek(en)?|productiebedrijf|manufacturing|energiebedrijf|energy supply|energievoorziening|waterbedrijf|watermaatschappij|afvalbeheer|recycling|waste management|milieudienst)\b",
        # Construction
        r"\b(bouwbedrijf|bouwnijverheid|aannemer(s)?|installatiebedrijf|constructie|bouwsector|bouwvakker)\b",
        # Retail / Trade
        r"\b(handel|detailhandel|groothandel|winkel|supermarkt|bakker(ij)?|slager(ij)?|kapsalon|drogisterij|webwinkel|e-commerce|shop|store)\b",
        # Transport / Logistics
        r"\b(transport(bedrijf)?|vervoer|logistiek|koerier(s)?|magazijn|opslag|distributiecentrum|transport and storage)\b",
        # Horeca
        r"\b(horeca|restaurant|café|bar|hotel|snackbar|catering|hospitality)\b",
        # IT / Media
        r"\b(ict|it|softwarebedrijf|software company|telecom|mediabedrijf|uitgeverij|communicatiebureau|cyberbedrijf|cybersecurity|digitale weerbaarheid|digitale veiligheid|informatiebeveiliging|veilig ondernemen)\b",
        # Finance
        r"\b(financiële dienstverlening|boekhoud(kantoor)?|accountantskantoor|administratiekantoor|verzekeringskantoor|bank|verzekeraar)\b",
        # Real estate
        r"\b(makelaar|vastgoed|real estate|woningcorporatie|onroerend goed|property rental)\b",
        # Professional / Legal / Consultancy
        r"\b(adviesbureau|consultancy|marketingbureau|ingenieursbureau|juridisch advies|advocatenkantoor|communicatieadvies|specialist business services)\b",
        # Health / Education
        r"\b(school|onderwijsinstelling|training|opleidingsinstituut|kinderopvang|basisschool|middelbare school|praktijk|kliniek|ziekenhuis|zorginstelling|fysiotherapie|gezondheidszorg|welzijnszorg)\b",
        # Recreation / Culture
        r"\b(sportschool|fitnesscentrum|sportvereniging|theater|museum|recreatiebedrijf|cultureel centrum|vereniging)\b",
    ]

    # Return SME if any sector pattern matches
    for pattern in sector_patterns:
        if re.search(pattern, text):
            return SME

    return ABSTAIN


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
    return SME if re.search(
        r"\b(mkb|bedrijf|ondernemer|zaak|organisatie)\b", text
    ) and re.search(
        r"\b(cyber|digitale|phishing|ransomware|hack|veiligheid|weerbaarheid|cybercrime)\b", text
    ) else ABSTAIN


@labeling_function()
def lf_sports_entertainment(x):
    text = (x.get("clean_geo") or "").lower()
    return NOT_SME if re.search(
        r"\b(honkbal|voetbal|sport|theater|film|serie|muziek|concert|festival|wedstrijden)\b", 
        text
    ) else ABSTAIN

@labeling_function()
def lf_business_crime(x):
    text = (x.get("clean_geo") or "").lower()
    # Business + crime co-occurrence
    if re.search(r"\b(bedrijf|onderneming|zaak|mkb|ondernemer|directeur|werkgever|adviesbureau)\b", text) and \
       re.search(r"\b(fraude|oplichting|witwassen|corruptie|diefstal|verduistering|afpersing|valsheid in geschrifte|onderzoek\s+naar|aangifte)\b", text):
        return SME
    return ABSTAIN

@labeling_function()
def lf_bankruptcy_only(x):
    text = (x.get("clean_geo") or "").lower()
    # Detect purely financial insolvency without crime
    if re.search(r"\b(failliet|faillissement|curator|doorstart|herstructurering)\b", text) and \
       not re.search(r"\b(fraude|oplichting|witwassen|corruptie|diefstal|verduistering|aangifte|onderzoek)\b", text):
        return NOT_SME
    return ABSTAIN



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
    # lf_international_politics,
    lf_accidents_crime,
    lf_politics_domestic,
    lf_sme_cybercrime,
    lf_sports_entertainment,
    lf_business_crime,
    #lf_bankruptcy_only,
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