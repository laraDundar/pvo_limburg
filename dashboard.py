import streamlit as st
import pandas as pd
import json
import os
from streamlit_folium import st_folium
import folium
from folium.plugins import HeatMap, MarkerCluster
from datetime import datetime, date

#streamlit help
def _rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


def _parse_to_date(x):
    if isinstance(x, date):
        return x
    if isinstance(x, str):
        try:
            return datetime.fromisoformat(x).date()
        except Exception:
            pass
    return datetime.today().date()

def _clamp_date_range(min_d: date, max_d: date, value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return (min_d, max_d)
    sd, ed = _parse_to_date(value[0]), _parse_to_date(value[1])
    if sd < min_d: sd = min_d
    if sd > max_d: sd = max_d
    if ed < min_d: ed = min_d
    if ed > max_d: ed = max_d
    if sd > ed:
        sd, ed = min_d, max_d
    return (sd, ed)



#preset storage
PRESETS_FILE = os.path.join("cache", "filter_presets.json")

def _ensure_cache_dir():
    os.makedirs("cache", exist_ok=True)
    os.makedirs("digests", exist_ok=True)

def _load_presets():
    _ensure_cache_dir()
    if os.path.exists(PRESETS_FILE):
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_presets(presets: dict):
    _ensure_cache_dir()
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2, default=str)




# all geoNames in Limburg
@st.cache_data
def limburg_box():
    geo_df = pd.read_csv(
        "geoNames\\NL.txt", 
        sep="\t", 
        header=None,
        dtype={4: float, 5: float},  # lat/lon columns
        names=[
            "geonameid","name","ascii_name","alternate_names",
            "latitude","longitude","feature_class","feature_code","country_code",
            "cc2","admin1_code","admin2_code","admin3_code","admin4_code",
            "population","elevation","dem","timezone","modification_date"
        ]
    )

    geo_df = geo_df[["name", "latitude", "longitude", "admin1_code"]]
    geo_in_box = geo_df[geo_df["admin1_code"] == 5]



    locations_in_box = set(geo_in_box['name'].str.lower())
    return locations_in_box
limburg = limburg_box()

#--------------------------------

FILE_PATH = "keywords\\all_articles_keywords.json"
st.title("Dashboard Prototype (I)")

try:

    with open(FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    df = pd.json_normalize(data)

    # st.subheader(f"Data loaded from: `{FILE_PATH}`")
    # st.write(f"{len(df)} Articles")

    # -------------------------
    # Filtering UI
    # -------------------------
    st.sidebar.header("Filter Options")

    # Column selector
    # cols_to_show = st.sidebar.multiselect(
    #     "Select columns to display",
    #     options=df.columns.tolist(),
    #     default=df.columns.tolist()
    # )



    #session-state defaults, global options for reset/presets
    feed_options_all = df["feed"].dropna().unique().tolist() if "feed" in df.columns else []
    if "published" in df.columns:
        _tmp_dates = pd.to_datetime(df["published"], errors="coerce")
        _min_date = _tmp_dates.min().date() if _tmp_dates.notna().any() else datetime.today().date()
        _max_date = _tmp_dates.max().date() if _tmp_dates.notna().any() else datetime.today().date()
    else:
        _min_date = _max_date = datetime.today().date()

    if "text_filter" not in st.session_state: st.session_state.text_filter = ""
    if "selected_feeds" not in st.session_state: st.session_state.selected_feeds = feed_options_all
    if "location_search" not in st.session_state: st.session_state.location_search = ""
    if "date_range" not in st.session_state: st.session_state.date_range = (_min_date, _max_date)
    if "_pending_preset" in st.session_state:
        p = st.session_state.pop("_pending_preset")
        st.session_state.text_filter = p.get("text_filter", "")
        st.session_state.selected_feeds = p.get("selected_feeds", feed_options_all)
        st.session_state.location_search = p.get("location_search", "")
        dr = p.get("date_range", (_min_date, _max_date))
        if isinstance(dr, (list, tuple)) and len(dr) == 2:
            st.session_state.date_range = (_parse_to_date(dr[0]), _parse_to_date(dr[1]))
        else:
            st.session_state.date_range = (_min_date, _max_date)

    #text search filter
    text_filter = st.sidebar.text_input("Search text (applies to all string columns)", key="text_filter")



    filtered_df = df.copy()
    if text_filter:
        mask = pd.Series(False, index=filtered_df.index)
        for col in filtered_df.select_dtypes(include=["object", "string"]).columns:
            mask |= filtered_df[col].astype(str).str.contains(text_filter, case=False, na=False)
        filtered_df = filtered_df[mask]

    # Feed filter
    if "feed" in filtered_df.columns:
        feed_options = filtered_df["feed"].dropna().unique().tolist()
        selected_feeds = st.sidebar.multiselect(
            "Filter by feed", options=feed_options, default=st.session_state.get("selected_feeds", feed_options_all), key="selected_feeds"
        )
        filtered_df = filtered_df[filtered_df["feed"].isin(selected_feeds)]

    # -------------------------
    # Location filter
    # -------------------------
    location_search = st.sidebar.text_input(
        "Filter by locations (type one or more tags, separated by commas)",
        value=st.session_state.location_search, key="location_search"
    )

    if location_search.strip():
        search_tags = [tag.strip() for tag in location_search.split(",") if tag.strip()]
        filtered_df = filtered_df[
            filtered_df["locations"].apply(
                lambda loc_list: any(
                    any(search_tag.lower() in loc.lower() for loc in loc_list)
                    for search_tag in search_tags
                )
                if isinstance(loc_list, list) else False
            )
        ]

    # -------------------------
    # Date filter new
    # -------------------------
    date_col = "published"
    if date_col in df.columns:
        start_d, end_d = st.session_state.get("date_range", (_min_date, _max_date))
        start_d, end_d = _clamp_date_range(_min_date, _max_date, (start_d, end_d))

        _picked = st.sidebar.date_input(
            "Filter by date",
            value=(start_d, end_d),
            min_value=_min_date,
            max_value=_max_date,
            key="date_range_widget",
        )

        if isinstance(_picked, (list, tuple)) and len(_picked) == 2:
            start_date, end_date = _picked
        else:
            start_date = end_date = _picked

        start_date, end_date = _clamp_date_range(_min_date, _max_date, (start_date, end_date))
        st.session_state.date_range = (start_date, end_date)

        tmp_dates = pd.to_datetime(filtered_df[date_col], errors="coerce")
        filtered_df = filtered_df.loc[tmp_dates.notna()].copy()
        tmp_dates = tmp_dates.loc[tmp_dates.notna()]
        filtered_df = filtered_df[
            (tmp_dates.dt.date >= start_date) & (tmp_dates.dt.date <= end_date)
            ]

    # -------------------------
    # Display filtered DataFrame
    # -------------------------
    # st.subheader("📈 Filtered DataFrame")
    # st.dataframe(filtered_df[cols_to_show])


    #filter summary
    _sd, _ed = st.session_state.get("date_range", (_min_date, _max_date))
    st.markdown(
        f"**Current filters:** {len(st.session_state.get('selected_feeds', []))} feed(s) • "
        f"{_sd} → {_ed} • search: “{st.session_state.get('text_filter','')}” • "
        f"locations: “{st.session_state.get('location_search','')}”"
    )
    st.write(f"**{len(filtered_df)}** articles match.")


    #presets
    st.sidebar.markdown("---")
    st.sidebar.subheader("Presets")
    _presets = _load_presets()
    _names = ["—"] + list(_presets.keys())
    c_load, c_btn = st.sidebar.columns([3,1])
    with c_load:
        _sel = c_load.selectbox("Load preset", options=_names)
    with c_btn:
        if st.button("Load"):
            if _sel != "—":
                st.session_state["_pending_preset"] = _presets[_sel]
                _rerun()

    _new_preset = st.sidebar.text_input("Save current as…", placeholder="e.g., Limburg 90d")
    if st.sidebar.button("Save preset") and _new_preset:
        _presets[_new_preset] = {
            "text_filter": st.session_state.text_filter,
            "selected_feeds": st.session_state.selected_feeds,
            "location_search": st.session_state.location_search,
            "date_range": list(st.session_state.date_range),
        }
        _save_presets(_presets)
        st.sidebar.success(f"Saved preset “{_new_preset}”.")

    #reset
    if st.sidebar.button("Reset filters"):
        st.session_state["_pending_preset"] = {
            "text_filter": "",
            "selected_feeds": feed_options_all,
            "location_search": "",
            "date_range": (_min_date, _max_date),
        }
        _rerun()

    # -------------------------
    # Map Section — Using Cached Geocoded Data
    # -------------------------
    st.subheader("Interactive Article Map")

    def geocode_locations_with_cache(rows, cache_file="cache/geocode_cache.json"):
        """Load cached coordinates (no warnings, no API calls)."""
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)

        # Load cache only
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        else:
            cache = {}

        geo_records = []
        loc_to_titles = {}

        # Collect unique locations
        for _, row in rows.iterrows():
            locs = row.get("locations", [])
            if isinstance(locs, list):
                for loc in locs:
                    loc_to_titles.setdefault(loc, []).append(row.get("title", "Untitled Article"))

        # Use only cached coordinates
        for loc, titles in loc_to_titles.items():
            if loc in cache:
                geo_data = cache[loc]
                geo_records.append({
                    "location": loc,
                    "lat": geo_data["lat"],
                    "lon": geo_data["lon"],
                    "titles": titles
                })
            # Skip if not in cache
            else:
                continue

        return geo_records

    geo_records = geocode_locations_with_cache(filtered_df)

    # Display the map and types of it
    if geo_records:

        map_mode = st.radio("Map mode", ["Heatmap", "Markers"], horizontal=True)

        m = folium.Map(location=[52.1, 5.3], zoom_start=7)

        if map_mode == "Heatmap":
            heat_data = [[r["lat"], r["lon"], len(r["titles"])] for r in geo_records]
            HeatMap(heat_data, radius=18, blur=15, max_zoom=6).add_to(m)
        else:
            cluster = MarkerCluster().add_to(m)
            for record in geo_records:
                popup_html = "<b>{}</b><br>{}".format(
                    record["location"],
                    "<br>".join([f"• {t}" for t in record["titles"]])
                )
                folium.Marker(
                    [record["lat"], record["lon"]],
                    popup=popup_html,
                    tooltip=f"{record['location']} ({len(record['titles'])} article(s))",
                    icon=folium.Icon(color="blue", icon="info-sign"),
                ).add_to(cluster)

        st_folium(m, width=1000, height=600)
        st.write(f"{len(filtered_df)} Articles")
        st.write(f"Showing {len(geo_records)} unique locations on the map")
    else:
        st.info("No cached geocoded locations found.")
    
    
    # -----------------------------------------
    # ARTICLE SPOTLIGHT
    # -----------------------------------------

    # heuristic 1: in Limburg
    
    in_limburg_df = filtered_df[
        filtered_df['locations'].apply(
            lambda tags: any(tag.lower() in limburg for tag in tags)
        )
    ].copy()

    # heuristic 2: compare to top keywords
    #???

    # heuristic 3: sme probabilty > 0.9 or head k?
    k = 5
    sme_df = filtered_df.sort_values(by='sme_probability', ascending=False).head(k)

    spotlight_df = pd.concat([in_limburg_df, sme_df])
    spotlight_df = spotlight_df[~spotlight_df.index.duplicated(keep='first')]
    st.subheader(f"Spotlight")
    st.dataframe(spotlight_df)


    # -------------------------
    # Top Keywords from Filtered Articles
    # -------------------------
    st.subheader("Top Keywords (Filtered Selection)")

    def extract_keywords(df):
        all_keywords = []
        for _, row in df.iterrows():
            kw_list = row.get("keywords", [])
            if isinstance(kw_list, list):
                for kw in kw_list:
                    if isinstance(kw, dict) and "word" in kw and "score" in kw:
                        all_keywords.append(kw)
        return all_keywords

    keywords = extract_keywords(filtered_df)

    if keywords:
        kw_df = pd.DataFrame(keywords)
        top_keywords = (
            kw_df.groupby("word", as_index=False)["score"]
            .sum()
            .sort_values("score", ascending=False)
            .head(20)
        )

        st.bar_chart(
            data=top_keywords.set_index("word")["score"],
            use_container_width=True
        )

        st.dataframe(top_keywords, use_container_width=True)
        st.caption("Keywords aggregated across all articles after filtering.")
    else:
        st.info("No keywords found for the filtered selection.")


    # with st.expander("Show raw JSON data"):
    #     st.json(data)

except FileNotFoundError:
    st.error(f"File not found at path: `{FILE_PATH}`")
except json.JSONDecodeError:
    st.error("The file is not valid JSON.")
except Exception as e:
    st.error(f"Unexpected error: {e}")
