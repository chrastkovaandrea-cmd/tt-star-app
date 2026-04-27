import streamlit as st
import unicodedata
import json
import os
import numpy as np
import datetime
from collections import Counter

# --- 1. KONFIGURACE A STAV ---
DATA_FILE = "tt_pro_model_v4.json"
BASE_ELO = 1500
K_FACTOR = 32  # Rychlost změny Elo ratingu

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

# --- 2. LOGIKA MODELU (Elo, Form, Tilt) ---

def calculate_elo_and_stats():
    """Vypočítá Elo ratingy a statistiky pro všechny hráče v DB."""
    elos = {}
    stats = {} # Tilt, Podání, Forma
    
    # Seřadit data podle času (pokud máme uloženo)
    for entry in st.session_state.data:
        pA, pB = entry["A"], entry["B"]
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        
        # Elo update
        R_A = 10**(elos[pA]/400)
        R_B = 10**(elos[pB]/400)
        E_A = R_A / (R_A + R_B)
        S_A = entry["win"]
        elos[pA] = elos[pA] + K_FACTOR * (S_A - E_A)
        elos[pB] = elos[pB] + K_FACTOR * ((1-S_A) - (1-E_A))
        
        # Analýza Tiltu (prohrál set, i když vedl o 4+ body?)
        # Tady bychom analyzovali entry["sequence"]
        
    return elos

def monte_carlo_pro(p_win_point_base, current_score=(0,0), server="A", iterations=5000):
    """
    Simulace se započtením podání.
    Ve stolním tenise se podání střídá po 2 bodech.
    """
    a_wins = 0
    # Bonus za podání (cca 5-10% ve stolním tenisu)
    serve_bonus = 0.07 

    for _ in range(iterations):
        s_a, s_b = current_score
        current_server = server
        total_pts_in_sim = s_a + s_b
        
        while True:
            # Dynamická pravděpodobnost podle toho, kdo podává
            p_point = p_win_point_base
            if current_server == "A": p_point += serve_bonus
            else: p_point -= serve_bonus
            
            if np.random.rand() < p_point: s_a += 1
            else: s_b += 1
            
            total_pts_in_sim += 1
            # Střídání podání po 2 bodech (nebo po 1 v prodloužení)
            if s_a >= 10 and s_b >= 10:
                if total_pts_in_sim % 1 == 0: # Každý bod
                    current_server = "B" if current_server == "A" else "A"
            elif total_pts_in_sim % 2 == 0:
                current_server = "B" if current_server == "A" else "A"
                
            if (s_a >= 11 or s_b >= 11) and abs(s_a - s_b) >= 2: break
            
        if s_a > s_b: a_wins += 1
    return a_wins / iterations

# --- 3. UI ---
st.set_page_config(page_title="TT STAR ULTRA", layout="wide")
st.title("🏓 TT STAR ULTRA MODEL (Elo + Point-by-Point)")

tabs = st.tabs(["📝 Zápis zápasu", "🔮 Predikce & Value", "📊 Elo Žebříček"])

# --- TAB 1: ZÁPIS ---
with tabs[0]:
    col1, col2 = st.columns(2)
    with col1: pA_name = st.text_input("Hráč A").upper()
    with col2: pB_name = st.text_input("Hráč B").upper()
    
    st.write("---")
    if 'seq' not in st.session_state: st.session_state.seq = []
    if 'server_start' not in st.session_state: st.session_state.server_start = "A"

    c1, c2, c3, c4 = st.columns(4)
    if c1.button(f"⚽ Bod {pA_name if pA_name else 'A'}"): st.session_state.seq.append("A")
    if c2.button(f"⚽ Bod {pB_name if pB_name else 'B'}"): st.session_state.seq.append("B")
    st.session_state.server_start = c3.radio("Začal podávat:", ["A", "B"])
    if c4.button("🗑️ Smazat"): st.session_state.seq = []

    # Zobrazení stavu
    sa = st.session_state.seq.count("A")
    sb = st.session_state.seq.count("B")
    st.subheader(f"Skóre: {sa} : {sb}")
    
    if st.button("💾 Uložit set a přepočítat Elo"):
        if pA_name and pB_name and st.session_state.seq:
            st.session_state.data.append({
                "A": pA_name, "B": pB_name,
                "sequence": st.session_state.seq.copy(),
                "win": 1 if sa > sb else 0,
                "timestamp": str(datetime.datetime.now())
            })
            save_data(st.session_state.data)
            st.success("Set uložen do historie!")
            st.session_state.seq = []
            st.rerun()

# --- TAB 2: PREDICKCE & VALUE ---
with tabs[1]:
    elos = calculate_elo_and_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        target_A = st.text_input("Hráč A (Predikce)").upper()
        odds_A = st.number_input("Kurz na A", value=1.85)
    with col2:
        target_B = st.text_input("Hráč B (Predikce)").upper()
        odds_B = st.number_input("Kurz na B", value=1.85)

    if target_A and target_B:
        eloA = elos.get(target_A, BASE_ELO)
        eloB = elos.get(target_B, BASE_ELO)
        
        # 1. Elo Pravděpodobnost
        expected_A = 1 / (1 + 10 ** ((eloB - eloA) / 400))
        
        # 2. Váha formy (posledních 5 zápasů)
        def get_form(player):
            recent = [x for x in st.session_state.data if x["A"] == player or x["B"] == player][-5:]
            if not recent: return 0.5
            wins = sum([1 for x in recent if (x["A"]==player and x["win"]==1) or (x["B"]==player and x["win"]==0)])
            return wins / len(recent)
        
        formA = get_form(target_A)
        formB = get_form(target_B)
        
        # Kombinované P-Win-Point (Elo + Forma)
        # Upravujeme střední hodnotu 0.50 podle Elo rozdílu a formy
        combined_p_point = 0.50 + (expected_A - 0.5) * 0.2 + (formA - formB) * 0.05
        
        # Simulace
        prob_A = monte_carlo_pro(combined_p_point)
        fair_odds = 1 / prob_A
        
        st.divider()
        st.write(f"### Elo: {int(eloA)} vs {int(eloB)} | Forma: {int(formA*100)}% vs {int(formB*100)}%")
        st.write(f"### Fair kurz: {round(fair_odds, 2)}")
        
        edge = (odds_A / fair_odds) - 1
        if edge > 0.03: # Value nad 3%
            st.success(f"🔥 VALUE BET ZJIŠTĚN: Edge {round(edge*100, 1)}%")
        else:
            st.info(f"Bez výrazné hodnoty (Edge {round(edge*100, 1)}%)")

# --- TAB 3: ŽEBŘÍČEK ---
with tabs[2]:
    st.subheader("🏆 Elo Žebříček (Síla hráčů)")
    elos = calculate_elo_and_stats()
    sorted_elos = sorted(elos.items(), key=lambda x: x[1], reverse=True)
    
    for rank, (name, val) in enumerate(sorted_elos):
        st.write(f"{rank+1}. **{name}** - {int(val)} bodů")

st.sidebar.write(f"Model v4.0 | {len(st.session_state.data)} setů")
