import streamlit as st

st.set_page_config(page_title="PVO_LIMBURG", layout="wide")
st.title("PVO_LIMBURG_DASHBOARD")

import json
import pandas as pd

# Loading data from keywords folder:
with open("keywords\\all_articles_keywords.json", "r", encoding="utf-8") as f:
    article_data = json.load(f)

with open("keywords\\all_articles_top_keywords.json", "r", encoding="utf-8") as f:
    top_keywords = json.load(f)

st.subheader("Raw Data Preview")
st.write("📄 Example article data:")
st.json(article_data[0])  # show one example
st.write("📊 Top keywords:")
st.json(top_keywords)