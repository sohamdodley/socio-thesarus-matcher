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
**Open-source academic tool** for:
1. Matching SPIDER keywords to **TheSoz** or **ELSST**
2. Checking journals against a curated **Q1** list (Sociology, Political Science, Development Studies, Anthropology, Gender Studies)
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
    ["Thesaurus Matcher (SPIDER)", "Journal Match (Q1)"]
)

# =========================================================
# MODULE 1: Thesaurus Matcher (TheSoz / ELSST + SPIDER)
# =========================================================
if section == "Thesaurus Matcher (SPIDER)":

    st.header("Thesaurus Matcher")

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

    st.subheader("1. Enter SPIDER Keywords")
    st.markdown("Fill the relevant boxes. Leave blank if not applicable.")

    col1, col2 = st.columns(2)
    with col1:
        sample = st.text_area("**S – Sample**", height=110,
                              placeholder="youth\nfirst-time voters\nurban women")
        phenomenon = st.text_area("**P – Phenomenon of Interest**", height=110,
                                  placeholder="political participation\nsocial media use")
        design = st.text_area("**D – Design**", height=90,
                              placeholder="qualitative\nsurvey\nmixed methods")
    with col2:
        evaluation = st.text_area("**E – Evaluation**", height=110,
                                  placeholder="voter turnout\npolitical efficacy")
        research_type = st.text_area("**R – Research type**", height=90,
                                     placeholder="qualitative research\nempirical study")

    min_score = st.slider("Minimum match score", 55, 90, 65)
    max_per_keyword = st.slider("Max preferred terms per keyword", 3, 8, 5)

    if st.button(f"Match Keywords with {source_name}", type="primary"):

        spider_sections = {
            "Sample (S)": [k.strip() for k in sample.split("\n") if k.strip()],
            "Phenomenon of Interest (P)": [k.strip() for k in phenomenon.split("\n") if k.strip()],
            "Design (D)": [k.strip() for k in design.split("\n") if k.strip()],
            "Evaluation (E)": [k.strip() for k in evaluation.split("\n") if k.strip()],
            "Research type (R)": [k.strip() for k in research_type.split("\n") if k.strip()],
        }

        filled_sections = {k: v for k, v in spider_sections.items() if v}

        if not filled_sections:
            st.warning("Please enter keywords in at least one SPIDER component.")
            st.stop()

        all_results = []
        boolean_groups = []
        mapping_summary = []

        for section_name, keywords in filled_sections.items():
            section_matches = []
            preferred_terms = []

            for kw in keywords:
                matches = match_single_keyword(kw, limit=max_per_keyword, min_score=min_score)
                section_matches.extend(matches)

                if matches:
                    for m in matches:
                        if m["preferred_term"] not in preferred_terms:
                            preferred_terms.append(m["preferred_term"])
                else:
                    preferred_terms.append(kw)  # fallback

            if section_matches:
                all_results.append((section_name, section_matches))
            else:
                fallback_rows = [{
                    "user_keyword": kw,
                    "preferred_term": kw,
                    "score": 0,
                    "alternatives": f"No good {source_name} match – original keyword kept"
                } for kw in keywords]
                all_results.append((section_name, fallback_rows))

            unique_terms = list(dict.fromkeys(preferred_terms))
            group = " OR ".join([f'"{t}"' for t in unique_terms])
            boolean_groups.append(f"({group})")

            mapping_summary.append({
                "SPIDER Component": section_name,
                "Terms used in Boolean": ", ".join(unique_terms)
            })

        # Display Mapping
        st.header("2. Keyword → Preferred Term Mapping")
        st.caption(f"Thesaurus used: **{source_name}**")

        for section_name, matches in all_results:
            st.subheader(section_name)
            df = pd.DataFrame(matches)
            st.dataframe(
                df[["user_keyword", "preferred_term", "score", "alternatives"]].rename(columns={
                    "user_keyword": "Your Keyword",
                    "preferred_term": f"Preferred Term ({source_name})",
                    "score": "Match Score",
                    "alternatives": "Notes / Alternatives"
                }),
                use_container_width=True,
                hide_index=True
            )

        # Boolean String
        st.header("3. Optimal Boolean String (All SPIDER Components)")
        final_boolean = " AND\n".join(boolean_groups)
        st.code(final_boolean, language="text")
        st.success("All filled SPIDER components have been included.")

        st.subheader("Summary of terms used")
        st.dataframe(pd.DataFrame(mapping_summary), use_container_width=True, hide_index=True)

        download_df = pd.concat(
            [pd.DataFrame(m).assign(**{"SPIDER Component": s}) for s, m in all_results],
            ignore_index=True
        )
        st.download_button(
            "Download Full Mapping as CSV",
            download_df.to_csv(index=False),
            f"{source_name.lower()}_spider_mapping.csv",
            "text/csv"
        )

# =========================================================
# MODULE 2: Journal Match (Q1)
# =========================================================
elif section == "Journal Match (Q1)":

    st.header("Journal Match – Q1 Filter")
    st.markdown("""
    Paste journal names (one per line) from your Scopus results.  
    The tool checks them against a **curated starter list** of established Q1 journals 
    in Sociology, Political Science, Development Studies, Anthropology, and Gender Studies.
    """)

    if journal_db.empty:
        st.error("`q1q2_journals.csv` not found. Please add the file to the repository.")
    else:
        st.info(f"Currently loaded: **{len(journal_db)}** curated Q1 journals (starter list only)")

        user_journals = st.text_area(
            "Paste journal names (one per line)",
            height=200,
            placeholder="American Sociological Review\nWorld Development\nGender & Society"
        )

        if st.button("Match Journals", type="primary"):
            input_list = [j.strip() for j in user_journals.split("\n") if j.strip()]
            if not input_list:
                st.warning("Please paste at least one journal name.")
            else:
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
                            "Note": "Verify manually on scimagojr.com"
                        })

                res_df = pd.DataFrame(results)
                st.subheader("Match Results")
                st.dataframe(res_df, use_container_width=True, hide_index=True)

                st.download_button(
                    "Download Results as CSV",
                    res_df.to_csv(index=False),
                    "journal_match_results.csv",
                    "text/csv"
                )

        with st.expander("View full curated Q1 journal list"):
            st.dataframe(journal_db, use_container_width=True, hide_index=True)
            st.caption("This is a starter list of well-established Q1 journals only. Always verify the latest quartile on scimagojr.com.")

st.markdown("---")
st.caption("TheSoz (GESIS) • ELSST (CESSDA) • Journal list = curated starter set of verified Q1 titles")