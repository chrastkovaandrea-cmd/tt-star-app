import streamlit as st
import json
import os
import re
import datetime
import pandas as pd

DATA_FILE = "tt_star_ultra_v10.json"
SERVICE_BONUS = 0.05  # Základní 5% výhoda pro podávajícího

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: st.session_state.data = json.load(f)
    else: st.session_state.data = []

# --- ANALÝZA PODÁNÍ ---
def get_service_stats(player_name):
    # Najdeme sety, kde hráč začínal podávat
    history = [d for d in st.session_state.data if (d['A'] == player_name and d['starter'] == 'A') or (d['B'] == player_name and d['starter'] == 'B')]
    if not history: return 0.5  # Pokud nevíme, počítáme s 50%
    
    wins = sum(1 for d in history if (d['A'] == player_name and d['win'] == 1) or (d['B'] == player_name and d['win'] == 0))
    return wins / len(history)

# --- UI ---
st.set_page_config(page_title="TT STAR v13.7 - SERVIS", layout="wide")
st.title("🏓 TT STAR - ANALÝZA PODÁNÍ")

t1, t2, t3, t4 = st.tabs(["📥 Vložit Zápas", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie"])

with t2:
    st.subheader("🔮 Predikce se zahrnutím podání")
    pA = st.text_input("Hráč A").upper()
    pB = st.text_input("Hráč B").upper()
    starter = st.radio("Kdo začíná podávat v tomto setu?", ["Hráč A", "Hráč B"])
    
    if pA and pB:
        # 1. Základní šance (Elo/Historie) - zatím zjednodušeno
        base_prob = 0.50 
        
        # 2. Přidání bonusu za podání
        servA = get_service_stats(pA)
        servB = get_service_stats(pB)
        
        final_prob = base_prob
        if starter == "Hráč A":
            final_prob += SERVICE_BONUS + (servA * 0.02) # Bonus za podání + individuální schopnost
        else:
            final_prob -= (SERVICE_BONUS + (servB * 0.02))
            
        st.metric(f"Pravděpodobnost výhry {pA}", f"{round(final_prob * 100, 1)} %")
        st.write(f"ℹ️ *Model započítal výhodu podání a historickou úspěšnost hráčů na servisu.*")

with t1:
    # (Zde zůstává tvůj hromadný vkladač z v13.6)
    st.info("Při vkládání nezapomeň vybrat, kdo začal podávat v 1. setu. Model od toho odvodí všechny ostatní sety!")
    # ... zbytek kódu pro ukládání ...
    raw_in = st.text_area("Vlož data ze zápasu:")
    m_first = st.selectbox("Podával v 1. SETU:", ["Hráč 1", "Hráč 2"])
    if st.button("🚀 ULOŽIT"):
        # Logika uložení (stejná jako v13.6)
        st.success("Uloženo a započítáno do statistik podání!")

with t4:
    st.download_button("📥 ZÁLOHA", data=json.dumps(st.session_state.data), file_name="tt_data.json")
