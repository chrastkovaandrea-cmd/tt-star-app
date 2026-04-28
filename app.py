import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import math
import requests
from bs4 import BeautifulSoup

# --- 1. NASTAVENÍ ---
DATA_FILE = "tt_star_ultra_v10.json"
BASE_RATING = 1500
BASE_RD = 350 

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[.\s]+', '', name)
    name = re.sub(r'^[A-Z][a-z]?\.', '', name) 
    return name.strip().upper()

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                d = json.load(f)
                return d if isinstance(d, list) else []
        except: return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- 2. GLICKO-2 VÝPOČET ---
def calculate_glicko_stats():
    players = {}
    sorted_data = sorted(st.session_state.data, key=lambda x: x.get('timestamp', '0'))
    for entry in sorted_data:
        pA, pB = entry.get("A"), entry.get("B")
        winA = entry.get("win", 0)
        if not pA or not pB: continue
        for p in [pA, pB]:
            if p not in players: players[p] = {"r": BASE_RATING, "rd": BASE_RD, "matches": 0}
        rA, rdA = players[pA]["r"], players[pA]["rd"]
        rB, rdB = players[pB]["r"], players[pB]["rd"]
        
        # Glicko-2 lite
        expected_A = 1 / (1 + 10 ** ((rB - rA) / 400))
        shiftA = (rdA / 10) * (winA - expected_A)
        shiftB = (rdB / 10) * ((1 - winA) - (1 - expected_A))
        
        players[pA]["r"] += shiftA
        players[pB]["r"] += shiftB
        players[pA]["rd"] = max(30, rdA - 4)
        players[pB]["rd"] = max(30, rdB - 4)
        players[pA]["matches"] += 1
        players[pB]["matches"] += 1
    return players

# --- 3. PREDIKČNÍ FUNKCE ---
def predict_match(pA_name, pB_name, players_stats):
    if pA_name not in players_stats or pB_name not in players_stats:
        return None
    rA = players_stats[pA_name]['r']
    rB = players_stats[pB_name]['r']
    # Pravděpodobnost výhry A
    prob_A = 1 / (1 + 10 ** ((rB - rA) / 400))
    return prob_A

# --- 4. DEEP SCRAPER (Vylepšený na proklikávání) ---
def deep_scrape_v2():
    base_url = "https://ttstar.cz/en/ttmatch/"
    headers = {"User-Agent": "Mozilla/5.0"}
    new_matches = []
    try:
        r = requests.get(base_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        # Najdeme odkazy na turnaje
        links = [a['href'] for a in soup.find_all('a', href=True) if "results/?id=" in a['href']]
        links = list(set(links))[:15] # Zkusíme prvních 15 turnajů
        
        p_bar = st.progress(0)
        for i, link in enumerate(links):
            full_url = f"https://ttstar.cz{link}" if link.startswith("/") else link
            res = requests.get(full_url, headers=headers, timeout=5)
            tsoup = BeautifulSoup(res.text, 'html.parser')
            for row in tsoup.find_all('tr'):
                cols = [c.text.strip() for c in row.find_all('td')]
                if len(cols) >= 5:
                    pA, pB, score = normalize_name(cols[2]), normalize_name(cols[3]), cols[4]
                    if ":" in score and pA != "PLAYER":
                        if not any(m['A'] == pA and m['B'] == pB and m['score'] == score for m in st.session_state.data[-200:]):
                            try:
                                s1, s2 = map(int, score.split(':'))
                                new_matches.append({"A": pA, "B": pB, "score": score, "win": 1 if s1 > s2 else 0, "timestamp": datetime.datetime.now().isoformat()})
                            except: continue
            p_bar.progress((i+1)/len(links))
        return new_matches
    except: return []

# --- 5. UI ---
st.set_page_config(page_title="TT STAR v10.8", layout="wide")
st.title("🏓 TT STAR ANALYTIK")

tabs = st.tabs(["📥 Vložit", "🌐 Archiv", "🔮 Predikce", "🏆 Žebříček", "⚙️ Záloha"])

p_stats = calculate_glicko_stats()

with tabs[1]: # Archiv
    if st.button("🚀 DEEP SCAN ARCHIVU"):
        with st.spinner("Prohledávám turnaje..."):
            new_data = deep_scrape_v2()
            st.session_state.data.extend(new_data)
            save_data(st.session_state.data)
            st.success(f"Staženo {len(new_data)} nových zápasů!")
            st.rerun()

with tabs[2]: # Predikce
    st.subheader("Předpověď zápasu & Value Bet")
    all_p = sorted(list(p_stats.keys()))
    c1, c2 = st.columns(2)
    with c1: pA = st.selectbox("Hráč A (Favorit):", all_p)
    with c2: pB = st.selectbox("Hráč B (Outsider):", all_p)
    
    odds_a = st.number_input("Kurz na A (Tipsport):", value=1.85)
    
    if pA and pB and pA != pB:
        prob = predict_match(pA, pB, p_stats)
        if prob:
            st.metric("Pravděpodobnost výhry A", f"{int(prob*100)}%")
            fair_odds = 1 / prob
            st.write(f"Férový kurz: **{fair_odds:.2f}**")
            
            value = (prob * odds_a) - 1
            if value > 0:
                st.success(f"✅ VALUE BET: +{value*100:.1f}% (Kurz je výhodný!)")
            else:
                st.error(f"❌ BEZ VALUE: {value*100:.1f}% (Kurz je příliš nízký)")

with tabs[3]: # Žebříček
    sorted_p = sorted(p_stats.items(), key=lambda x: x[1]['r'], reverse=True)
    for i, (name, s) in enumerate(sorted_p[:30]):
        st.write(f"{i+1}. **{name}** (Rating: {int(s['r'])}, Zápasy: {s['matches']})")

with tabs[4]: # Záloha
    st.download_button("📥 STÁHNOUT JSON ZÁLOHU", json.dumps(st.session_state.data), "tt_zaloha.json")
