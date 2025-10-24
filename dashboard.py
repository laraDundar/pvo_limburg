import streamlit as st
import pandas as pd
import json

# -------------------------
# 🔧 Hard-coded JSON file path
# -------------------------
FILE_PATH = "keywords\\all_articles_keywords.json"  # 👈 change this to your file path

st.title("📊 JSON to DataFrame Viewer")

try:
    # Read JSON from the hard-coded path
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Convert JSON to DataFrame
    df = pd.json_normalize(data)

    # Display results
    st.subheader(f"Data from: `{FILE_PATH}`")
    st.dataframe(df)

    # Optional: Show raw JSON
    with st.expander("Show raw JSON data"):
        st.json(data)

except FileNotFoundError:
    st.error(f"❌ File not found at path: `{FILE_PATH}`")
except json.JSONDecodeError:
    st.error("⚠️ The file is not valid JSON.")
except Exception as e:
    st.error(f"Unexpected error: {e}")
