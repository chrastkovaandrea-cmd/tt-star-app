import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import pandas as pd

# --- 1. NASTAVENÍ ---
DATA_FILE = "tt_star_ultra_v10.json"
BASE_RATING = 1500
BASE_RD = 350 

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    # Odstraní iniciály jako "L. ", "T. " atd.
    name = re.sub(r'^[A-Z]\.\s+', '', name)
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

# --- 2. NOVÝ CHYTRÝ PARSER PRO TVŮJ TEXT ---
def smart_extract_v3(text):
    """Speciálně upraveno pro formát: Jméno \n Jméno \n Výsledek"""
    new_entries = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    for i in range(len(lines)):
        # Hledáme řádek, kde je skóre (např. "3 : 1" nebo "3:0")
        score_match = re.match(r'^(\d)\s*:\s*(\d)$', lines[i])
        if score_match and i >= 2:
            # Předpokládáme, že dva řádky nad skóre jsou jména hráčů
            pA = normalize_name(lines[i-2])
            pB = normalize_name(lines[i-1])
            score = f"{score_match.group(1)}:{score_match.group(2)}"
            
            # Kontrola, zda to nejsou nesmysly (jako čísla nebo "ČAS")
            if len(pA) > 3 and len(pB) > 3 and ":" in score:
                # Duplicita
                if not any(d['A'] == pA and d['B'] == pB and d['score'] == score for d in st.session_state.data[-500:]):
                    s1, s2 = int(score_match.group(1)), int(score_match.group(2))
                    new_entries.append({
                        "A": pA, "B": pB, "score": score,
                        "win": 1 if s1 > s2 else 0,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "source": "ttstar_web"
                    })
    return new_entries

# --- 3. GLICKO VÝPOČET ---
def calculate_glicko_stats():
    players = {}
    data = sorted(st.session_state.data, key=lambda x: x.get('timestamp', '0'))
    for entry in data:
        pA, pB, winA = entry.get("A"), entry.get("B"), entry.get("win", 0)
        if not pA or not pB: continue
        for p in [pA, pB]:
            if p not in players: players[p] = {"r": BASE_RATING, "rd": BASE_RD, "matches": 0}
        rA, rdA, rB, rdB = players[pA]["r"], players[pA]["rd"], players[pB]["r"], players[pB]["rd"]
        ea = 1 / (1 + 10 ** ((rB - rA) / 400))
        players[pA]["r"] += (rdA / 10) * (winA - ea)
        players[pB]["r"] += (rdB / 10) * ((1 - winA) - (1 - ea))
        players[pA]["rd"] = max(30, rdA - 4)
        players[pB]["rd"] = max(30, rdB - 4)
        players[pA]["matches"] += 1; players[pB]["matches"] += 1
    return players

# --- 4. UI ---
st.set_page_config(page_title="TT STAR v11.7", layout="wide")
st.title("🏓 TT STAR - ANALYTIK PRO")

p_stats = calculate_glicko_stats()
tabs = st.tabs(["📥 Vklady", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Hromadný vklad z webu")
        bulk_text = st.text_area("Vlož text z TT Star (celý den):", height=300)
        if st.button("📥 ZPRACOVAT CELÝ DEN"):
            found = smart_extract_v3(bulk_text)
            st.session_state.data.extend(found)
            save_data(st.session_state.data)
            st.success(f"Nalezeno a uloženo {len(found)} zápasů!")
            st.rerun()
    with c2:
        st.subheader("Ruční vklad (Tipsport)")
        # ... (Tady je tvůj kód pro manuální vklad, nezměněn)
        st.info("Zde vkládej live sety jako dřív.")

with tabs[1]:
    st.subheader("Predikce")
    p_list = sorted(list(p_stats.keys()))
    if len(p_list) >= 2:
        colA, colB = st.columns(2)
        with colA: pA = st.selectbox("Hráč A:", p_list); oddsA = st.number_input("Kurz na A:", 1.01, 10.0, 1.85)
        with colB: pB = st.selectbox("Hráč B:", p_list)
        if pA != pB:
            prob = 1 / (1 + 10 ** ((p_stats[pB]['r'] - p_stats[pA]['r']) / 400))
            st.metric(f"Šance {pA}", f"{int(prob*100)}%")
            val = (prob * oddsA) - 1
            if val > 0: st.success(f"VALUE: +{val*100:.1f}%")
            else: st.error("BEZ VALUE")

with tabs[2]:
    st.subheader("Žebříček")
    if p_stats:
        df = pd.DataFrame([{"Hráč": k, "Rating": int(v['r']), "Zápasy": v['matches']} for k, v in p_stats.items()])
        st.dataframe(df.sort_values("Rating", ascending=False), use_container_width=True)

with tabs[4]:
    # HISTORIE S MOŽNOSTÍ ÚPRAVY PODÁNÍ
    st.subheader("Historie a Úpravy")
    if st.session_state.data:
        for idx, entry in list(enumerate(st.session_state.data))[-15:]:
            with st.expander(f"{entry['A']} vs {entry['B']} ({entry['score']})"):
                c1, c2, c3 = st.columns(3)
                newA = c1.text_input("Hráč A", entry['A'], key=f"nA{idx}")
                newB = c2.text_input("Hráč B", entry['B'], key=f"nB{idx}")
                newS = c3.text_input("Skóre", entry['score'], key=f"nS{idx}")
                c4, c5 = st.columns(2)
                newSet = c4.number_input("Set", 1, 5, entry.get('set_num',1), key=f"nSet{idx}")
                newStart = c5.selectbox("Podání", ["A", "B"], 0 if entry.get('starter')=="A" else 1, key=f"nSt{idx}")
                if st.button("Uložit", key=f"sv{idx}"):
                    st.session_state.data[idx].update({"A":newA, "B":newB, "score":newS, "set_num":newSet, "starter":newStart})
                    save_data(st.session_state.data); st.rerun()
    st.download_button("📥 STÁHNOUT ZÁLOHU", json.dumps(st.session_state.data), "zaloha.json")
