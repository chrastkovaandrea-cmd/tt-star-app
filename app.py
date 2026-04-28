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
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- VÝPOČTOVÉ JÁDRO ---
def calculate_ratings():
    elos, glicko = {}, {}
    for d in sorted(st.session_state.data, key=lambda x: x.get('timestamp', '')):
        pA, pB, winA = d['A'], d['B'], d['win']
        for p in [pA, pB]:
            if p not in elos: elos[p] = BASE_ELO
            if p not in glicko: glicko[p] = {"r": BASE_ELO, "rd": 350}
        
        # ELO
        ea = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        elos[pA] += 32 * (winA - ea)
        elos[pB] -= 32 * (winA - ea)
        
        # GLICKO
        grA, grB = glicko[pA]["r"], glicko[pB]["r"]
        e_g = 1 / (1 + 10 ** ((grB - grA) / 400))
        glicko[pA]["r"] += (glicko[pA]["rd"] / 10) * (winA - e_g)
        glicko[pB]["r"] += (glicko[pB]["rd"] / 10) * ((1-winA) - (1-e_g))
        glicko[pA]["rd"] = max(30, glicko[pA]["rd"] - 5)
        glicko[pB]["rd"] = max(30, glicko[pB]["rd"] - 5)
    return elos, glicko

def predict_match(pA, pB, starter, elos):
    eloA = elos.get(pA, BASE_ELO)
    eloB = elos.get(pB, BASE_ELO)
    probA = 1 / (1 + 10 ** ((eloB - eloA) / 400))
    # Korekce na podání (4%)
    probA = probA + 0.04 if starter == "A" else probA - 0.04
    probA = min(max(probA, 0.02), 0.98)
    # Odhad Overu podle vyrovnanosti Elo
    prob_over = max(0.25, 0.85 - (abs(eloA - eloB) / 500))
    return probA, prob_over

# --- UI ---
st.set_page_config(page_title="TT STAR v13.1 ULTRA", layout="wide")
st.title("🏓 TT STAR - ULTRA ANALYTIK")

t1, t2, t3, t4 = st.tabs(["📥 Vložit Set", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with t1:
    raw_in = st.text_area("Vložte text z Tipsportu (Live):", height=120)
    lines = [l.strip() for l in raw_in.split('\n') if l.strip()]
    c1, c2, c3 = st.columns(3)
    with c1: m_date = st.date_input("Datum:", datetime.date.today())
    with c2: m_set = st.number_input("Číslo setu:", 1, 5, value=1)
    with c3: m_first = st.selectbox("Kdo začal podávat v 1. SETU?", ["A", "B"])
    
    curr_starter = m_first if m_set % 2 != 0 else ("B" if m_first == "A" else "A")
    st.info(f"V {m_set}. setu podává: **Hráč {curr_starter}**")

    if st.button("🚀 ULOŽIT SET"):
        if len(lines) >= 2:
            pA, pB = normalize_name(lines[0]), normalize_name(lines[1])
            full_text = " ".join(lines)
            scores = re.findall(r'(\d+):(\d+)', full_text)
            if scores:
                sa, sb = map(int, scores[-1])
                new_entry = {"A": pA, "B": pB, "score": f"{sa}:{sb}", "win": 1 if sa > sb else 0, "starter": curr_starter, "set_num": m_set, "timestamp": str(datetime.datetime.now())}
                st.session_state.data.append(new_entry)
                save_data(st.session_state.data)
                st.success(f"Uloženo: {pA} vs {pB}")
                st.rerun()

with t2:
    st.subheader("🔮 Výpočet pravděpodobnosti")
    elos, _ = calculate_ratings()
    cp1, cp2 = st.columns(2)
    with cp1: pA_in = st.text_input("Hráč A").upper()
    with cp2: pB_in = st.text_input("Hráč B").upper()
    cp3, cp4, cp5 = st.columns(3)
    with cp3: s_side = st.radio("Podává v tomto setu:", ["A", "B"])
    with cp4: kA = st.number_input("Kurz na A", 1.0, 10.0, 1.85)
    with cp5: kO = st.number_input("Kurz Over 18.5", 1.0, 10.0, 1.85)
    
    if pA_in and pB_in:
        p_winA, p_over = predict_match(pA_in, pB_in, s_side, elos)
        v1, v2 = st.columns(2)
        with v1:
            st.metric(f"Výhra {pA_in}", f"{round(p_winA*100,1)}%", f"Fair: {round(1/p_winA,2)}")
            if (p_winA * kA) > 1.1: st.success(f"🔥 VALUE: {round(((p_winA*kA)-1)*100,1)}%")
        with v2:
            st.metric("Over 18.5", f"{round(p_over*100,1)}%", f"Fair: {round(1/p_over,2)}")
            if (p_over * kO) > 1.1: st.success(f"🔥 VALUE: {round(((p_over*kO)-1)*100,1)}%")

with t3:
    elos, glicko = calculate_ratings()
    if elos:
        rows = [{"Hráč": p, "Elo": int(elos[p]), "Glicko": int(glicko[p]["r"]), "RD": int(glicko[p]["rd"])} for p in elos]
        st.dataframe(pd.DataFrame(rows).sort_values("Glicko", ascending=False), use_container_width=True)

with t4:
    st.subheader("📦 Zálohování")
    st.download_button("📥 STÁHNOUT ZÁLOHU DO MOBILU", data=json.dumps(st.session_state.data, indent=4), file_name="tt_backup.json")
    uploaded = st.file_uploader("📤 NAHRÁT ZÁLOHU", type="json")
    if uploaded:
        st.session_state.data = json.load(uploaded); save_data(st.session_state.data); st.rerun()
    st.divider()
    for i in range(len(st.session_state.data)-1, -1, -1):
        d = st.session_state.data[i]
        with st.expander(f"📝 {d['A']} vs {d['B']} ({d['score']})"):
            if st.button("🗑️ SMAZAT", key=f"del_{i}"):
                st.session_state.data.pop(i); save_data(st.session_state.data); st.rerun()
