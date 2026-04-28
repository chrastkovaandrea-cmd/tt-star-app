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

# Inicializace dat
if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- VÝPOČTOVÉ JÁDRO ---
def calculate_ratings():
    elos = {}
    glicko = {}
    for d in sorted(st.session_state.data, key=lambda x: x.get('timestamp', '')):
        pA, pB, winA = d['A'], d['B'], d['win']
        for p in [pA, pB]:
            if p not in elos: elos[p] = 1500
            if p not in glicko: glicko[p] = {"r": 1500, "rd": 350}
        
        # ELO
        ea = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        elos[pA] += 32 * (winA - ea)
        elos[pB] -= 32 * (winA - ea)
        
        # GLICKO (zjednodušené pro stabilitu)
        grA, grB = glicko[pA]["r"], glicko[pB]["r"]
        e_glicko = 1 / (1 + 10 ** ((grB - grA) / 400))
        glicko[pA]["r"] += (glicko[pA]["rd"] / 10) * (winA - e_glicko)
        glicko[pB]["r"] += (glicko[pB]["rd"] / 10) * ((1-winA) - (1-e_glicko))
        glicko[pA]["rd"] = max(30, glicko[pA]["rd"] - 5)
        glicko[pB]["rd"] = max(30, glicko[pB]["rd"] - 5)
    return elos, glicko

# --- UI ---
st.set_page_config(page_title="TT STAR v13.0 ULTRA", layout="wide")
st.title("🏓 TT STAR - ULTRA ANALYTIK")

t1, t2, t3, t4 = st.tabs(["📥 Vložit Set", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with t1:
    raw_in = st.text_area("Vložte text z Tipsportu (Live):", height=120)
    lines = [l.strip() for l in raw_in.split('\n') if l.strip()]
    
    c1, c2, c3 = st.columns(3)
    with c1: m_date = st.date_input("Datum:", datetime.date.today())
    with c2: m_set = st.number_input("Číslo setu:", 1, 5, value=1)
    with c3: m_first = st.selectbox("Kdo začal podávat v 1. SETU?", ["A", "B"])
    
    # Automatické střídání podání
    curr_starter = m_first if m_set % 2 != 0 else ("B" if m_first == "A" else "A")
    st.info(f"V {m_set}. setu podává: **Hráč {curr_starter}**")

    if st.button("🚀 ULOŽIT SET"):
        if len(lines) >= 2:
            pA, pB = normalize_name(lines[0]), normalize_name(lines[1])
            full_text = " ".join(lines)
            scores = re.findall(r'(\d+):(\d+)', full_text)
            if scores:
                sa, sb = map(int, scores[-1])
                new_entry = {
                    "A": pA, "B": pB, "score": f"{sa}:{sb}", 
                    "win": 1 if sa > sb else 0, "starter": curr_starter,
                    "set_num": m_set, "timestamp": str(datetime.datetime.now())
                }
                st.session_state.data.append(new_entry)
                save_data(st.session_state.data)
                st.success(f"Uloženo: {pA} vs {pB} ({sa}:{sb})")
                st.rerun()

with t3:
    elos, glicko = calculate_ratings()
    if elos:
        rows = [{"Hráč": p, "Elo": int(elos[p]), "Glicko": int(glicko[p]["r"]), "Jistota": int(glicko[p]["rd"])} for p in elos]
        st.dataframe(pd.DataFrame(rows).sort_values("Glicko", ascending=False), use_container_width=True)

with t4:
    st.subheader("📦 Správa tvých dat")
    
    # ZÁLOHOVÁNÍ
    col_z1, col_z2 = st.columns(2)
    with col_z1:
        st.download_button(
            label="📥 STÁHNOUT ZÁLOHU DO MOBILU",
            data=json.dumps(st.session_state.data, indent=4),
            file_name=f"tt_backup_{datetime.date.today()}.json",
            mime="application/json"
        )
    with col_z2:
        uploaded_file = st.file_uploader("📤 NAHRÁT ZÁLOHU ZE SOUBORU", type="json")
        if uploaded_file is not None:
            st.session_state.data = json.load(uploaded_file)
            save_data(st.session_state.data)
            st.success("Data byla úspěšně nahrána!")
            st.rerun()

    st.divider()
    for i in range(len(st.session_state.data)-1, -1, -1):
        d = st.session_state.data[i]
        with st.expander(f"📝 {d['A']} vs {d['B']} ({d['score']})"):
            if st.button("🗑️ SMAZAT ZÁZNAM", key=f"del_{i}"):
                st.session_state.data.pop(i)
                save_data(st.session_state.data)
                st.rerun()
