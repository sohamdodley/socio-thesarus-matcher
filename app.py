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
    page_title="Social Science Thesaurus Matcher",
    page_icon="🔍",
    layout="wide"
)

st.title("Social Science Thesarus Matcher")
st.markdown("""
**Open-source tool** for matching SPIDER keywords to preferred terms from  
**TheSoz** (GESIS) or **ELSST** (CESSDA)
""")

# -----------------------------
# Thesurus Selection
# -----------------------------
st.header("0. Choose Thesarus")

thesaurus_choice = st.radio(
    "Select which thesaurus you want to use:",
    options=["TheSoz (GESIS)", "ELSST (CESSDA)"],
    horizontal=True
)

# -----------------------------
# Download & Load Functions
# -----------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

@st.cache_resource
def load_thesoz():
    path = DATA_DIR / "thesoz.ttl"
    if not path.exists():
        with st.spinner("Downloading TheSoz thesaurus..."):
            url = "https://zenodo.org/records/18773539/files/thesoz.ttl?download=1"
            response = requests.get(url, stream=True)
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

    g = rdflib.Graph()
    g.parse(path, format="turtle")

    concepts = []
    for concept in g.subjects(RDF.type, SKOS.Concept):
        pref_labels = []
        alt_labels = []
        for label in g.objects(concept, SKOS.prefLabel):
            if getattr(label, "language", None) == "en":
                pref_labels.append(str(label))
        for label in g.objects(concept, SKOS.altLabel):
            if getattr(label, "language", None) == "en":
                alt_labels.append(str(label))
        if pref_labels:
            concepts.append({
                "uri": str(concept),
                "preferred": pref_labels[0],
                "alternatives": alt_labels,
                "all_labels": pref_labels + alt_labels
            })
    return concepts

@st.cache_resource
def load_elsst():
    path = DATA_DIR / "elsst.ttl"
    if not path.exists():
        with st.spinner("Downloading ELSST thesaurus (this may take 1–2 minutes)..."):
            url = "https://zenodo.org/records/17631194/files/ELSST_R6.ttl?download=1"
            response = requests.get(url, stream=True)
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

    g = rdflib.Graph()
    g.parse(path, format="turtle")

    concepts = []
    for concept in g.subjects(RDF.type, SKOS.Concept):
        pref_labels = []
        alt_labels = []
        for label in g.objects(concept, SKOS.prefLabel):
            if getattr(label, "language", None) == "en":
                pref_labels.append(str(label))
        for label in g.objects(concept, SKOS.altLabel):
            if getattr(label, "language", None) == "en":
                alt_labels.append(str(label))
        if pref_labels:
            concepts.append({
                "uri": str(concept),
                "preferred": pref_labels[0],
                "alternatives": alt_labels,
                "all_labels": pref_labels + alt_labels
            })
    return concepts

# Load the selected thesaurus
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

# -----------------------------
# Matching Function
# -----------------------------
def match_single_keyword(keyword, limit=6, min_score=62):
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
        placeholder="e.g.\nyouth\nfirst-time voters\nurban women",
        height=120
    )
    phenomenon = st.text_area(
        "**P – Phenomenon of Interest**",
        placeholder="e.g.\npolitical participation\nsocial media use",
        height=120
    )
    design = st.text_area(
        "**D – Design**",
        placeholder="e.g.\nqualitative\nsurvey\nmixed methods",
        height=100
    )

with col2:
    evaluation = st.text_area(
        "**E – Evaluation**",
        placeholder="e.g.\nvoter turnout\npolitical knowledge",
        height=120
    )
    research_type = st.text_area(
        "**R – Research type**",
        placeholder="e.g.\nqualitative research\nempirical study",
        height=100
    )

min_score = st.slider("Minimum match score", 55, 90, 65)
max_per_keyword = st.slider("Max preferred terms per keyword", 3, 8, 5)

# -----------------------------
# Run Matching
# -----------------------------
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
                preferred_terms.append(kw)

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
    st.caption(f"Using: **{source_name}**")

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
    st.success(f"All filled SPIDER components included using **{source_name}**.")

    st.subheader("Summary of terms used")
    st.dataframe(pd.DataFrame(mapping_summary), use_container_width=True, hide_index=True)

    download_df = pd.concat(
        [pd.DataFrame(m).assign(**{"SPIDER Component": s}) for s, m in all_results],
        ignore_index=True
    )
    st.download_button(
        label="Download Full Mapping as CSV",
        data=download_df.to_csv(index=False),
        file_name=f"{source_name.lower()}_spider_mapping.csv",
        mime="text/csv"
    )

st.markdown("---")
st.caption("Data sources: TheSoz (GESIS) • ELSST (CESSDA) • Both open access")