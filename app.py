import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import math
import requests
from bs4 import BeautifulSoup

# --- 1. NASTAVENÍ A KONSTANTY ---
DATA_FILE = "tt_star_ultra_v10.json"
BASE_RATING = 1500
BASE_RD = 350 # Startovací nejistota (vysoká = neznáme hráče)
BASE_VOL = 0.06

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
        json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- 2. GLICKO-2 VÝPOČET (To "lepší" než Elo) ---
def calculate_glicko_stats():
    players = {}
    # Seřadíme data podle času, aby se model učil postupně
    sorted_data = sorted(st.session_state.data, key=lambda x: x.get('timestamp', '0'))
    
    for entry in sorted_data:
        pA, pB = entry.get("A"), entry.get("B")
        winA = entry.get("win", 0)
        
        for p in [pA, pB]:
            if p not in players:
                players[p] = {"r": BASE_RATING, "rd": BASE_RD, "matches": 0}
        
        # Matematika Glicko-2 (zjednodušený update)
        rA, rdA = players[pA]["r"], players[pA]["rd"]
        rB, rdB = players[pB]["r"], players[pB]["rd"]
        
        expected_A = 1 / (1 + 10 ** ((rB - rA) / 400))
        
        # Dynamický K-faktor založený na nejistotě (RD)
        # Čím méně hráče známe (vyšší RD), tím větší skok v bodech
        shiftA = (rdA / 10) * (winA - expected_A)
        shiftB = (rdB / 10) * ((1 - winA) - (1 - expected_A))
        
        players[pA]["r"] += shiftA
        players[pB]["r"] += shiftB
        
        # S každým zápasem klesá nejistota (RD)
        players[pA]["rd"] = max(30, rdA - 5)
        players[pB]["rd"] = max(30, rdB - 5)
        players[pA]["matches"] += 1
        players[pB]["matches"] += 1
        
    return players

# --- 3. SCRAPER (Automatické dolování historie) ---
def deep_scrape():
    url = "https://ttstar.cz/en/ttmatch/"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = list(set([a['href'] for a in soup.find_all('a', href=True) if "results/?id=" in a['href']]))
        new_matches = []
        
        p_bar = st.progress(0)
        for i, link in enumerate(links[:20]): # Prvních 20 turnajů pro začátek
            full_url = f"https://ttstar.cz{link}" if link.startswith("/") else link
            tr = requests.get(full_url, timeout=5)
            tsoup = BeautifulSoup(tr.text, 'html.parser')
            for row in tsoup.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 5:
                    pA, pB = normalize_name(cols[2].text), normalize_name(cols[3].text)
                    res = cols[4].text.strip()
                    if ":" in res and pA != "PLAYER":
                        # Kontrola duplicity
                        if not any(m['A'] == pA and m['B'] == pB and m['score'] == res for m in st.session_state.data[-50:]):
                            new_matches.append({"A": pA, "B": pB, "score": res, "win": 1 if int(res.split(':')[0]) > int(res.split(':')[1]) else 0, "timestamp": "2025-01-01T00:00:00", "source": "auto"})
            p_bar.progress((i+1)/len(links[:20]))
        return new_matches
    except: return []

# --- 4. UI STREAMLIT ---
st.set_page_config(page_title="TT STAR ULTRA v10", layout="wide")
st.title("🏓 TT STAR - GLICKO-2 ANALYTIK")

tabs = st.tabs(["📥 Vložit", "🌐 Archiv", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with tabs[0]: # Vkládání setů (tvůj původní parser)
    raw_in = st.text_area("Vložte text z Tipsportu:")
    if st.button("Uložit z Tipsportu"):
        # ... (zde by byl tvůj parse_live_text a uložení)
        st.success("Uloženo!")

with tabs[1]: # Automatický scraper
    if st.button("🚀 SPUSTIT AUTO-TRÉNINK (Archiv)"):
        new_stuff = deep_scrape()
        st.session_state.data.extend(new_stuff)
        save_data(st.session_state.data)
        st.success(f"Přidáno {len(new_stuff)} zápasů!")

with tabs[4]: # Historie a ZÁLOHA
    st.subheader("💾 Záloha tvé práce")
    json_string = json.dumps(st.session_state.data)
    st.download_button(
        label="📥 STÁHNOUT DATABÁZI (Záloha do mobilu)",
        data=json_string,
        file_name=f"tt_backup_{datetime.date.today()}.json",
        mime="application/json"
    )
    # ... (zde pokračuje tvá správa historie pro mazání a úpravy)
