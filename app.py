import streamlit as st
import unicodedata
import json
import os
import numpy as np
import datetime

# --- 1. NASTAVENÍ ---
DATA_FILE = "tt_star_ultra_v6.json"
BASE_ELO = 1500
K_FACTOR = 32

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return " ".join(name.strip().split()).upper()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

if 'current_match_sets' not in st.session_state:
    st.session_state.current_match_sets = []

# --- 2. LOGIKA ELO ---
def calculate_elo():
    elos = {}
    for match in st.session_state.data:
        pA, pB = match["A"], match["B"]
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        
        expected_A = 1 / (1 + 10**((elos[pB] - elos[pA]) / 400))
        actual_A = 1 if match["winner"] == pA else 0
        
        shift = K_FACTOR * (actual_A - expected_A)
        elos[pA] += shift
        elos[pB] -= shift
    return elos

# --- 3. UI ---
st.set_page_config(page_title="TT STAR ANALYZER", layout="wide")
st.title("🏓 TT STAR PRO MODEL - Best of 5")

tabs = st.tabs(["🎮 Live Zápis", "📊 Model & Value", "🏆 Ranking"])

# --- TAB 1: ZÁPIS (NA 3 VÍTĚZNÉ) ---
with tabs[0]:
    col_names = st.columns(2)
    with col_names[0]: pA = st.text_input("Hráč A").upper()
    with col_names[1]: pB = st.text_input("Hráč B").upper()

    st.divider()
    
    # Skóre zápasu
    sets_A = sum(1 for s in st.session_state.current_match_sets if s['win'] == 'A')
    sets_B = sum(1 for s in st.session_state.current_match_sets if s['win'] == 'B')
    
    st.markdown(f"<h1 style='text-align: center;'>{sets_A} : {sets_B}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center;'>{pA if pA else 'Hráč A'} vs {pB if pB else 'Hráč B'}</p>", unsafe_allow_html=True)

    # Průběh setu
    if 'seq' not in st.session_state: st.session_state.seq = []
    
    sa, sb = st.session_state.seq.count("A"), st.session_state.seq.count("B")
    
    st.progress(min(sa / 11, 1.0) if sa > sb else min(sb / 11, 1.0))
    st.subheader(f"Aktuální set: {sa} : {sb}")

    c1, c2, c3 = st.columns([2, 2, 1])
    # Tlačítka pro body - automaticky se deaktivují, pokud zápas skončil
    match_ended = sets_A >= 3 or sets_B >= 3
    
    if c1.button(f"⚽ Bod {pA if pA else 'A'}", disabled=match_ended): 
        st.session_state.seq.append("A")
        st.rerun()
    if c2.button(f"⚽ Bod {pB if pB else 'B'}", disabled=match_ended): 
        st.session_state.seq.append("B")
        st.rerun()
    if c3.button("🔄 Zpět"): 
        if st.session_state.seq: st.session_state.seq.pop()
        st.rerun()

    # Kontrola konce setu (11 bodů a rozdíl 2)
    set_finished = (sa >= 11 or sb >= 11) and abs(sa - sb) >= 2
    
    if set_finished:
        st.warning(f"Set skončil výsledkem {sa}:{sb}. Nezapomeňte ho uložit.")

    col_save = st.columns(2)
    if col_save[0].button("➕ ULOŽIT SET", use_container_width=True, type="primary"):
        if sa > 0 or sb > 0:
            st.session_state.current_match_sets.append({
                "score": f"{sa}:{sb}",
                "win": "A" if sa > sb else "B",
                "sequence": st.session_state.seq.copy()
            })
            st.session_state.seq = []
            st.rerun()

    if match_ended:
        st.success(f"🏆 Zápas skončil! Vítěz: {pA if sets_A > sets_B else pB}")
        if st.button("💾 ULOŽIT CELÝ ZÁPAS DO HISTORIE", use_container_width=True):
            winner = pA if sets_A > sets_B else pB
            st.session_state.data.append({
                "A": pA, "B": pB,
                "sets": st.session_state.current_match_sets.copy(),
                "final_score": f"{sets_A}:{sets_B}",
                "winner": winner,
                "timestamp": str(datetime.datetime.now())
            })
            save_data(st.session_state.data)
            st.session_state.current_match_sets = []
            st.success("Zápas byl úspěšně uložen a Elo přepočítáno.")
            st.rerun()

# --- TAB 2: MODEL & VALUE ---
with tabs[1]:
    elos = calculate_elo()
    st.subheader("Simulace a hledání hodnoty")
    
    colA, colB = st.columns(2)
    with colA:
        inA = st.text_input("Hráč A", key="valA").upper()
        oddsA = st.number_input("Kurz Tipsport (A)", value=1.85)
    with colB:
        inB = st.text_input("Hráč B", key="valB").upper()
    
    if inA and inB:
        eA, eB = elos.get(inA, 1500), elos.get(inB, 1500)
        # Pravděpodobnost na základě Elo
        win_prob_A = 1 / (1 + 10 ** ((eB - eA) / 400))
        fair_odds = 1 / win_prob_A
        
        st.write(f"**Elo rating:** {int(eA)} vs {int(eB)}")
        st.metric("Fair Kurz (podle historie)", round(fair_odds, 2))
        
        edge = (oddsA / fair_odds) - 1
        if edge > 0.05:
            st.success(f"🔥 VALUE DETEKCÍ: +{round(edge*100, 1)}% na {inA}")
        elif edge < -0.05:
            st.warning(f"Nevýhodný kurz (Ztráta {round(edge*100, 1)}%)")
        else:
            st.info("Kurz odpovídá historické síle.")

# --- TAB 3: ŽEBŘÍČEK ---
with tabs[2]:
    st.subheader("🏆 Elo Ranking Hráčů")
    current_elos = calculate_elo()
    if current_elos:
        sorted_ranking = sorted(current_elos.items(), key=lambda x: x[1], reverse=True)
        for r, (name, val) in enumerate(sorted_ranking):
            st.write(f"{r+1}. **{name}** — {int(val)} bodů")
    else:
        st.info("Zatím žádná data. Uložte první zápas.")

st.sidebar.write(f"Celkem zápasů: {len(st.session_state.data)}")
if st.sidebar.button("Resetovat model"):
    if st.sidebar.checkbox("Opravdu smazat všechna data?"):
        save_data([])
        st.session_state.data = []
        st.rerun()
