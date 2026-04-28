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
    name = re.sub(r'^[A-Z]\.\s+', '', name)
    # Odfiltrujeme skóre a pomocné texty, aby se nedostaly do jmen
    if re.match(r'^\d\s*:\s*\d$', name) or "SET" in name.upper() or "FINALE" in name.upper():
        return ""
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

# --- 2. PARSERY ---
def smart_extract_ttstar_v4(text):
    new_entries = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i in range(len(lines)):
        score_match = re.match(r'^(\d)\s*:\s*(\d)$', lines[i])
        if score_match and i >= 2:
            pA = normalize_name(lines[i-2])
            pB = normalize_name(lines[i-1])
            # Validace: jména nesmí být prázdná a nesmí to být skóre
            if pA and pB and len(pA) > 2 and len(pB) > 2:
                s1, s2 = int(score_match.group(1)), int(score_match.group(2))
                new_entries.append({
                    "A": pA, "B": pB, "score": f"{s1}:{s2}",
                    "win": 1 if s1 > s2 else 0,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "source": "bulk"
                })
    return new_entries

# --- 3. GLICKO LOGIKA ---
def calculate_glicko():
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
        players[pA]["rd"] = max(30, rdA - 4); players[pB]["rd"] = max(30, rdB - 4)
        players[pA]["matches"] += 1; players[pB]["matches"] += 1
    return players

# --- 4. UI ---
st.set_page_config(page_title="TT STAR v12.1", layout="wide")
st.title("🏓 TT STAR ANALYTIK PRO")

p_stats = calculate_glicko()
tabs = st.tabs(["📥 Vložit Data", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with tabs[0]:
    cL, cR = st.columns(2)
    with cL:
        st.subheader("Tipsport Live")
        tip_in = st.text_area("Vlož text z Tipsportu:", height=150, key="tip_v12")
        # Jednoduchý parser pro jména z Live textu
        lines = tip_in.split('\n')
        suggest_A = normalize_name(lines[2]) if len(lines) > 2 else ""
        suggest_B = normalize_name(lines[4]) if len(lines) > 4 else ""
        
        c1, c2 = st.columns(2)
        m_date = c1.date_input("Datum:", datetime.date.today())
        m_set = c2.number_input("Set č.:", 1, 5, value=1)
        m_first = st.selectbox("Kdo začal podávat v 1. SETU?", ["A", "B"])
        
        if m_set % 2 != 0: curr_starter = m_first
        else: curr_starter = "B" if m_first == "A" else "A"
        
        st.info(f"V {m_set}. setu podává: **HRÁČ {curr_starter}**")
        
        # Ruční kontrola jmen před uložením
        finalA = st.text_input("Jméno Hráče A:", suggest_A)
        finalB = st.text_input("Jméno Hráče B:", suggest_B)
        finalS = st.text_input("Skóre (např. 11:5):", "0:0")
        
        if st.button("🚀 ULOŽIT SET"):
            if finalA and finalB:
                s_parts = finalS.split(':')
                win_val = 1 if (len(s_parts)==2 and int(s_parts[0]) > int(s_parts[1])) else 0
                dt = datetime.datetime.combine(m_date, datetime.datetime.now().time())
                st.session_state.data.append({
                    "A": finalA.upper(), "B": finalB.upper(), "score": finalS, 
                    "win": win_val, "starter": curr_starter, "set_num": m_set, 
                    "timestamp": dt.isoformat()
                })
                save_data(st.session_state.data); st.success("Uloženo!"); st.rerun()

    with cR:
        st.subheader("Archiv TT Star")
        bulk_in = st.text_area("Vlož text z webu:", height=150, key="bulk_v12")
        if st.button("📥 ZPRACOVAT ARCHIV"):
            fnd = smart_extract_ttstar_v4(bulk_in)
            st.session_state.data.extend(fnd); save_data(st.session_state.data)
            st.success(f"Uloženo {len(fnd)} zápasů!"); st.rerun()

with tabs[1]:
    st.subheader("Predikce s kurzy")
    p_list = [p for p in sorted(list(p_stats.keys())) if p]
    if len(p_list) >= 2:
        col1, col2 = st.columns(2)
        with col1: 
            pA = st.selectbox("Hráč A:", p_list)
            oA = st.number_input("Kurz na A (Tipsport):", 1.01, 10.0, 1.85)
        with col2: 
            pB = st.selectbox("Hráč B:", p_list)
            oB = st.number_input("Kurz na B (Tipsport):", 1.01, 10.0, 1.85)
            
        if pA != pB:
            probA = 1 / (1 + 10 ** ((p_stats[pB]['r'] - p_stats[pA]['r']) / 400))
            probB = 1 - probA
            
            c_res1, c_res2 = st.columns(2)
            with c_res1:
                st.metric(f"Šance {pA}", f"{int(probA*100)}%")
                valA = (probA * oA) - 1
                if valA > 0: st.success(f"VALUE A: +{valA*100:.1f}%")
            with c_res2:
                st.metric(f"Šance {pB}", f"{int(probB*100)}%")
                valB = (probB * oB) - 1
                if valB > 0: st.success(f"VALUE B: +{valB*100:.1f}%")

with tabs[2]:
    st.subheader("Žebříček")
    # Zobrazíme jen skutečné hráče (ne skóre)
    valid_p = {k: v for k, v in p_stats.items() if k and not re.match(r'^\d\s*:\s*\d$', k)}
    df = pd.DataFrame([{"Hráč": k, "Rating": int(v['r']), "Zápasy": v['matches']} for k, v in valid_p.items()])
    st.dataframe(df.sort_values("Rating", ascending=False), use_container_width=True)

with tabs[3]:
    st.subheader("Historie a správa")
    if st.session_state.data:
        rev_data = list(enumerate(st.session_state.data))
        rev_data.reverse()
        for idx, entry in rev_data[:20]:
            with st.expander(f"{entry['A']} vs {entry['B']} ({entry['score']})"):
                c1, c2, c3 = st.columns(3)
                eA = c1.text_input("Hráč A", entry['A'], key=f"eA_{idx}")
                eB = c2.text_input("Hráč B", entry['B'], key=f"eB_{idx}")
                eS = c3.text_input("Skóre", entry['score'], key=f"eS_{idx}")
                b1, b2 = st.columns(2)
                if b1.button("💾 Uložit", key=f"bs_{idx}"):
                    st.session_state.data[idx].update({"A":eA.upper(), "B":eB.upper(), "score":eS})
                    save_data(st.session_state.data); st.rerun()
                if b2.button("🗑️ Smazat", key=f"bd_{idx}"):
                    st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()
    st.download_button("📥 STÁHNOUT ZÁLOHU", json.dumps(st.session_state.data, indent=4), "tt_backup.json")
