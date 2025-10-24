import streamlit as st
import pandas as pd
import json

# -------------------------
# 🔧 Hard-coded JSON file path
# -------------------------
FILE_PATH = "keywords\\all_articles_keywords.json"  
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

# -----------------------------------------
    # 🗺️ Interactive Folium Map (Provinces + Countries)
    # -----------------------------------------
    from geopy.geocoders import Nominatim
    from streamlit_folium import st_folium
    import folium
    import time

    st.subheader("🗺️ Interactive Article Map")

    @st.cache_data
    def geocode_locations_with_articles(rows):
        """Geocode unique locations and attach related article titles."""
        geolocator = Nominatim(user_agent="pvo_dashboard")
        geo_records = []
        loc_to_titles = {}

        for _, row in rows.iterrows():
            locs = row.get("locations", [])
            if isinstance(locs, list):
                for loc in locs:
                    loc_to_titles.setdefault(loc, []).append(row.get("title", "Untitled Article"))

        for loc, titles in loc_to_titles.items():
            try:
                # Add "Netherlands" for better accuracy
                location = geolocator.geocode(loc + ", Netherlands", geometry="geojson")
                if location:
                    geo_records.append({
                        "location": loc,
                        "lat": location.latitude,
                        "lon": location.longitude,
                        "titles": titles,
                        "geojson": location.raw.get("geojson")
                    })
                time.sleep(1)  # avoid rate limits
            except Exception as e:
                print(f"⚠️ Could not geocode {loc}: {e}")
                continue

        return geo_records

    if "locations" in filtered_df.columns and filtered_df["locations"].notna().any():
        geo_records = geocode_locations_with_articles(filtered_df)

        if geo_records:
            m = folium.Map(location=[52.1, 5.3], zoom_start=7)
            province_keywords = [
                "limburg", "noord-brabant", "gelderland", "utrecht", "zuid-holland",
                "noord-holland", "overijssel", "drenthe", "friesland", "groningen", "flevoland"
            ]

            for record in geo_records:
                loc_lower = record["location"].lower()
                titles_html = "<br>".join([f"• {t}" for t in record["titles"]])
                popup_html = f"<b>{record['location']}</b><br>{titles_html}"

                # 🔹 Highlight entire province if name matches
                if any(prov in loc_lower for prov in province_keywords) and record.get("geojson"):
                    folium.GeoJson(
                        record["geojson"],
                        name=record["location"],
                        tooltip=f"{record['location']} ({len(record['titles'])} article(s))",
                        popup=popup_html,
                        style_function=lambda x: {
                            "fillColor": "#b3d9ff",
                            "color": "#1f78b4",
                            "weight": 2,
                            "fillOpacity": 0.35,
                        },
                    ).add_to(m)

                # 🔹 Highlight entire country if broad (e.g., "Netherlands", "Belgium", "Germany")
                elif record.get("geojson") and loc_lower in ["nederland", "netherlands", "belgie", "belgium", "duitsland", "germany"]:
                    folium.GeoJson(
                        record["geojson"],
                        name=record["location"],
                        tooltip=f"{record['location']} ({len(record['titles'])} article(s))",
                        popup=popup_html,
                        style_function=lambda x: {
                            "fillColor": "#ccffcc",
                            "color": "#33a02c",
                            "weight": 1,
                            "fillOpacity": 0.3,
                        },
                    ).add_to(m)

                # 🔹 Default marker for cities / towns
                else:
                    folium.Marker(
                        [record["lat"], record["lon"]],
                        popup=popup_html,
                        tooltip=f"{record['location']} ({len(record['titles'])} article(s))",
                        icon=folium.Icon(color="blue", icon="info-sign"),
                    ).add_to(m)

            st_folium(m, width=1000, height=600)
            st.write(f"🗺️ Showing {len(geo_records)} unique locations on the map.")
        else:
            st.info("No valid locations could be geocoded.")
    else:
        st.info("No location data found in this dataset.")

    # Expand raw JSON
    with st.expander("Show raw JSON data"):
        st.json(data)

except FileNotFoundError:
    st.error(f"❌ File not found at path: `{FILE_PATH}`")
except json.JSONDecodeError:
    st.error("⚠️ The file is not valid JSON.")
except Exception as e:
    st.error(f"Unexpected error: {e}")