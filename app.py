import streamlit as st
import rdflib
from rdflib.namespace import SKOS, RDF
from rapidfuzz import fuzz, process
import pandas as pd
import requests
import os
from pathlib import Path

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="SocioThesaurus Matcher",
    page_icon="🔍",
    layout="wide"
)

st.title("SocioThesaurus Matcher")
st.markdown("""
**Open-source tool** for matching research keywords to preferred terms from  
**TheSoz** (Thesaurus for the Social Sciences – GESIS)
""")

# -----------------------------
# Download TheSoz (only once)
# -----------------------------
DATA_DIR = Path("data")
THESOZ_PATH = DATA_DIR / "thesoz.ttl"

@st.cache_resource
def download_and_load_thesoz():
    DATA_DIR.mkdir(exist_ok=True)

    if not THESOZ_PATH.exists():
        st.info("Downloading TheSoz thesaurus (first time only)... Please wait.")
        url = "https://zenodo.org/records/18773539/files/thesoz.ttl?download=1"
        response = requests.get(url, stream=True)
        with open(THESOZ_PATH, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        st.success("Download completed!")

    # Load the graph
    g = rdflib.Graph()
    g.parse(THESOZ_PATH, format="turtle")

    concepts = []
    LANGUAGE = "en"

    for concept in g.subjects(RDF.type, SKOS.Concept):
        pref_labels = []
        alt_labels = []

        for label in g.objects(concept, SKOS.prefLabel):
            if getattr(label, "language", None) == LANGUAGE:
                pref_labels.append(str(label))

        for label in g.objects(concept, SKOS.altLabel):
            if getattr(label, "language", None) == LANGUAGE:
                alt_labels.append(str(label))

        if pref_labels:
            concepts.append({
                "uri": str(concept),
                "preferred": pref_labels[0],
                "alternatives": alt_labels,
                "all_labels": pref_labels + alt_labels
            })

    return concepts

# Load data
with st.spinner("Loading TheSoz thesaurus..."):
    try:
        concepts = download_and_load_thesoz()
        st.success(f"Loaded **{len(concepts)}** concepts from TheSoz")
    except Exception as e:
        st.error(f"Failed to load TheSoz: {e}")
        st.stop()

# -----------------------------
# Matching Function
# -----------------------------
def match_keywords(user_keywords, limit=10, min_score=65):
    results = []

    label_to_concept = {}
    all_labels = []

    for c in concepts:
        for label in c["all_labels"]:
            all_labels.append(label)
            label_to_concept[label] = c

    for kw in user_keywords:
        kw = kw.strip()
        if not kw:
            continue

        matches = process.extract(
            kw,
            all_labels,
            scorer=fuzz.token_set_ratio,
            limit=limit
        )

        for match_label, score, _ in matches:
            if score >= min_score:
                concept = label_to_concept[match_label]
                results.append({
                    "Your Keyword": kw,
                    "Preferred Term (TheSoz)": concept["preferred"],
                    "Match Score": score,
                    "Alternative Labels": ", ".join(concept["alternatives"][:4]) if concept["alternatives"] else "—",
                    "URI": concept["uri"]
                })

    # Keep highest score for each preferred term
    seen = {}
    for r in results:
        term = r["Preferred Term (TheSoz)"]
        if term not in seen or r["Match Score"] > seen[term]["Match Score"]:
            seen[term] = r

    unique_results = list(seen.values())
    return sorted(unique_results, key=lambda x: x["Match Score"], reverse=True)

def generate_boolean(matches):
    if not matches:
        return "No matches found."
    unique_terms = list(dict.fromkeys([m["Preferred Term (TheSoz)"] for m in matches]))
    return " OR ".join([f'"{term}"' for term in unique_terms])

# -----------------------------
# User Interface
# -----------------------------
st.subheader("Enter your research keywords")
st.caption("Paste keywords from your SPIDER table (one per line)")

default_text = """political participation
social media
youth
first-time voters
political efficacy"""

user_input = st.text_area("Keywords", value=default_text, height=180)

col1, col2 = st.columns(2)
with col1:
    min_score = st.slider("Minimum Match Score", 50, 95, 65)
with col2:
    max_results = st.slider("Max Results", 5, 20, 10)

if st.button("Match with TheSoz", type="primary"):
    keywords = [k.strip() for k in user_input.split("\n") if k.strip()]

    if not keywords:
        st.warning("Please enter at least one keyword.")
    else:
        with st.spinner("Matching against TheSoz..."):
            matches = match_keywords(keywords, limit=max_results, min_score=min_score)

        if not matches:
            st.warning("No good matches found. Try lowering the minimum score.")
        else:
            st.subheader("Suggested Preferred Terms")
            df = pd.DataFrame(matches)
            st.dataframe(
                df[["Your Keyword", "Preferred Term (TheSoz)", "Match Score", "Alternative Labels"]],
                use_container_width=True
            )

            st.subheader("Suggested Boolean String")
            boolean_str = generate_boolean(matches)
            st.code(boolean_str, language="text")

            st.download_button(
                label="Download Results as CSV",
                data=df.to_csv(index=False),
                file_name="thesoz_matches.csv",
                mime="text/csv"
            )

st.markdown("---")
st.caption("Data source: Thesaurus for the Social Sciences (TheSoz) • GESIS – Leibniz Institute for the Social Sciences • Open Access")