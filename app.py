import streamlit as st
import rdflib
from rdflib.namespace import SKOS, RDF
from rapidfuzz import fuzz, process
import pandas as pd
import requests
from pathlib import Path

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="Social Science Literature Toolkit",
    page_icon="📚",
    layout="wide"
)

st.title("Social Science Literature Toolkit")
st.markdown("""
**Open-source academic tool** for literature searching in Sociology, Political Science,  
Development Studies, Anthropology, and Gender Studies.
""")

# -----------------------------
# Load Q1 Journal Database
# -----------------------------
@st.cache_data
def load_journal_db():
    path = Path("q1q2_journals.csv")
    if path.exists():
        return pd.read_csv(path)
    else:
        return pd.DataFrame(columns=["Journal", "ISSN", "Category", "Quartile", "Note"])

journal_db = load_journal_db()

# -----------------------------
# Sidebar Navigation
# -----------------------------
section = st.sidebar.radio(
    "Choose Module",
    [
        "1. Thesaurus Matcher (SPIDER)",
        "2. Journal Match (Q1)",
        "3. Full Search Strategy"
    ]
)

# =========================================================
# MODULE 1: Thesaurus Matcher
# =========================================================
if section == "1. Thesaurus Matcher (SPIDER)":

    st.header("1. Thesaurus Matcher (SPIDER)")

    thesaurus_choice = st.radio(
        "Select Thesaurus:",
        ["TheSoz (GESIS)", "ELSST (CESSDA)"],
        horizontal=True
    )

    DATA_DIR = Path("data")
    DATA_DIR.mkdir(exist_ok=True)

    @st.cache_resource
    def load_thesoz():
        path = DATA_DIR / "thesoz.ttl"
        if not path.exists():
            with st.spinner("Downloading TheSoz..."):
                url = "https://zenodo.org/records/18773539/files/thesoz.ttl?download=1"
                r = requests.get(url, stream=True)
                with open(path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
        g = rdflib.Graph()
        g.parse(path, format="turtle")
        concepts = []
        for concept in g.subjects(RDF.type, SKOS.Concept):
            prefs, alts = [], []
            for lab in g.objects(concept, SKOS.prefLabel):
                if getattr(lab, "language", None) == "en":
                    prefs.append(str(lab))
            for lab in g.objects(concept, SKOS.altLabel):
                if getattr(lab, "language", None) == "en":
                    alts.append(str(lab))
            if prefs:
                concepts.append({
                    "preferred": prefs[0],
                    "alternatives": alts,
                    "all_labels": prefs + alts
                })
        return concepts

    @st.cache_resource
    def load_elsst():
        path = DATA_DIR / "elsst.ttl"
        if not path.exists():
            with st.spinner("Downloading ELSST (may take 1–2 minutes)..."):
                url = "https://zenodo.org/records/17631194/files/ELSST_R6.ttl?download=1"
                r = requests.get(url, stream=True)
                with open(path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
        g = rdflib.Graph()
        g.parse(path, format="turtle")
        concepts = []
        for concept in g.subjects(RDF.type, SKOS.Concept):
            prefs, alts = [], []
            for lab in g.objects(concept, SKOS.prefLabel):
                if getattr(lab, "language", None) == "en":
                    prefs.append(str(lab))
            for lab in g.objects(concept, SKOS.altLabel):
                if getattr(lab, "language", None) == "en":
                    alts.append(str(lab))
            if prefs:
                concepts.append({
                    "preferred": prefs[0],
                    "alternatives": alts,
                    "all_labels": prefs + alts
                })
        return concepts

    with st.spinner(f"Loading {thesaurus_choice}..."):
        try:
            if thesaurus_choice.startswith("TheSoz"):
                concepts = load_thesoz()
                source_name = "TheSoz"
            else:
                concepts = load_elsst()
                source_name = "ELSST"
            st.success(f"Loaded **{len(concepts)}** concepts from **{source_name}**")
        except Exception as e:
            st.error(f"Failed to load thesaurus: {e}")
            st.stop()

    def match_single_keyword(keyword, limit=6, min_score=62):
        if not keyword.strip():
            return []
        label_to_concept = {}
        all_labels = []
        for c in concepts:
            for label in c["all_labels"]:
                all_labels.append(label)
                label_to_concept[label] = c
        matches = process.extract(keyword, all_labels, scorer=fuzz.token_set_ratio, limit=limit)
        results, seen = [], set()
        for match_label, score, _ in matches:
            if score >= min_score:
                concept = label_to_concept[match_label]
                pref = concept["preferred"]
                if pref not in seen:
                    seen.add(pref)
                    results.append({
                        "user_keyword": keyword,
                        "preferred_term": pref,
                        "score": score,
                        "alternatives": ", ".join(concept["alternatives"][:3]) if concept["alternatives"] else "—"
                    })
        return results

    st.subheader("Enter SPIDER Keywords")
    col1, col2 = st.columns(2)
    with col1:
        sample = st.text_area("**S – Sample**", height=100)
        phenomenon = st.text_area("**P – Phenomenon of Interest**", height=100)
        design = st.text_area("**D – Design**", height=80)
    with col2:
        evaluation = st.text_area("**E – Evaluation**", height=100)
        research_type = st.text_area("**R – Research type**", height=80)

    min_score = st.slider("Minimum match score", 55, 90, 65)
    max_per_keyword = st.slider("Max terms per keyword", 3, 8, 5)

    if st.button(f"Generate Boolean String ({source_name})", type="primary"):
        spider_sections = {
            "Sample (S)": [k.strip() for k in sample.split("\n") if k.strip()],
            "Phenomenon of Interest (P)": [k.strip() for k in phenomenon.split("\n") if k.strip()],
            "Design (D)": [k.strip() for k in design.split("\n") if k.strip()],
            "Evaluation (E)": [k.strip() for k in evaluation.split("\n") if k.strip()],
            "Research type (R)": [k.strip() for k in research_type.split("\n") if k.strip()],
        }
        filled = {k: v for k, v in spider_sections.items() if v}
        if not filled:
            st.warning("Enter keywords in at least one SPIDER component.")
            st.stop()

        all_results, boolean_groups, summary = [], [], []
        for sec, kws in filled.items():
            sec_matches, prefs = [], []
            for kw in kws:
                matches = match_single_keyword(kw, max_per_keyword, min_score)
                sec_matches.extend(matches)
                if matches:
                    for m in matches:
                        if m["preferred_term"] not in prefs:
                            prefs.append(m["preferred_term"])
                else:
                    prefs.append(kw)
            if not sec_matches:
                sec_matches = [{"user_keyword": kw, "preferred_term": kw, "score": 0,
                                "alternatives": "Original keyword kept"} for kw in kws]
            all_results.append((sec, sec_matches))
            unique = list(dict.fromkeys(prefs))
            boolean_groups.append("(" + " OR ".join([f'"{t}"' for t in unique]) + ")")
            summary.append({"SPIDER Component": sec, "Terms used": ", ".join(unique)})

        st.subheader("Keyword → Preferred Term Mapping")
        for sec, matches in all_results:
            st.markdown(f"**{sec}**")
            df = pd.DataFrame(matches)
            st.dataframe(df[["user_keyword", "preferred_term", "score", "alternatives"]],
                         use_container_width=True, hide_index=True)

        st.subheader("Optimal Boolean String")
        final_boolean = " AND\n".join(boolean_groups)
        st.code(final_boolean, language="text")
        st.session_state["last_boolean"] = final_boolean   # store for Module 3
        st.success("Boolean string ready. You can now use it in Module 3.")

# =========================================================
# MODULE 2: Journal Match
# =========================================================
elif section == "2. Journal Match (Q1)":

    st.header("2. Journal Match (Q1)")
    st.markdown("Check whether journals from your Scopus results appear in the curated Q1 starter list.")

    if journal_db.empty:
        st.error("`q1q2_journals.csv` not found.")
    else:
        st.info(f"Loaded **{len(journal_db)}** curated Q1 journals")

        user_journals = st.text_area("Paste journal names (one per line)", height=180)

        if st.button("Match Journals", type="primary"):
            input_list = [j.strip() for j in user_journals.split("\n") if j.strip()]
            results = []
            for j in input_list:
                match = journal_db[journal_db["Journal"].str.contains(j, case=False, na=False)]
                if not match.empty:
                    for _, row in match.iterrows():
                        results.append({
                            "Your Input": j,
                            "Matched Journal": row["Journal"],
                            "Category": row["Category"],
                            "Quartile": row["Quartile"],
                            "Note": row["Note"]
                        })
                else:
                    results.append({
                        "Your Input": j,
                        "Matched Journal": "—",
                        "Category": "—",
                        "Quartile": "Not in starter Q1 list",
                        "Note": "Verify on scimagojr.com"
                    })
            res_df = pd.DataFrame(results)
            st.dataframe(res_df, use_container_width=True, hide_index=True)
            st.download_button("Download Results", res_df.to_csv(index=False),
                               "journal_match_results.csv", "text/csv")

        with st.expander("View curated Q1 journal list"):
            st.dataframe(journal_db, use_container_width=True, hide_index=True)

# =========================================================
# MODULE 3: Full Search Strategy (Option B)
# =========================================================
elif section == "3. Full Search Strategy":

    st.header("3. Full Search Strategy")
    st.markdown("""
    This module brings together the **Boolean search string** and the **Q1 journal list**  
    so you can plan a high-quality literature search.
    """)

    st.subheader("A. Your Boolean Search String")
    if "last_boolean" in st.session_state and st.session_state["last_boolean"]:
        st.code(st.session_state["last_boolean"], language="text")
        st.success("Boolean string loaded from Module 1.")
    else:
        st.info("No Boolean string found yet. Please generate one first in **Module 1: Thesaurus Matcher**.")

    st.subheader("B. Recommended Q1 Target Journals")
    if not journal_db.empty:
        st.dataframe(journal_db[["Journal", "Category", "Quartile"]], use_container_width=True, hide_index=True)
    else:
        st.warning("Q1 journal list not loaded.")

    st.subheader("C. How to Combine Them (Recommended Workflow)")
    st.markdown("""
    1. Copy the Boolean string from Section A above.
    2. Go to **Scopus** (or Web of Science).
    3. Paste the Boolean string and run the search.
    4. In Scopus, use the **Source title** filter or export the journal list.
    5. Come back to **Module 2** and paste the journal names to check which ones are Q1.
    6. Prefer articles published in the Q1 journals shown in Section B.
    """)

    st.subheader("D. Quick Tips for Better Results")
    st.markdown("""
    - Start broad with the Boolean string, then narrow by year, document type, and Q1 journals.
    - Always verify the latest quartile on [scimagojr.com](https://www.scimagojr.com) because rankings can change.
    - Use the Boolean string in both Scopus and Google Scholar for complementary coverage.
    """)

st.markdown("---")
st.caption("TheSoz (GESIS) • ELSST (CESSDA) • Q1 list = curated starter set of verified journals")