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

# --- 2. PARSER (Tvůj původní systém) ---
def parse_live_text(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    set_num = 1
    s_match = re.search(r'(\d+)\.\s*SET', text, re.IGNORECASE)
    if s_match: set_num = int(s_match.group(1))
    forbidden = ["milestone-logo", "kurzy", "průběh", "statistiky", "tikety", "začátek zápasu"]
    clean = [l for l in lines if not any(f in l.lower() for f in forbidden) and not l.lower().startswith("konec")]
    if len(clean) < 2: return None
    pA, pB = normalize_name(clean[0]), normalize_name(clean[1])
    full = re.sub(r'\s*:\s*', ':', " ".join(clean))
    scores = re.findall(r'(\d+):(\d+)', full)
    pts = [(int(a), int(b)) for a, b in scores] if scores else []
    if pts and (pts[0][0] + pts[0][1]) > (pts[-1][0] + pts[-1][1]): pts.reverse()
    starter = "A"
    serve_info = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text, re.IGNORECASE)
    if serve_info:
        found = normalize_name(serve_info.group(1))
        starter = "B" if (found in pB or pB in found) else "A"
    return {"A": pA, "B": pB, "score": f"{pts[-1][0]}:{pts[-1][1]}" if pts else "0:0", "win": 1 if pts and pts[-1][0] > pts[-1][1] else 0, "starter": starter, "set_num": set_num}

# --- 3. GLICKO-2 VÝPOČET ---
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
        expected_A = 1 / (1 + 10 ** ((rB - rA) / 400))
        shiftA = (rdA / 10) * (winA - expected_A)
        shiftB = (rdB / 10) * ((1 - winA) - (1 - expected_A))
        players[pA]["r"] += shiftA
        players[pB]["r"] += shiftB
        players[pA]["rd"] = max(30, rdA - 5)
        players[pB]["rd"] = max(30, rdB - 5)
        players[pA]["matches"] += 1
        players[pB]["matches"] += 1
    return players

# --- 4. SCRAPER (Archiv) ---
def deep_scrape():
    url = "https://ttstar.cz/en/ttmatch/"
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = list(set([a['href'] for a in soup.find_all('a', href=True) if "results/?id=" in a['href']]))
        new_matches = []
        p_bar = st.progress(0)
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
                            if not any(m['A'] == pA and m['B'] == pB and m['score'] == res for m in st.session_state.data[-100:]):
                                new_matches.append({"A": pA, "B": pB, "score": res, "win": 1 if int(res.split(':')[0]) > int(res.split(':')[1]) else 0, "timestamp": datetime.datetime.now().isoformat(), "source": "auto"})
            except: continue
            p_bar.progress((i+1)/limit)
        return new_matches
    except: return []

# --- 5. UI STREAMLIT ---
st.set_page_config(page_title="TT STAR ULTRA v10.6", layout="wide")
st.title("🏓 TT STAR - GLICKO-2 ANALYTIK")

tabs = st.tabs(["📥 Vložit Set", "🌐 Archiv", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with tabs[0]: 
    raw_in = st.text_area("Vložte text z Tipsportu:", height=150)
    c_d1, c_d2, c_d3 = st.columns(3)
    res = parse_live_text(raw_in) if raw_in else None
    with c_d1: m_date = st.date_input("Datum zápasu:", datetime.date.today())
    with c_d2: m_set = st.number_input("Číslo setu:", 1, 5, value=res['set_num'] if res else 1)
    with c_d3: m_start = st.selectbox("Kdo začal podávat?", ["A", "B"], index=0 if (res and res['starter']=="A") else 1)
    
    if st.button("🚀 Uložit set"):
        if res:
            dt = datetime.datetime.combine(m_date, datetime.datetime.now().time())
            st.session_state.data.append({
                "id": str(dt.timestamp()), 
                "A": res["A"], "B": res["B"], 
                "score": res["score"], "win": res["win"], 
                "starter": m_start, "set_num": m_set, 
                "timestamp": dt.isoformat()
            })
            save_data(st.session_state.data)
            st.success("Uloženo!")
            st.rerun()

with tabs[1]: 
    if st.button("🚀 SPUSTIT AUTO-TRÉNINK (Archiv 2022-2026)"):
        new_stuff = deep_scrape()
        st.session_state.data.extend(new_stuff)
        save_data(st.session_state.data)
        st.success(f"Přidáno {len(new_stuff)} zápasů!")

with tabs[3]:
    p_stats = calculate_glicko_stats()
    sorted_p = sorted(p_stats.items(), key=lambda x: x[1]['r'], reverse=True)
    for i, (name, s) in enumerate(sorted_p[:30]):
        st.write(f"{i+1}. **{name}** — Rating: `{int(s['r'])}` | Zápasů: `{s['matches']}` | Nejistota: `{int(s['rd'])}`")

with tabs[4]: 
    st.subheader("💾 Nahrát zálohu (Obnova dat)")
    uploaded_file = st.file_uploader("Vyber soubor JSON z mobilu:", type="json")
    if uploaded_file is not None:
        st.session_state.data = json.load(uploaded_file)
        save_data(st.session_state.data)
        st.success("Data obnovena!")
        st.rerun()
    st.divider()
    st.subheader("📥 Stáhnout aktuální data")
    st.download_button("STÁHNOUT ZÁLOHU DO MOBILU", json.dumps(st.session_state.data, indent=4), f"tt_backup_{datetime.date.today()}.json", "application/json")
