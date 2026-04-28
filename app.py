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
def parse_tipsport_complex(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) < 5: return None
    # Jména jsou obvykle na začátku pod sebou
    pA = normalize_name(lines[2]) if len(lines) > 2 else "HRÁČ A"
    pB = normalize_name(lines[4]) if len(lines) > 4 else "HRÁČ B"
    score_match = re.search(r'\((\d+):(\d+)\)', text)
    f_score, win = "0:0", 0
    if score_match:
        s1, s2 = int(score_match.group(1)), int(score_match.group(2))
        f_score = f"{s1}:{s2}"
        win = 1 if s1 > s2 else 0
    return {"A": pA, "B": pB, "score": f_score, "win": win}

def smart_extract_ttstar(text):
    new_entries = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i in range(len(lines)):
        score_match = re.match(r'^(\d)\s*:\s*(\d)$', lines[i])
        if score_match and i >= 2:
            pA, pB = normalize_name(lines[i-2]), normalize_name(lines[i-1])
            if len(pA) > 3 and len(pB) > 3:
                s1, s2 = int(score_match.group(1)), int(score_match.group(2))
                new_entries.append({"A": pA, "B": pB, "score": f"{s1}:{s2}", "win": 1 if s1 > s2 else 0, "timestamp": datetime.datetime.now().isoformat(), "source": "bulk"})
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
st.set_page_config(page_title="TT STAR v12.0", layout="wide")
st.title("🏓 TT STAR ANALYTIK PRO")

p_stats = calculate_glicko()
tabs = st.tabs(["📥 Vložit Data", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with tabs[0]:
    cL, cR = st.columns(2)
    with cL:
        st.subheader("Tipsport Live")
        tip_in = st.text_area("Vlož text z Tipsportu:", height=150, key="tip_area")
        res = parse_tipsport_complex(tip_in) if tip_in else None
        c1, c2 = st.columns(2)
        m_date = c1.date_input("Datum:", datetime.date.today())
        m_set = c2.number_input("Set č.:", 1, 5, value=1)
        m_first = st.selectbox("Kdo začal podávat v 1. SETU?", ["A", "B"])
        
        # LOGIKA STŘÍDÁNÍ: Lichý set = začínající, sudý set = ten druhý
        if m_set % 2 != 0: curr_starter = m_first
        else: curr_starter = "B" if m_first == "A" else "A"
        
        st.info(f"V {m_set}. setu podává: **HRÁČ {curr_starter}**")
        if st.button("🚀 ULOŽIT SET"):
            if res:
                dt = datetime.datetime.combine(m_date, datetime.datetime.now().time())
                st.session_state.data.append({"A": res["A"], "B": res["B"], "score": res["score"], "win": res["win"], "starter": curr_starter, "set_num": m_set, "timestamp": dt.isoformat()})
                save_data(st.session_state.data); st.success("Uloženo!"); st.rerun()

    with cR:
        st.subheader("Archiv TT Star")
        bulk_in = st.text_area("Vlož text z webu:", height=150, key="bulk_area")
        if st.button("📥 ZPRACOVAT ARCHIV"):
            fnd = smart_extract_ttstar(bulk_in)
            st.session_state.data.extend(fnd); save_data(st.session_state.data)
            st.success(f"Uloženo {len(fnd)} zápasů!"); st.rerun()

with tabs[1]:
    st.subheader("Predikce")
    p_list = sorted(list(p_stats.keys()))
    if len(p_list) >= 2:
        col1, col2 = st.columns(2)
        with col1: pA = st.selectbox("Hráč A:", p_list); oA = st.number_input("Kurz na A:", 1.01, 10.0, 1.85)
        with col2: pB = st.selectbox("Hráč B:", p_list)
        if pA != pB:
            prob = 1 / (1 + 10 ** ((p_stats[pB]['r'] - p_stats[pA]['r']) / 400))
            st.metric(f"Šance {pA}", f"{int(prob*100)}%")
            val = (prob * oA) - 1
            if val > 0: st.success(f"VALUE: +{val*100:.1f}%")
            else: st.error("BEZ VALUE")

with tabs[2]:
    st.subheader("Žebříček")
    df = pd.DataFrame([{"Hráč": k, "Rating": int(v['r']), "Zápasy": v['matches']} for k, v in p_stats.items()])
    st.dataframe(df.sort_values("Rating", ascending=False), use_container_width=True)

with tabs[3]:
    st.subheader("Historie a správa")
    if st.session_state.data:
        rev_data = list(enumerate(st.session_state.data))
        rev_data.reverse()
        for idx, entry in rev_data[:15]:
            with st.expander(f"{entry['A']} vs {entry['B']} ({entry['score']})"):
                c1, c2, c3 = st.columns(3)
                eA = c1.text_input("Hráč A", entry['A'], key=f"editA_{idx}")
                eB = c2.text_input("Hráč B", entry['B'], key=f"editB_{idx}")
                eS = c3.text_input("Skóre", entry['score'], key=f"editS_{idx}")
                c4, c5 = st.columns(2)
                eSet = c4.number_input("Set", 1, 5, entry.get('set_num',1), key=f"editSet_{idx}")
                eSt = c5.selectbox("Podání", ["A", "B"], 0 if entry.get('starter')=="A" else 1, key=f"editSt_{idx}")
                
                # Tlačítka s unikátními klíči
                b1, b2 = st.columns(2)
                if b1.button("💾 Uložit", key=f"btn_save_{idx}"):
                    st.session_state.data[idx].update({"A":eA.upper(), "B":eB.upper(), "score":eS, "set_num":eSet, "starter":eSt})
                    save_data(st.session_state.data); st.rerun()
                if b2.button("🗑️ Smazat", key=f"btn_del_{idx}"):
                    st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()

    st.divider()
    st.download_button("📥 STÁHNOUT ZÁLOHU", json.dumps(st.session_state.data, indent=4), "tt_backup.json")
    up = st.file_uploader("Nahrát zálohu")
    if up:
        st.session_state.data = json.load(up); save_data(st.session_state.data); st.rerun()
