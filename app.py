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
    name = re.sub(r'^[A-Z]\.\s+', '', name) # Odstraní "L. "
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
    """Parser pro složitý text z Tipsportu (Limonov vs Bako)"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) < 5: return None
    
    # Hledání jmen (obvykle první dva řádky po 'sety123')
    pA = normalize_name(lines[2]) if len(lines) > 2 else ""
    pB = normalize_name(lines[4]) if len(lines) > 4 else ""
    
    # Hledání skóre v řádku "Konec zápasu" nebo "Konec X. setu"
    score_match = re.search(r'\((\d+):(\d+)\)', text)
    final_score = "0:0"
    win = 0
    if score_match:
        s1, s2 = score_match.group(1), score_match.group(2)
        final_score = f"{s1}:{s2}"
        win = 1 if int(s1) > int(s2) else 0
        
    return {"A": pA, "B": pB, "score": final_score, "win": win}

def smart_extract_ttstar(text):
    """Parser pro archiv TT Star (ten svislý seznam)"""
    new_entries = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i in range(len(lines)):
        score_match = re.match(r'^(\d)\s*:\s*(\d)$', lines[i])
        if score_match and i >= 2:
            pA = normalize_name(lines[i-2])
            pB = normalize_name(lines[i-1])
            if len(pA) > 3 and len(pB) > 3:
                s1, s2 = int(score_match.group(1)), int(score_match.group(2))
                new_entries.append({
                    "A": pA, "B": pB, "score": f"{s1}:{s2}",
                    "win": 1 if s1 > s2 else 0,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "source": "bulk"
                })
    return new_entries

# --- 3. LOGIKA VÝPOČTŮ ---

def get_starter_for_set(first_set_starter, current_set_num):
    """Vypočítá, kdo podává, na základě střídání setů"""
    # 1. set = starter, 2. set = opposite, 3. set = starter...
    if current_set_num % 2 != 0: # Lichý set (1, 3, 5)
        return first_set_starter
    else: # Sudý set (2, 4)
        return "B" if first_set_starter == "A" else "A"

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
st.set_page_config(page_title="TT STAR v11.9", layout="wide")
st.title("🏓 TT STAR ANALYTIK PRO")

p_stats = calculate_glicko()
tabs = st.tabs(["📥 Vložit Data", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

# --- VKLÁDÁNÍ ---
with tabs[0]:
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.subheader("Vklad z Tipsportu (Live)")
        tip_text = st.text_area("Vlož text z Tipsportu:", height=150)
        res = parse_tipsport_complex(tip_text) if tip_text else None
        
        c1, c2 = st.columns(2)
        m_date = c1.date_input("Datum:", datetime.date.today())
        m_set = c2.number_input("Tento set č.:", 1, 5, value=1)
        
        # Klíčová funkce: Výběr, kdo podával v 1. SETU
        m_first_starter = st.selectbox("Kdo podával v 1. SETU zápasu?", ["A", "B"])
        
        # Automatický výpočet pro aktuální set
        m_current_starter = get_starter_for_set(m_first_starter, m_set)
        st.info(f"V {m_set}. setu automaticky podává: **Hráč {m_current_starter}**")
        
        if st.button("🚀 ULOŽIT SET"):
            if res:
                dt = datetime.datetime.combine(m_date, datetime.datetime.now().time())
                st.session_state.data.append({
                    "A": res["A"], "B": res["B"], "score": res["score"],
                    "win": res["win"], "starter": m_current_starter, 
                    "set_num": m_set, "timestamp": dt.isoformat(), "source": "manual"
                })
                save_data(st.session_state.data)
                st.success("Set úspěšně uložen!"); st.rerun()

    with col_r:
        st.subheader("Vklad z Archivu TT Star")
        bulk_text = st.text_area("Vlož zkopírovaný text turnaje:", height=150)
        if st.button("📥 ZPRACOVAT ARCHIV"):
            found = smart_extract_ttstar(bulk_text)
            st.session_state.data.extend(found)
            save_data(st.session_state.data)
            st.success(f"Uloženo {len(found)} zápasů!"); st.rerun()

# --- PREDIKCE ---
with tabs[1]:
    st.subheader("Predikce zápasu")
    p_list = sorted(list(p_stats.keys()))
    if len(p_list) >= 2:
        cA, cB = st.columns(2)
        with cA: pA = st.selectbox("Hráč A:", p_list); oA = st.number_input("Kurz na A:", 1.01, 10.0, 1.85)
        with cB: pB = st.selectbox("Hráč B:", p_list)
        if pA != pB:
            prob = 1 / (1 + 10 ** ((p_stats[pB]['r'] - p_stats[pA]['r']) / 400))
            st.metric(f"Šance {pA}", f"{int(prob*100)}%")
            val = (prob * oA) - 1
            if val > 0: st.success(f"VALUE: +{val*100:.1f}%")
            else: st.error("BEZ VALUE")

# --- ŽEBŘÍČEK ---
with tabs[2]:
    st.subheader("Žebříček Glicko-2")
    df = pd.DataFrame([{"Hráč": k, "Rating": int(v['r']), "Zápasy": v['matches']} for k, v in p_stats.items()])
    st.dataframe(df.sort_values("Rating", ascending=False), use_container_width=True)

# --- HISTORIE ---
with tabs[3]:
    st.subheader("Historie (Možnost úprav)")
    if st.session_state.data:
        rev_data = list(enumerate(st.session_state.data))
        rev_data.reverse()
        for idx, entry in rev_data[:15]:
            with st.expander(f"{entry['A']} vs {entry['B']} ({entry['score']})"):
                c1, c2, c3 = st.columns(3)
                nA = c1.text_input("Hráč A", entry['A'], key=f"ha{idx}")
                nB = c2.text_input("Hráč B", entry['B'], key=f"hb{idx}")
                nS = c3.text_input("Skóre", entry['score'], key=f"hs{idx}")
                c4, c5 = st.columns(2)
                nSet = c4.number_input("Set č.", 1, 5, entry.get('set_num',1), key=f"hset{idx}")
                nSt = c5.selectbox("Kdo podával", ["A", "B"], 0 if entry.get('starter')=="A" else 1, key=f"hst{idx}")
                if st.button("Uložit změny", key=f"hb{idx}"):
                    st.session_state.data[idx].update({"A":nA.upper(), "B":nB.upper(), "score":nS, "set_num":nSet, "starter":nSt})
                    save_data(st.session_state.data); st.rerun()
                if st.button("Smazat", key=f"hd{idx}"):
                    st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()
    
    st.divider()
    st.download_button("📥 STÁHNOUT ZÁLOHU", json.dumps(st.session_state.data), "backup.json")
    up = st.file_uploader("Obnovit data ze souboru")
    if up:
        st.session_state.data = json.load(up); save_data(st.session_state.data); st.rerun()
