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
BASE_RD = 350 
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
            if p not in players:
                players[p] = {"r": BASE_RATING, "rd": BASE_RD, "matches": 0}
        
        rA, rdA = players[pA]["r"], players[pA]["rd"]
        rB, rdB = players[pB]["r"], players[pB]["rd"]
        
        expected_A = 1 / (1 + 10 ** ((rB - rA) / 400))
        
        # Glicko-2 lite shift
        shiftA = (rdA / 10) * (winA - expected_A)
        shiftB = (rdB / 10) * ((1 - winA) - (1 - expected_A))
        
        players[pA]["r"] += shiftA
        players[pB]["r"] += shiftB
        
        players[pA]["rd"] = max(30, rdA - 5)
        players[pB]["rd"] = max(30, rdB - 5)
        players[pA]["matches"] += 1
        players[pB]["matches"] += 1
        
    return players

# --- 3. SCRAPER (Archiv) ---
def deep_scrape():
    url = "https://ttstar.cz/en/ttmatch/"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = list(set([a['href'] for a in soup.find_all('a', href=True) if "results/?id=" in a['href']]))
        new_matches = []
        
        p_bar = st.progress(0)
        # Skenujeme prvních 40 turnajů pro masivní data
        limit = min(len(links), 40)
        for i, link in enumerate(links[:limit]):
            full_url = f"https://ttstar.cz{link}" if link.startswith("/") else link
            try:
                tr = requests.get(full_url, timeout=5)
                tsoup = BeautifulSoup(tr.text, 'html.parser')
                for row in tsoup.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 5:
                        pA, pB = normalize_name(cols[2].text), normalize_name(cols[3].text)
                        res = cols[4].text.strip()
                        if ":" in res and pA != "PLAYER":
                            # Pojistka proti duplicitám
                            if not any(m['A'] == pA and m['B'] == pB and m['score'] == res for m in st.session_state.data[-100:]):
                                new_matches.append({
                                    "A": pA, "B": pB, "score": res, 
                                    "win": 1 if int(res.split(':')[0]) > int(res.split(':')[1]) else 0, 
                                    "timestamp": datetime.datetime.now().isoformat(), 
                                    "source": "auto"
                                })
            except: continue
            p_bar.progress((i+1)/limit)
        return new_matches
    except: return []

# --- 4. UI STREAMLIT ---
st.set_page_config(page_title="TT STAR ULTRA v10.5", layout="wide")
st.title("🏓 TT STAR - GLICKO-2 ANALYTIK")

tabs = st.tabs(["📥 Vložit", "🌐 Archiv", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with tabs[0]: 
    st.subheader("Vložit nové zápasy")
    raw_in = st.text_area("Vložte text z Tipsportu (parser):")
    if st.button("Uložit data"):
        # Tady by byl tvůj kód pro parsování textu
        st.info("Zde vlož kód svého parseru pro uložení.")

with tabs[1]: 
    st.subheader("Automatické doplnění z archivu")
    st.write("Tato funkce prohledá web ttstar.cz a doplní chybějící historii.")
    if st.button("🚀 SPUSTIT AUTO-TRÉNINK (Archiv 2022-2026)"):
        new_stuff = deep_scrape()
        st.session_state.data.extend(new_stuff)
        save_data(st.session_state.data)
        st.success(f"Přidáno {len(new_stuff)} zápasů!")

with tabs[3]:
    st.subheader("Aktuální žebříček (Glicko-2)")
    p_stats = calculate_glicko_stats()
    sorted_p = sorted(p_stats.items(), key=lambda x: x[1]['r'], reverse=True)
    for i, (name, s) in enumerate(sorted_p[:30]):
        st.write(f"{i+1}. **{name}** — Rating: `{int(s['r'])}` | Zápasů: `{s['matches']}` | Nejistota: `{int(s['rd'])}`")

with tabs[4]: 
    st.subheader("💾 Záchranná brzda - Nahrát zálohu")
    st.warning("Pokud ti zmizela data, nahraj zde svůj poslední stažený JSON soubor.")
    
    uploaded_file = st.file_uploader("Vyber soubor se zálohou (JSON)", type="json")
    if uploaded_file is not None:
        st.session_state.data = json.load(uploaded_file)
        save_data(st.session_state.data)
        st.success("Data byla úspěšně obnovena!")
        st.rerun()

    st.divider()
    
    st.subheader("📥 Stažení aktuálních dat")
    st.write("Doporučujeme stahovat zálohu po každé větší úpravě.")
    json_string = json.dumps(st.session_state.data, indent=4)
    st.download_button(
        label="STÁHNOUT ZÁLOHU DO MOBILU",
        data=json_string,
        file_name=f"tt_backup_{datetime.date.today()}.json",
        mime="application/json"
    )

    st.divider()
    if st.button("🗑️ SMAZAT CELOU DATABÁZI"):
        if st.checkbox("Opravdu smazat vše?"):
            st.session_state.data = []
            save_data([])
            st.rerun()
