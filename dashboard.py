import streamlit as st
import pandas as pd
import json
import os
import time
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import folium

# -------------------------
# 🔧 Hard-coded JSON file path
# -------------------------
FILE_PATH = "keywords\\all_articles_keywords.json"
st.title("📊 JSON to DataFrame Viewer (with Filters)")

try:
    # -------------------------
    # 📂 Load JSON data
    # -------------------------
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    df = pd.json_normalize(data)

    st.subheader(f"Data loaded from: `{FILE_PATH}`")
    st.write(f"Rows: {len(df)}, Columns: {len(df.columns)}")

    # -------------------------
    # 🔍 Sidebar Filtering UI
    # -------------------------
    st.sidebar.header("🔎 Filter Options")

    # Column selector
    cols_to_show = st.sidebar.multiselect(
        "Select columns to display",
        options=df.columns.tolist(),
        default=df.columns.tolist()
    )

    # Text search filter
    text_filter = st.sidebar.text_input("Search text (applies to all string columns)")

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
            "Filter by feed", options=feed_options, default=feed_options
        )
        filtered_df = filtered_df[filtered_df["feed"].isin(selected_feeds)]

    # -------------------------
    # 📍 Location filter
    # -------------------------
    location_search = st.sidebar.text_input(
        "Filter by locations (type one or more tags, separated by commas)",
        value=""
    )

    if location_search.strip():
        search_tags = [tag.strip() for tag in location_search.split(",") if tag.strip()]
        filtered_df = filtered_df[
            filtered_df["locations"].apply(
                lambda loc_list: any(
                    any(search_tag.lower() in loc.lower() for loc in loc_list)
                    for search_tag in search_tags
                )
            )
        ]

    # -------------------------
    # 📅 Date filter
    # -------------------------
    date_col = "published"
    if date_col in filtered_df.columns:
        filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], errors="coerce")
        filtered_df = filtered_df.dropna(subset=[date_col])

        if not filtered_df.empty:
            min_date = filtered_df[date_col].min().date()
            max_date = filtered_df[date_col].max().date()

            start_date, end_date = st.sidebar.date_input(
                "Filter by date",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )

            filtered_df = filtered_df[
                (filtered_df[date_col].dt.date >= start_date)
                & (filtered_df[date_col].dt.date <= end_date)
            ]

    # -------------------------
    # 📈 Display filtered DataFrame
    # -------------------------
    st.subheader("📈 Filtered DataFrame")
    st.dataframe(filtered_df[cols_to_show])

    # -------------------------
    # 🔝 Top Keywords from Filtered Articles
    # -------------------------
    st.subheader("🔝 Top Keywords (Filtered Selection)")

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

    # -------------------------
    # 🧾 Show raw JSON
    # -------------------------
    with st.expander("Show raw JSON data"):
        st.json(data)

except FileNotFoundError:
    st.error(f"❌ File not found at path: `{FILE_PATH}`")
except json.JSONDecodeError:
    st.error("⚠️ The file is not valid JSON.")
except Exception as e:
    st.error(f"Unexpected error: {e}")
