import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import math
import pandas as pd

# --- KONFIGURACE ---
DATA_FILE = "tt_star_ultra_v10.json"
BASE_ELO = 1500

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'^[.\s]+', '', name).strip().upper()

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- VÝPOČTOVÉ JÁDRO (ELO + BODY + GLICKO) ---
def calculate_ratings():
    elos, glicko = {}, {}
    for d in sorted(st.session_state.data, key=lambda x: x.get('timestamp', '')):
        pA, pB, winA, score = d['A'], d['B'], d['win'], d.get('score', "11:7")
        for p in [pA, pB]:
            if p not in elos: elos[p] = BASE_ELO
            if p not in glicko: glicko[p] = {"r": BASE_ELO, "rd": 350}
        
        # MOV (Margin of Victory) - Body ovlivňují sílu posunu
        try:
            pts = list(map(int, score.split(':')))
            diff = abs(pts[0] - pts[1])
        except: diff = 4
        
        mult = math.log(diff + 1) * (2.2 / (1 * 0.001 + 2.2))
        ea = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        elos[pA] += 32 * (winA - ea) * mult
        elos[pB] -= 32 * (winA - ea) * mult
        
        # Glicko
        grA, grB = glicko[pA]["r"], glicko[pB]["r"]
        e_g = 1 / (1 + 10 ** ((grB - grA) / 400))
        glicko[pA]["r"] += (glicko[pA]["rd"] / 10) * (winA - e_g)
        glicko[pB]["r"] += (glicko[pB]["rd"] / 10) * ((1-winA) - (1-e_g))
        glicko[pA]["rd"] = max(30, glicko[pA]["rd"] - 5)
        glicko[pB]["rd"] = max(30, glicko[pB]["rd"] - 5)
    return elos, glicko

def get_exact_score(probA):
    # Simulace nejpravděpodobnějších konců setu
    if probA > 0.5:
        return [("11:7", "Vysoká"), ("11:9", "Střední"), ("11:5", "Nízká")]
    else:
        return [("7:11", "Vysoká"), ("9:11", "Střední"), ("5:11", "Nízká")]

# --- UI ---
st.set_page_config(page_title="TT STAR v13.2 ULTRA", layout="wide")
st.title("🏓 TT STAR - ANALYTIK (BODY & SETY)")

t1, t2, t3, t4 = st.tabs(["📥 Vložit Set", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with t1:
    raw_in = st.text_area("Vložte text z Tipsportu (Live):", height=100)
    c1, c2, c3 = st.columns(3)
    with c1: m_date = st.date_input("Datum:", datetime.date.today())
    with c2: m_set = st.number_input("Set č.:", 1, 5, value=1)
    with c3: m_first = st.selectbox("Podával v 1. SETU:", ["A", "B"])
    
    curr_starter = m_first if m_set % 2 != 0 else ("B" if m_first == "A" else "A")
    st.warning(f"V {m_set}. setu podává: **Hráč {curr_starter}**")

    if st.button("🚀 ULOŽIT SET"):
        lines = [l.strip() for l in raw_in.split('\n') if l.strip()]
        if len(lines) >= 2:
            pA, pB = normalize_name(lines[0]), normalize_name(lines[1])
            scores = re.findall(r'(\d+):(\d+)', " ".join(lines))
            if scores:
                sa, sb = map(int, scores[-1])
                st.session_state.data.append({
                    "A": pA, "B": pB, "score": f"{sa}:{sb}", "win": 1 if sa > sb else 0,
                    "starter": curr_starter, "set_num": m_set, "timestamp": str(datetime.datetime.now())
                })
                save_data(st.session_state.data); st.success("Uloženo!"); st.rerun()

with t2:
    elos, _ = calculate_ratings()
    cp1, cp2 = st.columns(2)
    with cp1: pA_in = st.text_input("Hráč A").upper()
    with cp2: pB_in = st.text_input("Hráč B").upper()
    cp3, cp4, cp5 = st.columns(3)
    with cp3: s_side = st.radio("Podává v setu:", ["A", "B"])
    with cp4: kA = st.number_input("Kurz na A", 1.0, 10.0, 1.85)
    with cp5: kO = st.number_input("Kurz Over 18.5", 1.0, 10.0, 1.85)
    
    if pA_in and pB_in:
        eloA, eloB = elos.get(pA_in, 1500), elos.get(pB_in, 1500)
        p_winA = 1 / (1 + 10 ** ((eloB - eloA) / 400))
        p_winA = p_winA + 0.05 if s_side == "A" else p_winA - 0.05
        p_over = max(0.25, 0.85 - (abs(eloA - eloB) / 500))
        
        v1, v2 = st.columns(2)
        with v1:
            st.metric(f"Výhra {pA_in}", f"{round(p_winA*100,1)}%")
            st.write("**Pravděpodobné skóre:**")
            for sc, conf in get_exact_score(p_winA):
                st.write(f"- {sc} ({conf} šance)")
        with v2:
            st.metric("Over 18.5", f"{round(p_over*100,1)}%")

with t4:
    st.subheader("📦 Záloha dat")
    st.download_button("📥 STÁHNOUT ZÁLOHU DO MOBILU", data=json.dumps(st.session_state.data), file_name="tt_backup.json")
    uploaded = st.file_uploader("📤 NAHRÁT ZÁLOHU", type="json")
    if uploaded:
        st.session_state.data = json.load(uploaded); save_data(st.session_state.data); st.rerun()
