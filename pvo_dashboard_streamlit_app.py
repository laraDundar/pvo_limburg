# PVO Limburg — News Monitor Prototype (Streamlit)
# ------------------------------------------------
# Quick start:
#   pip install streamlit pandas numpy plotly folium streamlit-folium python-dateutil
#   streamlit run pvo_dashboard_streamlit_app.py
#
# Expected data inputs (any that exists will be loaded, in this order):
#   - nos_articles_economie.json  (output of your scraper)
#   - nos_articles.json
#   - nos_articles_economie.csv / nos_articles.csv
#
# Optional (to enable a real choropleth map):
#   Put a NL provinces GeoJSON at data/nl_provinces.geojson (WGS84). A widely-used one is available from CBS/PDOK.
#   Otherwise the app will show an interactive bar chart instead of the province choropleth.
#
# Feedback covered:
#   - "Separate filter into parts of Limburg or make map interactive" → Province filter + Limburg subregion filter. Optional interactive map.
#   - "Make filter savable" → Presets saved to ~/.pvo_limburg/presets.json (Save / Load / Delete).
#   - "Consider digest and notification" → Export CSV and generate an HTML digest file you can email/schedule externally.
#
# Notes:
#   - Province/subregion inference is heuristic, based on place-name evidence. It’s transparent and overridable.
#   - Crime type is derived by keyword rules (tweak CRIME_KEYWORDS below).

from __future__ import annotations
import os
import io
import json
from pathlib import Path
from datetime import datetime, date
from collections import Counter, defaultdict

import pandas as pd
import numpy as np
import plotly.express as px

import streamlit as st

# Optional map libs
try:
    import folium  # type: ignore
    from streamlit_folium import st_folium  # type: ignore
    _MAP_OK = True
except Exception:
    _MAP_OK = False

# ----------------------------
# Config & constants
# ----------------------------
APP_TITLE = "PVO Limburg — News Monitor Prototype"
DATA_CANDIDATES = [
    "nos_articles_economie.json",
    "nos_articles.json",
    "nos_articles_economie.csv",
    "nos_articles.csv",
]
GEOJSON_PATH = Path("data/nl_provinces.geojson")  # optional
PRESETS_PATH = Path.home() / ".pvo_limburg" / "presets.json"
DIGEST_DIR = Path("digests")
DIGEST_DIR.mkdir(parents=True, exist_ok=True)
PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)

# simple Dutch & English stopwords (extend as needed)
STOPWORDS = set(
    """
    de het een en of maar als dan toch dus voor met zonder over naar uit aan op bij door ook al niet wel geen om te van tot
    je jij u hij zij ze we wij jullie ik hun hem haar die dat dit deze deze daar hier er waar omdat terwijl zodra zodat
    is zijn was waren wordt worden ben bent waren worden kan kunnen moet moeten zal zullen hebben heeft hadden doen doet deden
    the a an and or but if then so for with without about into to from at by of on in out up down it its they them he she we you i
    this that these those here there what when where why how which who whose been being be am are were will would should could
    over onder boven tegen volgens tussen meer minder veel weinig zeer nu later gisteren vandaag morgen elke iedere sommige
    """.split()
)

# Crime keyword rules (lowercased). Map → set of keywords. Adjust freely.
CRIME_KEYWORDS: dict[str, set[str]] = {
    "cybercrime": {
        "phishing", "ransomware", "ddos", "hack", "hacking", "malware", "spoof", "nep-mail", "nepmail",
        "nepwebsite", "oplichting online", "credential", "datalek", "brute force", "botnet",
    },
    "drugs": {
        "drugs", "hennep", "xtc", "mdma", "meth", "cocaïne", "cocaine", "synthetische", "drugslab",
        "chemisch", "chemicaliën", "productielocaties", "speed",
    },
    "fraude": {"fraude", "oplichting", "vals", "valse", "nep", "factuur", "helpdeskfraude", "bankhelpdesk"},
    "witwassen": {"witwas", "witwassen", "geldsmokkel", "cash center", "onder toezicht"},
    "geweld": {
        "geweld", "schietpartij", "steekpartij", "mishandeling", "overval", "bedreiging", "aanranding", "diefstal met geweld",
    },
    "ondermijning": {"ondermijning", "productielocaties", "crimineel", "lofz", "loods", "chemische apparatuur"},
}

# Limburg subregions (heuristic buckets). Municipality names as they’re likely to appear in text.
LIMBURG_SUBREGIONS: dict[str, set[str]] = {
    "Noord": {
        "venlo", "venray", "horst aan de maas", "peel en maas", "beesel", "bergen", "gennep", "mook en middelaar",
        "sevenum", "tegelen", "blitterswijck",
    },
    "Midden": {
        "roermond", "weert", "leudal", "nederweert", "maasgouw", "roerdalen", "echt-susteren", "thorn", "heythuysen",
    },
    "Zuid": {
        "maastricht", "heerlen", "sittard-geleen", "kerkrade", "landgraaf", "brunssum", "stein", "beek", "beekdaelen",
        "eijsden-margraten", "meerssen", "simpelveld", "vaals", "valkenburg aan de geul", "gulpen-wittem", "voerendaal",
    },
}

# ----------------------------
# Utilities
# ----------------------------

def _read_any(path: Path | str) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError
    if path.suffix.lower() == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported file: {path}")


def load_articles() -> pd.DataFrame:
    for cand in DATA_CANDIDATES:
        try:
            df = _read_any(cand)
            st.sidebar.success(f"Loaded data: {cand}")
            return normalize_schema(df)
        except Exception:
            continue
    st.error("No data file found. Put nos_articles_economie.json (or csv) in this folder.")
    return pd.DataFrame(columns=[
        "feed", "title", "url", "published", "summary", "full_text",
        "sme_probability", "sme_label", "country", "country_score", "clean_geo", "locations", "country_evidence",
    ])


def normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # unify text fields
    for col in ["title", "summary", "full_text", "clean_geo"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    # published → datetime
    if "published" in df.columns:
        df["published_dt"] = pd.to_datetime(df["published"], errors="coerce", utc=True).dt.tz_convert(None)
    else:
        df["published_dt"] = pd.NaT

    # SME columns
    if "sme_probability" not in df.columns:
        df["sme_probability"] = 0.0
    if "sme_label" not in df.columns:
        df["sme_label"] = (df["sme_probability"] >= 0.6).astype(int)

    # country columns
    if "country" not in df.columns:
        df["country"] = "uncertain"
    if "country_score" not in df.columns:
        df["country_score"] = 0.0

    # evidence parsing → list of pairs or strings
    if "country_evidence" not in df.columns:
        df["country_evidence"] = [[] for _ in range(len(df))]
    else:
        df["country_evidence"] = df["country_evidence"].apply(_coerce_evidence)

    # long text for searching
    df["search_blob"] = (
            df["title"].str.lower() + " " + df["summary"].str.lower() + " " + df["full_text"].str.lower()
    )

    # derive crime tags
    df["crime_tags"] = df["search_blob"].apply(detect_crime_tags)

    # province & subregion (heuristic) limited to Limburg for now
    prov, subr = zip(*df.apply(_infer_province_subregion, axis=1))
    df["province_inferred"] = prov
    df["limburg_part"] = subr

    # convenience
    df["date"] = df["published_dt"].dt.date

    return df


def _coerce_evidence(val):
    if isinstance(val, list):
        # items may be [place, cc] or strings
        out = []
        for item in val:
            if isinstance(item, (list, tuple)) and item:
                out.append(str(item[0]))
            else:
                out.append(str(item))
        return out
    try:
        return [str(val)] if pd.notna(val) else []
    except Exception:
        return []


def detect_crime_tags(text: str | list[str]) -> list[str]:
    if isinstance(text, list):
        blob = " ".join([str(t).lower() for t in text])
    else:
        blob = str(text).lower()
    found = []
    for tag, kws in CRIME_KEYWORDS.items():
        if any(k in blob for k in kws):
            found.append(tag)
    return found or ["other"]


def _infer_province_subregion(row) -> tuple[str | None, str | None]:
    """Naive province/subregion inference based on place-name evidence.
    Returns (province, limburg_part) where province is e.g. "Limburg" or None, and limburg_part ∈ {Noord,Midden,Zuid,None}.
    """
    blob = (row.get("clean_geo") or "") + " " + (row.get("title") or "") + " " + (row.get("summary") or "")
    blob = blob.lower()
    evid = [e.lower() for e in row.get("country_evidence", [])]

    # Only try to guess Limburg; other provinces left as None
    for part, names in LIMBURG_SUBREGIONS.items():
        for name in names:
            if name in blob or any(name in e for e in evid):
                return "Limburg", part
    return ("Limburg", None) if "limburg" in blob else (None, None)


# ----------------------------
# Presets (saved filters)
# ----------------------------

def load_presets() -> dict:
    if PRESETS_PATH.exists():
        try:
            return json.load(open(PRESETS_PATH, "r", encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_presets(obj: dict) -> None:
    with open(PRESETS_PATH, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ----------------------------
# Filtering logic
# ----------------------------

def apply_filters(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    out = df.copy()
    # text search
    q = (f.get("q") or "").strip().lower()
    if q:
        out = out[out["search_blob"].str.contains(q, na=False)]

    # date range
    since, until = f.get("date_range", (None, None))
    if since:
        out = out[out["date"] >= since]
    if until:
        out = out[out["date"] <= until]

    # province
    prov = f.get("province")
    if prov and prov != "Any":
        out = out[out["province_inferred"] == prov]

    # limburg part
    part = f.get("limburg_part")
    if part and part != "Any":
        out = out[out["limburg_part"] == part]

    # crime tags (any)
    tags = f.get("crime_tags") or []
    if tags:
        out = out[out["crime_tags"].apply(lambda xs: any(t in xs for t in tags))]

    # SME probability threshold
    min_sme = f.get("min_sme", 0.0)
    out = out[out["sme_probability"] >= float(min_sme)]

    return out.sort_values("published_dt", ascending=False)


# ----------------------------
# Digest generation
# ----------------------------

def make_digest_html(df: pd.DataFrame, filters: dict) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    top_terms = compute_top_terms(df, n=12)
    items = []
    for _, r in df.head(100).iterrows():
        prob = f"{r['sme_probability']:.2f}"
        date_str = r.get("published_dt")
        if pd.notna(date_str):
            date_str = pd.to_datetime(date_str).strftime("%Y-%m-%d %H:%M")
        else:
            date_str = ""
        items.append(f"""
        <li>
          <b>{r['title']}</b> &mdash; <i>{date_str}</i><br/>
          <a href="{r['url']}">Open source</a> | SME p={prob} | Tags: {', '.join(r['crime_tags'])}
          <div style='color:#555; margin-top:4px'>{r['summary']}</div>
        </li>
        """)

    html = f"""
    <html><head><meta charset='utf-8'><title>PVO Limburg Digest</title></head>
    <body>
      <h2>PVO Limburg — Daily Digest</h2>
      <p><small>Generated {ts}</small></p>
      <h3>Filters</h3>
      <pre>{json.dumps(filters, ensure_ascii=False, indent=2)}</pre>
      <h3>Top terms</h3>
      <ul>{''.join(f'<li>{w} — {c}</li>' for w,c in top_terms)}</ul>
      <h3>Articles ({len(df)})</h3>
      <ol>{''.join(items)}</ol>
    </body></html>
    """
    return html


# ----------------------------
# Analytics helpers
# ----------------------------

def compute_top_terms(df: pd.DataFrame, n: int = 10) -> list[tuple[str, int]]:
    cnt = Counter()
    for txt in (df["search_blob"] if "search_blob" in df.columns else []):
        for w in str(txt).split():
            w = w.strip(".,:;()[]\"'!?“”’`).-/_")
            if not w or w in STOPWORDS or w.isdigit() or len(w) < 3:
                continue
            cnt[w] += 1
    return cnt.most_common(n)


def counts_by_province(df: pd.DataFrame) -> pd.DataFrame:
    # We only infer Limburg currently; everything else is None → group under "Other/Unknown"
    prov = df["province_inferred"].fillna("Other/Unknown")
    return prov.value_counts().rename_axis("province").reset_index(name="count")


def counts_by_limburg_part(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["province_inferred"] == "Limburg"
    sub = df.loc[mask, "limburg_part"].fillna("Unspecified")
    return sub.value_counts().rename_axis("part").reset_index(name="count")


# ----------------------------
# UI
# ----------------------------

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# Data
df = load_articles()

# Sidebar — filters & presets
st.sidebar.header("Filters")

# presets
presets = load_presets()
load_choice = st.sidebar.selectbox("Load preset", ["(none)"] + sorted(presets.keys()))
if load_choice != "(none)":
    st.session_state["filters"] = presets[load_choice]

# Current filters (session)
filters = st.session_state.get("filters", {})

# Text search
filters["q"] = st.sidebar.text_input("Free text", value=filters.get("q", ""))

# Date range
if not df.empty and df["date"].notna().any():
    min_d = df["date"].min()
    max_d = df["date"].max()
else:
    min_d = date(2024, 1, 1)
    max_d = date.today()

filters["date_range"] = st.sidebar.date_input(
    "Date range", value=(filters.get("date_range", (min_d, max_d))), min_value=min_d, max_value=max_d
)

# Province & Limburg part
filters["province"] = st.sidebar.selectbox("Province", ["Any", "Limburg"], index=(1 if filters.get("province") == "Limburg" else 0))
if filters.get("province") == "Limburg":
    parts = ["Any", "Noord", "Midden", "Zuid"]
    try:
        idx = parts.index(filters.get("limburg_part", "Any"))
    except ValueError:
        idx = 0
    filters["limburg_part"] = st.sidebar.radio("Limburg part", parts, index=idx, horizontal=True)
else:
    filters["limburg_part"] = "Any"

# Crime tags
all_tags = sorted(CRIME_KEYWORDS.keys()) + ["other"]
filters["crime_tags"] = st.sidebar.multiselect("Crime type(s)", all_tags, default=filters.get("crime_tags", []))

# SME threshold
filters["min_sme"] = st.sidebar.slider("Min. SME probability", 0.0, 1.0, float(filters.get("min_sme", 0.4)), 0.05)

# Save/delete preset
st.sidebar.subheader("Presets")
new_name = st.sidebar.text_input("Preset name")
col_a, col_b = st.sidebar.columns(2)
if col_a.button("Save current"):
    if not new_name.strip():
        st.sidebar.error("Give the preset a name.")
    else:
        presets = load_presets()
        presets[new_name.strip()] = filters
        save_presets(presets)
        st.sidebar.success(f"Saved preset '{new_name.strip()}'")
if col_b.button("Delete loaded") and load_choice != "(none)":
    presets.pop(load_choice, None)
    save_presets(presets)
    st.sidebar.warning(f"Deleted preset '{load_choice}'")

# Persist session filters
st.session_state["filters"] = filters

# Apply filters
filtered = apply_filters(df, filters)

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Articles (filtered)", len(filtered))
try:
    last_dt = pd.to_datetime(filtered["published_dt"].max()).strftime("%Y-%m-%d %H:%M") if not filtered.empty else "—"
except Exception:
    last_dt = "—"
k2.metric("Latest item", last_dt)
k3.metric("% SME≥thr", f"{( (filtered['sme_probability'] >= filters['min_sme']).mean() * 100 if len(filtered)>0 else 0):.0f}%")
# simple tag with most hits
tag_counts = Counter(t for tags in filtered.get("crime_tags", []) for t in (tags if isinstance(tags, list) else []))
most_tag = tag_counts.most_common(1)[0][0] if tag_counts else "—"
k4.metric("Top crime tag", most_tag)

st.divider()

# Layout: left list, right analytics
left, right = st.columns([0.58, 0.42])

with left:
    st.subheader("Articles")
    if filtered.empty:
        st.info("No articles match your filters.")
    else:
        for _, r in filtered.head(200).iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.markdown(f"**{r['title']}**")
                    meta = []
                    if pd.notna(r.get("published_dt")):
                        meta.append(pd.to_datetime(r["published_dt"]).strftime("%Y-%m-%d %H:%M"))
                    if r.get("province_inferred"):
                        meta.append(r.get("province_inferred"))
                    if r.get("limburg_part"):
                        meta.append(r.get("limburg_part"))
                    st.caption(" • ".join(meta))
                    st.write((r.get("summary") or r.get("full_text") or "").strip()[:350] + ("…" if len((r.get("summary") or r.get("full_text") or ""))>350 else ""))
                with col2:
                    st.progress(float(r.get("sme_probability", 0.0)))
                    st.caption("SME probability")
                    st.write(", ".join(r.get("crime_tags", [])))
                    st.link_button("Open source", r.get("url") or "#", use_container_width=True)
                # Evidence / quick view
                with st.expander("Quick view"):
                    st.write(r.get("full_text")[:1500] + ("…" if len(r.get("full_text") or "")>1500 else ""))
                    ev = ", ".join(r.get("country_evidence", []))
                    if ev:
                        st.caption(f"evidence: {ev}")

with right:
    st.subheader("Map & terms")

    # Province counts
    prov_df = counts_by_province(filtered)

    # Map (optional) or bar chart
    if _MAP_OK and GEOJSON_PATH.exists() and not prov_df.empty:
        try:
            with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
                nl_geo = json.load(f)
            # Expect a property 'name' or 'provincie' on features; normalize
            name_key = "name"
            if nl_geo.get("features") and "provincie" in nl_geo["features"][0]["properties"]:
                name_key = "provincie"

            # build mapping df for folium choropleth
            # Note: we only have 'Limburg' explicitly; others aggregate under Other/Unknown so map will mainly show Limburg value.
            m = folium.Map(location=[51.44, 5.71], zoom_start=7)
            folium.Choropleth(
                geo_data=nl_geo,
                data=prov_df,
                columns=["province", "count"],
                key_on=f"feature.properties.{name_key}",
                name="choropleth",
                fill_opacity=0.7,
                line_opacity=0.2,
                legend_name="Articles",
            ).add_to(m)
            st_folium(m, width=None, height=420)
        except Exception as e:
            st.info(f"Map unavailable ({e}). Showing bar chart instead.")
            fig = px.bar(prov_df, x="province", y="count", title="Articles by province (inferred)")
            st.plotly_chart(fig, use_container_width=True)
    else:
        fig = px.bar(prov_df, x="province", y="count", title="Articles by province (inferred)")
        st.plotly_chart(fig, use_container_width=True)

    #limburg parts
    sub_df = counts_by_limburg_part(filtered)
    if not sub_df.empty:
        fig2 = px.bar(sub_df, x="part", y="count", title="Limburg — by part")
        st.plotly_chart(fig2, use_container_width=True)



    #top terms
    terms = compute_top_terms(filtered, n=12)
    if terms:
        terms_df = pd.DataFrame(terms, columns=["term", "count"])
        fig3 = px.bar(terms_df, x="term", y="count", title="Top terms (current filters)")
        st.plotly_chart(fig3, use_container_width=True)

    #export
    st.markdown("### Export & Digest")
    csv_buf = io.StringIO()
    filtered.to_csv(csv_buf, index=False)
    st.download_button(
        "Export CSV", data=csv_buf.getvalue().encode("utf-8"), file_name="pvo_filtered_articles.csv", mime="text/csv"
    )

    if st.button("Generate HTML digest"):
        html = make_digest_html(filtered, filters)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = DIGEST_DIR / f"digest_{ts}.html"
        out_path.write_text(html, encoding="utf-8")
        st.success(f"Digest saved: {out_path}")
        st.code(str(out_path))






st.divider()
st.caption(
    "Prototype — province/subregion and crime tags are heuristics."
)
