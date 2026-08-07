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
    page_title="SocioThesaurus Matcher",
    page_icon="🔍",
    layout="wide"
)

st.title("SocioThesaurus Matcher")
st.markdown("""
**Open-source tool** for matching SPIDER keywords to preferred terms from  
**TheSoz** (Thesaurus for the Social Sciences – GESIS)
""")

# -----------------------------
# Download & Load TheSoz
# -----------------------------
DATA_DIR = Path("data")
THESOZ_PATH = DATA_DIR / "thesoz.ttl"

@st.cache_resource
def download_and_load_thesoz():
    DATA_DIR.mkdir(exist_ok=True)

    if not THESOZ_PATH.exists():
        with st.spinner("Downloading TheSoz thesaurus (first time only)..."):
            url = "https://zenodo.org/records/18773539/files/thesoz.ttl?download=1"
            response = requests.get(url, stream=True)
            with open(THESOZ_PATH, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

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
def match_single_keyword(keyword, limit=6, min_score=62):
    """Return best matching preferred terms for one keyword"""
    if not keyword.strip():
        return []

    label_to_concept = {}
    all_labels = []

    for c in concepts:
        for label in c["all_labels"]:
            all_labels.append(label)
            label_to_concept[label] = c

    matches = process.extract(
        keyword,
        all_labels,
        scorer=fuzz.token_set_ratio,
        limit=limit
    )

    results = []
    seen = set()

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

# -----------------------------
# SPIDER Input Section
# -----------------------------
st.header("1. Enter SPIDER Keywords")

st.markdown("Fill in the relevant SPIDER elements. Leave blank if not applicable.")

col1, col2 = st.columns(2)

with col1:
    sample = st.text_area(
        "**S – Sample** (Who / What population?)",
        placeholder="e.g.\nyouth\nfirst-time voters\nurban women\ninformal workers",
        height=120
    )
    phenomenon = st.text_area(
        "**P – Phenomenon of Interest**",
        placeholder="e.g.\npolitical participation\nsocial media use\npolitical efficacy",
        height=120
    )
    design = st.text_area(
        "**D – Design** (Study type)",
        placeholder="e.g.\nqualitative\nethnography\nsurvey\nmixed methods",
        height=100
    )

with col2:
    evaluation = st.text_area(
        "**E – Evaluation** (What is measured / outcome)",
        placeholder="e.g.\nvoter turnout\npolitical knowledge\nengagement",
        height=120
    )
    research_type = st.text_area(
        "**R – Research type**",
        placeholder="e.g.\nqualitative research\nprimary research\nempirical study",
        height=100
    )

min_score = st.slider("Minimum match score", 55, 90, 65)
max_per_keyword = st.slider("Max preferred terms per keyword", 3, 8, 5)

# -----------------------------
# Run Matching
# -----------------------------
if st.button("Match Keywords with TheSoz", type="primary"):

    spider_sections = {
        "Sample (S)": [k.strip() for k in sample.split("\n") if k.strip()],
        "Phenomenon of Interest (P)": [k.strip() for k in phenomenon.split("\n") if k.strip()],
        "Design (D)": [k.strip() for k in design.split("\n") if k.strip()],
        "Evaluation (E)": [k.strip() for k in evaluation.split("\n") if k.strip()],
        "Research type (R)": [k.strip() for k in research_type.split("\n") if k.strip()],
    }

    # Keep only sections the user actually filled
    filled_sections = {k: v for k, v in spider_sections.items() if v}

    if not filled_sections:
        st.warning("Please enter keywords in at least one SPIDER component.")
        st.stop()

    all_results = []          # for display tables
    boolean_groups = []       # for final Boolean string
    mapping_summary = []      # for download

    for section_name, keywords in filled_sections.items():
        section_matches = []
        preferred_terms = []

        for kw in keywords:
            matches = match_single_keyword(kw, limit=max_per_keyword, min_score=min_score)
            section_matches.extend(matches)

            if matches:
                # Take the best preferred terms for this keyword
                for m in matches:
                    if m["preferred_term"] not in preferred_terms:
                        preferred_terms.append(m["preferred_term"])
            else:
                # Fallback: keep original keyword if no good match
                preferred_terms.append(kw)

        # Store for display
        if section_matches:
            all_results.append((section_name, section_matches))
        else:
            # Still show that this section was used (with original keywords)
            fallback_rows = [{
                "user_keyword": kw,
                "preferred_term": kw,
                "score": 0,
                "alternatives": "No good TheSoz match – original keyword kept"
            } for kw in keywords]
            all_results.append((section_name, fallback_rows))

        # Build Boolean group for this SPIDER component
        unique_terms = list(dict.fromkeys(preferred_terms))  # preserve order, remove duplicates
        group = " OR ".join([f'"{t}"' for t in unique_terms])
        boolean_groups.append(f"({group})")

        mapping_summary.append({
            "SPIDER Component": section_name,
            "Terms used in Boolean": ", ".join(unique_terms)
        })

    # -------------------------------------------------
    # 2. Display Mapping
    # -------------------------------------------------
    st.header("2. Keyword → Preferred Term Mapping")

    for section_name, matches in all_results:
        st.subheader(section_name)
        df = pd.DataFrame(matches)
        st.dataframe(
            df[["user_keyword", "preferred_term", "score", "alternatives"]].rename(columns={
                "user_keyword": "Your Keyword",
                "preferred_term": "Preferred Term (TheSoz)",
                "score": "Match Score",
                "alternatives": "Notes / Alternatives"
            }),
            use_container_width=True,
            hide_index=True
        )

    # -------------------------------------------------
    # 3. Final Boolean String (all components)
    # -------------------------------------------------
    st.header("3. Optimal Boolean String (All SPIDER Components)")

    final_boolean = " AND\n".join(boolean_groups)

    st.code(final_boolean, language="text")

    st.success("All filled SPIDER components have been included in the Boolean string.")

    # Summary table
    st.subheader("Summary of terms used")
    st.dataframe(pd.DataFrame(mapping_summary), use_container_width=True, hide_index=True)

    # Download
    download_df = pd.concat(
        [pd.DataFrame(m).assign(**{"SPIDER Component": s}) for s, m in all_results],
        ignore_index=True
    )
    st.download_button(
        label="Download Full Mapping as CSV",
        data=download_df.to_csv(index=False),
        file_name="thesoz_spider_full_mapping.csv",
        mime="text/csv"
    )

st.markdown("---")
st.caption("Data source: Thesaurus for the Social Sciences (TheSoz) • GESIS – Leibniz Institute for the Social Sciences")