# --- visualize_cooccurrence.py ---
import json
import itertools
import networkx as nx
import matplotlib.pyplot as plt
from collections import Counter
from pathlib import Path


def build_cooccurrence_network(articles, min_cooccurrence=1):
    """
    Build a co-occurrence graph from a list of articles.
    Each article must contain a 'keywords' list with dicts like {'word': 'x', 'score': 0.123}
    """
    pair_counter = Counter()

    for art in articles:
        if "keywords" not in art:
            continue
        words = [kw["word"] for kw in art["keywords"] if kw.get("word")]
        # all unique word pairs per article
        for w1, w2 in itertools.combinations(sorted(set(words)), 2):
            pair_counter[(w1, w2)] += 1

    # build graph
    G = nx.Graph()
    for (w1, w2), weight in pair_counter.items():
        if weight >= min_cooccurrence:
            G.add_edge(w1, w2, weight=weight)

    return G


def visualize_network(G, title, color="skyblue"):
    """
    Draws the given networkx graph with matplotlib
    """
    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(G, k=0.4, seed=42)

    node_sizes = [800 + 300 * G.degree(n) for n in G]
    edge_widths = [d["weight"] for (_, _, d) in G.edges(data=True)]

    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=color, alpha=0.8)
    nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color="gray", alpha=0.5)
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight="bold")

    plt.title(title, fontsize=14, weight="bold")
    plt.axis("off")
    plt.tight_layout()
    plt.show()


def main():
    # ✅ Input file paths (adjust if needed)
    ncsc_path = Path("scrapedArticles/ncsc_sme_keywords.json")
    nos_path = Path("scrapedArticles/nos_sme_keywords.json")

    # ✅ Load JSON data
    with open(ncsc_path, "r", encoding="utf-8") as f:
        ncsc_articles = json.load(f)
    with open(nos_path, "r", encoding="utf-8") as f:
        nos_articles = json.load(f)

    # ✅ Build graphs
    G_ncsc = build_cooccurrence_network(ncsc_articles, min_cooccurrence=1)
    G_nos = build_cooccurrence_network(nos_articles, min_cooccurrence=1)

    # ✅ Visualize
    visualize_network(G_ncsc, "NCSC Keyword Co-Occurrence Network", color="skyblue")
    visualize_network(G_nos, "NOS/SME Keyword Co-Occurrence Network", color="orange")


if __name__ == "__main__":
    main()
