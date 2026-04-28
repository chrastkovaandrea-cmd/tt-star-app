import streamlit as st
import json
import os
import re
import datetime
import pandas as pd
import math

DATA_FILE = "tt_star_ultra_v10.json"

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: st.session_state.data = json.load(f)
    else: st.session_state.data = []

# --- ANALYTICKÉ FUNKCE ---
def analyze_player_context(player_name, target_time):
    # Filtrace zápasů daného hráče
    history = [d for d in st.session_state.data if d['A'] == player_name or d['B'] == player_name]
    if not history: return 1.0 # Neutrální
    
    # 1. Analýza denní doby
    target_hour = target_time.hour
    morning_wins = [d for d in history if 6 <= datetime.datetime.fromisoformat(d['timestamp']).hour < 13]
    evening_wins = [d for d in history if datetime.datetime.fromisoformat(d['timestamp']).hour >= 17]
    
    # 2. Únava (kolikátý zápas dnes?)
    today_str = target_time.strftime('%Y-%m-%d')
    today_matches = [d for d in history if d['timestamp'].startswith(today_str)]
    fatigue_penalty = len(today_matches) * 0.02 # 2% dolů za každý odehraný zápas dnes
    
    return 1.0 - fatigue_penalty

# --- UI ---
st.set_page_config(page_title="TT STAR v13.6 ULTRA", layout="wide")
st.title("🏓 TT STAR - ANALÝZA FORMY A ČASU")

t1, t2, t3, t4 = st.tabs(["📥 Vložit Zápas", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie"])

with t1:
    st.subheader("Hromadné vložení s časem")
    c1, c2 = st.columns(2)
    with c1:
        m_date = st.date_input("Datum:", datetime.date.today())
    with c2:
        m_time = st.time_input("Čas začátku:", datetime.time(8, 0))
    
    raw_in = st.text_area("Vlož data ze zápasu (Jména a body):", height=150)
    first_server = st.selectbox("Kdo začal podávat v 1. SETU?", ["Hráč 1", "Hráč 2"])

    if st.button("🚀 ULOŽIT CELÝ ZÁPAS"):
        # Logika pro rozsekání jmen a bodů (z v13.5)
        try:
            lines = [l.strip() for l in raw_in.split('\n') if l.strip()]
            name1 = re.sub(r'[\d\t]+', '', lines[0]).strip().upper()
            name2 = re.sub(r'[\d\t]+', '', lines[len(lines)//2]).strip().upper()
            p1_sets = re.findall(r'\d+', lines[0])[1:]
            p2_sets = re.findall(r'\d+', lines[len(lines)//2])[1:]
            
            ts = f"{m_date}T{m_time.isoformat()}"
            
            for i in range(len(p1_sets)):
                set_num = i + 1
                starter = "A" if (first_server == "Hráč 1" and set_num % 2 != 0) or (first_server == "Hráč 2" and set_num % 2 == 0) else "B"
                st.session_state.data.append({
                    "A": name1, "B": name2, "score": f"{p1_sets[i]}:{p2_sets[i]}",
                    "win": 1 if int(p1_sets[i]) > int(p2_sets[i]) else 0,
                    "starter": starter, "set_num": set_num, "timestamp": ts
                })
            save_data(st.session_state.data)
            st.success("Zápas uložen do historie!")
        except:
            st.error("Chyba! Zkontroluj formát textu.")

with t2:
    st.subheader("🔮 Inteligentní Predikce")
    # Tady model porovná Elo a přidá k tomu vliv času a únavy
    pA = st.text_input("Hráč A").upper()
    pB = st.text_input("Hráč B").upper()
    
    if pA and pB:
        # Tady probíhá ten výpočet únavy
        bonusA = analyze_player_context(pA, datetime.datetime.now())
        bonusB = analyze_player_context(pB, datetime.datetime.now())
        
        st.write(f"📊 **Analýza formy:**")
        st.write(f"- {pA}: Únavový koeficient {round(bonusA, 2)}")
        st.write(f"- {pB}: Únavový koeficient {round(bonusB, 2)}")
        
        if bonusA < bonusB:
            st.info(f"💡 Tip: {pA} je dnes více vytížen, může se projevit únava.")

with t4:
    st.download_button("📥 ZÁLOHA DO MOBILU", data=json.dumps(st.session_state.data), file_name="tt_data.json")
