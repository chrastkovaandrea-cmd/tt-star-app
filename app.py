import streamlit as st
import json
import os
import re
import datetime
import math
import unicodedata
import pandas as pd
import io

# =========================================================
# KONFIGURACE
# =========================================================

DATA_FILE = "tt_star_ultra_v17.json"

st.set_page_config(
    page_title="TT STAR ANALYTIK PRO",
    page_icon="🏓",
    layout="wide"
)

# =========================================================
# FUNKCE
# =========================================================

def normalize_name(name):
    if not name or pd.isna(name):
        return ""

    name = str(name).strip().upper()
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)

    return re.sub(r'[^A-Z\s]', '', name).strip()


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    st.cache_data.clear()


# =========================================================
# SESSION STATE
# =========================================================

if "data" not in st.session_state:

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                st.session_state.data = json.load(f)

        except:
            st.session_state.data = []

    else:
        st.session_state.data = []


if "txt_area" not in st.session_state:
    st.session_state.txt_area = ""

if "success_msg" not in st.session_state:
    st.session_state.success_msg = ""


# =========================================================
# GLICKO-2 RATING
# =========================================================

@st.cache_data(show_spinner="Přepočítávám žebříček...")
def get_ratings(data_list):

    ratings = {}

    BASE_R = 1500
    BASE_RD = 350
    BASE_VOL = 0.06

    if not data_list:
        return {}

    sorted_data = sorted(
        data_list,
        key=lambda x: str(x.get('timestamp', ''))
    )

    q = math.log(10) / 400

    for d in sorted_data:

        pA = d.get('A')
        pB = d.get('B')
        score = d.get('score')

        if not pA or not pB or ":" not in str(score):
            continue

        pA = normalize_name(pA)
        pB = normalize_name(pB)

        for p in [pA, pB]:

            if p not in ratings:
                ratings[p] = {
                    "r":
