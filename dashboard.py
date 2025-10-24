import streamlit as st
import pandas as pd
import json

# -------------------------
# 🔧 Hard-coded JSON file path
# -------------------------
FILE_PATH = "keywords\\all_articles_keywords.json"  # 👈 change this to your file path

st.title("📊 JSON to DataFrame Viewer (with Filters)")

try:
    # Read JSON (UTF-8 to avoid encoding issues)
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Convert JSON to DataFrame
    df = pd.json_normalize(data)

    st.subheader(f"Data loaded from: `{FILE_PATH}`")
    st.write(f"Rows: {len(df)}, Columns: {len(df.columns)}")

    # -------------------------
    # 🔍 Basic Filtering UI
    # -------------------------
    st.sidebar.header("🔎 Filter Options")

    # Select columns to display
    cols_to_show = st.sidebar.multiselect(
        "Select columns to display",
        options=df.columns.tolist(),
        default=df.columns.tolist()
    )

    # Text filter (for any column)
    text_filter = st.sidebar.text_input("Search text (applies to all string columns)")

    # Apply text filter
    filtered_df = df.copy()
    if text_filter:
        mask = pd.Series(False, index=filtered_df.index)
        for col in filtered_df.select_dtypes(include=["object", "string"]).columns:
            mask |= filtered_df[col].astype(str).str.contains(text_filter, case=False, na=False)
        filtered_df = filtered_df[mask]
    
    # Categorical / string filter (for 'feed' column)
    if 'feed' in filtered_df.columns:
        feed_options = filtered_df['feed'].dropna().unique().tolist()
        selected_feeds = st.sidebar.multiselect(
            "Filter by feed", options=feed_options, default=feed_options
        )
        filtered_df = filtered_df[filtered_df['feed'].isin(selected_feeds)]
    
    # LOCATION SEARCH 
    location_search = st.sidebar.text_input(
    "Filter by locations (type one or more tags, separated by commas)",
    value=""
    )

    # Apply filter if user typed something
    filtered_df = df.copy()
    if location_search.strip():
        # Split input by commas, strip whitespace
        search_tags = [tag.strip() for tag in location_search.split(",") if tag.strip()]
        
        # Keep rows where any tag matches any search term (case-insensitive)
        filtered_df = filtered_df[
            filtered_df['locations'].apply(
                lambda loc_list: any(
                    any(search_tag.lower() in loc.lower() for loc in loc_list)
                    for search_tag in search_tags
                )
            )
        ]

    # DATE FILTER
    date_col = 'published'  # replace with your actual column name

    if date_col in filtered_df.columns:
        # Convert all dates to datetime, pandas handles different formats and time zones
        filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], errors='coerce')

        # Optional: drop rows where parsing failed (NaT)
        filtered_df = filtered_df.dropna(subset=[date_col])

    if date_col in filtered_df.columns and not filtered_df.empty:
        min_date = filtered_df[date_col].min().date()
        max_date = filtered_df[date_col].max().date()
        
        start_date, end_date = st.sidebar.date_input(
            "Filter by date",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

        # Filter the DataFrame by the selected date range
        filtered_df = filtered_df[
            (filtered_df[date_col].dt.date >= start_date) &
            (filtered_df[date_col].dt.date <= end_date)
        ]


    # Display filtered DataFrame
    st.subheader("📈 Filtered DataFrame")
    st.dataframe(filtered_df[cols_to_show])

    # Expand raw JSON
    with st.expander("Show raw JSON data"):
        st.json(data)

except FileNotFoundError:
    st.error(f"❌ File not found at path: `{FILE_PATH}`")
except json.JSONDecodeError:
    st.error("⚠️ The file is not valid JSON.")
except Exception as e:
    st.error(f"Unexpected error: {e}")