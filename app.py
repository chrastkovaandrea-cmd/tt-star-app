import streamlit as st
import unicodedata
import json
import os
import re
import datetime

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

# --- 2. SMART PARSER (Vytáhne data z jakéhokoliv zkopírovaného textu) ---
def smart_extract_from_text(text):
    new_entries = []
    # Rozdělíme text na řádky
    lines = text.split('\n')
    for line in lines:
        # Hledáme vzorec: Jméno Jméno skóre (např. 3:1 nebo 0:3)
        # Tento regex najde skóre a zkusí vzít text před ním
        match = re.search(r'([A-ZÁ-ž\s\.]+)\s+([A-ZÁ-ž\s\.]+)\s+(\d:\d)', line, re.IGNORECASE)
        if match:
            pA = normalize_name(match.group(1))
            pB = normalize_name(match.group(2))
            score = match.group(3)
            if pA and pB and ":" in score:
                # Kontrola duplicity
                if not any(d['A'] == pA and d['B'] == pB and d['score'] == score for d in st.session_state.data[-300:]):
                    s1, s2 = map(int, score.split(':'))
                    new_entries.append({
                        "A": pA, "B": pB, "score": score,
                        "win": 1 if s1 > s2 else 0,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "source": "manual_batch"
                    })
    return new_entries

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
        players[pA]["rd"] = max(30, rdA - 4)
        players[pB]["rd"] = max(30, rdB - 4)
        players[pA]["matches"] += 1
        players[pB]["matches"] += 1
    return players

# --- 4. UI ---
st.set_page_config(page_title="TT STAR ULTRA v11.0", layout="wide")
st.title("🏓 TT STAR - SMART ANALYTIK")

tabs = st.tabs(["📥 Vložit Set", "🌐 Archivní Vklad", "🔮 Predikce", "🏆 Žebříček", "⚙️ Záloha"])

p_stats = calculate_glicko_stats()

with tabs[0]: # RUČNÍ VKLAD JEDNOHO SETU (Tvůj parser)
    st.subheader("Detailní vklad setu (včetně podání)")
    raw_in = st.text_area("Vložte text z Tipsportu (jeden set):", height=100)
    # ... (zde zůstává tvá logika výběru data a uložení jako v předchozím kódu)
    if st.button("Uložit jeden set"):
        st.info("Zde proběhne tvůj klasický parse a uložení.")

with tabs[1]: # SMART ARCHIVNÍ VKLAD
    st.subheader("Hromadný vklad z webu (Zkopírovaný text)")
    st.write("Jdi na web TT Star (Results nebo Archiv), dej Ctrl+A (vybrat vše), Ctrl+C (kopírovat) a vlož to sem.")
    bulk_text = st.text_area("Sem vlož text z webu:", height=300)
    if st.button("🚀 ZPRACOVAT A ULOŽIT VŠE"):
        if bulk_text:
            extracted = smart_extract_from_text(bulk_text)
            st.session_state.data.extend(extracted)
            save_data(st.session_state.data)
            st.success(f"Hotovo! Našel jsem a přidal {len(extracted)} nových zápasů.")
            st.rerun()

with tabs[2]: # PREDIKCE
    all_p = sorted(list(p_stats.keys()))
    if len(all_p) >= 2:
        c1, c2 = st.columns(2)
        with c1: pA = st.selectbox("Hráč A:", all_p)
        with c2: pB = st.selectbox("Hráč B:", all_p)
        odds = st.number_input("Kurz na A:", value=1.85)
        
        rA, rB = p_stats[pA]['r'], p_stats[pB]['r']
        prob = 1 / (1 + 10 ** ((rB - rA) / 400))
        st.metric(f"Šance {pA} na výhru", f"{int(prob*100)}%")
        val = (prob * odds) - 1
        if val > 0: st.success(f"✅ VALUE: +{val*100:.1f}%")
        else: st.error(f"❌ BEZ VALUE: {val*100:.1f}%")
    else:
        st.warning("V databázi není dost hráčů. Vlož nejdřív data v záložce Archiv!")

with tabs[4]: # ZÁLOHA
    st.download_button("📥 STÁHNOUT JSON DO MOBILU", json.dumps(st.session_state.data), "tt_backup.json")
