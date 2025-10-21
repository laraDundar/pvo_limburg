# --- visualize_keywords.py ---
import json
import matplotlib.pyplot as plt
from wordcloud import WordCloud

# ✅ Load keywords from JSON files
with open("scrapedArticles/top_keywords_sme_ncsc.json", "r", encoding="utf-8") as f:
    ncsc_keywords = json.load(f)

with open("scrapedArticles/top_keywords_sme_nos.json", "r", encoding="utf-8") as f:
    sme_keywords = json.load(f)

# ✅ Generate two word clouds
wc_ncsc = WordCloud(
    width=600, height=400, background_color="white", colormap="Blues"
).generate_from_frequencies(ncsc_keywords)

wc_sme = WordCloud(
    width=600, height=400, background_color="white", colormap="Oranges"
).generate_from_frequencies(sme_keywords)

# ✅ Plot side by side
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
axes[0].imshow(wc_ncsc, interpolation="bilinear")
axes[0].set_title("NCSC Keywords – Cybersecurity Focus", fontsize=14, weight="bold")
axes[0].axis("off")

axes[1].imshow(wc_sme, interpolation="bilinear")
axes[1].set_title("SME Keywords – Economic/Business Focus", fontsize=14, weight="bold")
axes[1].axis("off")

plt.tight_layout()
plt.show()
