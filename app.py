import streamlit as st
import rdflib
from rdflib.namespace import SKOS, RDF
from rapidfuzz import fuzz, process
import pandas as pd
import requests
from pathlib import Path
from urllib.parse import quote_plus

st.set_page_config(page_title="Social Science Literature Toolkit", page_icon="📚", layout="wide")
st.title("Social Science Literature Toolkit")
st.markdown("**Open-source tool** for building high-quality search strategies in Sociology, Political Science, Development Studies, Anthropology and Gender Studies.")

# -----------------------------
# Load Journal Rankings
# -----------------------------
@st.cache_data
def load_journal_db():
    path = Path("journal_rankings.csv")
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=["Journal", "ISSN", "Category", "Ranking_System", "Level", "Note"])

journal_db = load_journal_db()

# -----------------------------
# Sidebar
# -----------------------------
section = st.sidebar.radio("Choose Module", [
    "1. Thesarus Matcher",
    "2. Journal Match",
    "3. Full Search Strategy"
])

# =========================================================
# MODULE 1: Thesarus Matcher
# =========================================================
if section == "1. Thesarus Matcher":

    st.header("1. Thesarus Matcher")

    thesaurus_choice = st.radio("Select Thesarus", ["TheSoz (GESIS)", "ELSST (CESSDA)"], horizontal=True)
    mode = st.radio("Select Input Mode", ["Simple Keyword Mode", "SPIDER Mode", "PICO Mode"], horizontal=True)

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
                concepts.append({"preferred": prefs[0], "alternatives": alts, "all_labels": prefs + alts})
        return concepts

    @st.cache_resource
    def load_elsst():
        path = DATA_DIR / "elsst.ttl"
        if not path.exists():
            with st.spinner("Downloading ELSST..."):
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
                concepts.append({"preferred": prefs[0], "alternatives": alts, "all_labels": prefs + alts})
        return concepts

    with st.spinner(f"Loading {thesaurus_choice}..."):
        try:
            concepts = load_thesoz() if "TheSoz" in thesaurus_choice else load_elsst()
            source_name = "TheSoz" if "TheSoz" in thesaurus_choice else "ELSST"
            st.success(f"Loaded **{len(concepts)}** concepts from **{source_name}**")
        except Exception as e:
            st.error(f"Failed to load thesarus: {e}")
            st.stop()

    def match_keyword(keyword, limit=5, min_score=85):
        if not keyword.strip():
            return []
        label_to_concept, all_labels = {}, []
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

    keywords_dict = {}

    if mode == "Simple Keyword Mode":
        st.info("Enter your main concepts, one per line.")
        simple_text = st.text_area("Keywords (one per line)", height=140,
                                   placeholder="political participation\nyouth\nsocial media")
        if simple_text.strip():
            keywords_dict["Keywords"] = [k.strip() for k in simple_text.split("\n") if k.strip()]

    elif mode == "SPIDER Mode":
        with st.expander("What is SPIDER?", expanded=False):
            st.markdown("""
            **SPIDER** helps break a topic into five parts:  
            **S** = Sample (who) · **P** = Phenomenon of Interest · **D** = Design · **E** = Evaluation · **R** = Research type.  
            Fill only the boxes that fit your topic.
            """)
            st.markdown("**Example:** Young people’s political participation on social media  \nS: youth · P: political participation · D: qualitative · E: political efficacy · R: qualitative research")

        c1, c2 = st.columns(2)
        with c1:
            s = st.text_area("**S – Sample**", height=80)
            p = st.text_area("**P – Phenomenon of Interest**", height=80)
            d = st.text_area("**D – Design**", height=70)
        with c2:
            e = st.text_area("**E – Evaluation**", height=80)
            r = st.text_area("**R – Research type**", height=70)
        keywords_dict = {
            "Sample (S)": [k.strip() for k in s.split("\n") if k.strip()],
            "Phenomenon of Interest (P)": [k.strip() for k in p.split("\n") if k.strip()],
            "Design (D)": [k.strip() for k in d.split("\n") if k.strip()],
            "Evaluation (E)": [k.strip() for k in e.split("\n") if k.strip()],
            "Research type (R)": [k.strip() for k in r.split("\n") if k.strip()]
        }

    elif mode == "PICO Mode":
        with st.expander("What is PICO?", expanded=False):
            st.markdown("""
            **PICO** structures a question as:  
            **P** = Population · **I** = Intervention/Exposure · **C** = Comparison (optional) · **O** = Outcome.
            """)
            st.markdown("**Example:** Effect of social media on political knowledge among young voters  \nP: young voters · I: social media use · O: political knowledge")

        c1, c2 = st.columns(2)
        with c1:
            p = st.text_area("**P – Population**", height=80)
            i = st.text_area("**I – Intervention / Exposure**", height=80)
        with c2:
            c = st.text_area("**C – Comparison** (optional)", height=80)
            o = st.text_area("**O – Outcome**", height=80)
        keywords_dict = {
            "Population (P)": [k.strip() for k in p.split("\n") if k.strip()],
            "Intervention (I)": [k.strip() for k in i.split("\n") if k.strip()],
            "Comparison (C)": [k.strip() for k in c.split("\n") if k.strip()],
            "Outcome (O)": [k.strip() for k in o.split("\n") if k.strip()]
        }

    filled = {k: v for k, v in keywords_dict.items() if v}
    min_score = st.slider("Minimum match score", 70, 95, 85)
    max_terms = st.slider("Max preferred terms per keyword", 2, 6, 4)

    if st.button(f"Generate Search Strategy ({source_name})", type="primary"):
        if not filled:
            st.warning("Please enter at least one keyword.")
            st.stop()

        all_results, boolean_groups = [], []
        weak_match = False

        for section, kws in filled.items():
            section_matches, preferred = [], []
            for kw in kws:
                matches = match_keyword(kw, limit=max_terms, min_score=min_score)
                section_matches.extend(matches)
                if matches:
                    for m in matches:
                        if m["preferred_term"] not in preferred:
                            preferred.append(m["preferred_term"])
                else:
                    preferred.append(kw)
                    weak_match = True

            if section_matches:
                all_results.append((section, section_matches))
            else:
                all_results.append((section, [{"user_keyword": kw, "preferred_term": kw, "score": 0,
                                              "alternatives": "No strong match – original kept"} for kw in kws]))

            unique = list(dict.fromkeys(preferred))
            boolean_groups.append("(" + " OR ".join([f'"{t}"' for t in unique]) + ")")

        st.subheader("Keyword → Preferred Term Mapping")
        for sec, matches in all_results:
            st.markdown(f"**{sec}**")
            st.dataframe(pd.DataFrame(matches)[["user_keyword", "preferred_term", "score", "alternatives"]],
                         use_container_width=True, hide_index=True)

        final_boolean = " AND\n".join(boolean_groups)
        st.subheader("Boolean Search String")
        st.code(final_boolean, language="text")
        st.session_state["last_boolean"] = final_boolean

        if weak_match:
            st.subheader("Comprehensive Free-text Fallback")
            st.info("Some terms had no strong controlled-vocabulary match. Use these ready-made searches:")
            all_kws = list(dict.fromkeys([k for v in filled.values() for k in v]))
            gs_query = " AND ".join([f'"{k}"' for k in all_kws])
            st.markdown("**Google Scholar**")
            st.code(gs_query)
            st.markdown(f"[Open in Google Scholar](https://scholar.google.com/scholar?q={quote_plus(gs_query)})")
            st.markdown("**JSTOR**")
            st.code(" AND ".join(all_kws))
            st.markdown(f"[Open in JSTOR](https://www.jstor.org/action/doBasicSearch?Query={quote_plus(' AND '.join(all_kws))})")

# =========================================================
# MODULE 2: Journal Match
# =========================================================
elif section == "2. Journal Match":

    st.header("2. Journal Match")
    st.markdown("Check journals against curated high-quality lists (SCImago Q1, Web of Science Q1, Norwegian Level 2, JUFO Level 2/3).")

    if journal_db.empty:
        st.error("`journal_rankings.csv` not found.")
    else:
        systems = ["All"] + sorted(journal_db["Ranking_System"].unique().tolist())
        selected = st.multiselect("Select ranking systems", systems, default=["All"])

        user_input = st.text_area("Paste journal names (one per line)", height=160)

        if st.button("Match Journals", type="primary"):
            journals = [j.strip() for j in user_input.split("\n") if j.strip()]
            results = []
            df = journal_db if "All" in selected else journal_db[journal_db["Ranking_System"].isin(selected)]

            for j in journals:
                match = df[df["Journal"].str.contains(j, case=False, na=False)]
                if not match.empty:
                    for _, row in match.iterrows():
                        results.append({
                            "Your Input": j,
                            "Matched Journal": row["Journal"],
                            "Category": row["Category"],
                            "Ranking System": row["Ranking_System"],
                            "Level": row["Level"],
                            "Note": row["Note"]
                        })
                else:
                    results.append({
                        "Your Input": j,
                        "Matched Journal": "—",
                        "Category": "—",
                        "Ranking System": "—",
                        "Level": "Not found in selected lists",
                        "Note": "Verify on official sites"
                    })
            res_df = pd.DataFrame(results)
            st.dataframe(res_df, use_container_width=True, hide_index=True)
            st.download_button("Download Results", res_df.to_csv(index=False), "journal_match_results.csv", "text/csv")

        with st.expander("View full curated lists"):
            st.dataframe(journal_db, use_container_width=True, hide_index=True)

# =========================================================
# MODULE 3: Full Search Strategy
# =========================================================
elif section == "3. Full Search Strategy":

    st.header("3. Full Search Strategy")
    st.subheader("A. Your Boolean Search String")
    if "last_boolean" in st.session_state and st.session_state["last_boolean"]:
        st.code(st.session_state["last_boolean"], language="text")
    else:
        st.info("No Boolean string generated yet. Create one in Module 1.")

    st.subheader("B. High-Quality Journal Lists (Starter Sets)")
    if not journal_db.empty:
        st.dataframe(journal_db[["Journal", "Category", "Ranking_System", "Level"]],
                     use_container_width=True, hide_index=True)
    else:
        st.warning("Journal lists not loaded.")

    st.subheader("C. Recommended Workflow")
    st.markdown("""
    1. Copy the Boolean string from Section A.  
    2. Run it in **Scopus** or **Web of Science**.  
    3. Note the journal names from the results.  
    4. Paste them into **Module 2** to check quality rankings.  
    5. Prefer articles published in journals that appear in SCImago Q1, Web of Science Q1, Norwegian Level 2, or JUFO Level 2/3.  
    6. Always verify the latest ranking on the official websites.
    """)

st.markdown("---")
st.caption("TheSoz (GESIS) • ELSST (CESSDA) • Journal lists = curated starter sets only")