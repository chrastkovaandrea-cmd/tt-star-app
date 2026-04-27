import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import math

# --- 1. NASTAVENÍ A DATA ---
DATA_FILE = "tt_star_ultra_v9.json"
BASE_ELO = 1500
K_FACTOR = 32

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
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- 2. LOGIKA PREDIKCE (MATH ENGINE) ---
def get_win_prob(eloA, eloB):
    return 1 / (1 + 10 ** ((eloB - eloA) / 400))

def predict_stats(eloA, eloB):
    pA_win_match = get_win_prob(eloA, eloB)
    # Odhad pravděpodobnosti vyhrání JEDNOHO BODU (zjednodušený model)
    pA_point = 0.5 + (pA_win_match - 0.5) * 0.2
    
    # Simulace Over/Under 18.5 (šance na stav 9:10 nebo 10:9 a vyšší)
    # Ve stolním tenise je hranice 18.5 bodu velmi častá
    prob_over_18_5 = (pA_point * (1-pA_point)) * 3.5 # Empirický koeficient pro TT
    prob_over_18_5 = min(max(prob_over_18_5, 0.3), 0.7) # Omezení reality

    return {
        "probA": pA_win_match,
        "probB": 1 - pA_win_match,
        "over18_5": prob_over_18_5,
        "under18_5": 1 - prob_over_18_5,
        "expected_score": "11:9" if pA_win_match > 0.5 else "9:11"
    }

# --- 3. SMART PARSER v9.4 (Stabilní) ---
def parse_live_text(text):
    raw_lines = [l.strip() for l in text.split('\n') if l.strip()]
    clean_lines = [l for l in raw_lines if "milestone-logo" not in l.lower() and l not in [".", ":"]]
    if len(clean_lines) < 2: return None
    pA_name = normalize_name(clean_lines[0])
    pB_name = normalize_name(clean_lines[1])
    detected_starter = "A" 
    serve_match = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text, re.IGNORECASE)
    if serve_match:
        found_name = normalize_name(serve_match.group(1))
        if found_name and (found_name in pB_name or pB_name in found_name):
            detected_starter = "B"
    all_scores = re.findall(r'(\d+)\s*:\s*(\d+)', text)
    if not all_scores: return None
    points = [(int(a), int(b)) for a, b in all_scores]
    if (points[0][0] + points[0][1]) > (points[-1][0] + points[-1][1]):
        points.reverse()
    sequence, last_a, last_b, unique_points = [], 0, 0, []
    for p in points:
        if not unique_points or p != unique_points[-1]:
            if unique_points and (p[0] + p[1]) < (unique_points[-1][0] + unique_points[-1][1]): continue
            unique_points.append(p)
    for a, b in unique_points:
        if a > last_a: sequence.append("A")
        elif b > last_b: sequence.append("B")
        last_a, last_b = a, b
    return {"A": pA_name, "B": pB_name, "score": f"{last_a}:{last_b}", "win": 1 if last_a > last_b else 0, "sequence": sequence, "starter": detected_starter}

def calculate_elos():
    elos = {}
    for entry in st.session_state.data:
        pA, pB = entry.get("A", "Neznámý"), entry.get("B", "Neznámý")
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        exp_A = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        actual_A = entry.get("win", 0)
        shift = K_FACTOR * (actual_A - exp_A)
        elos[pA] += shift
        elos[pB] -= shift
    return elos

# --- 4. UI ---
st.set_page_config(page_title="TT STAR PREDICTOR v9.5", layout="wide")
st.title("🏓 TT STAR - VŠEUMĚL v9.5")

tabs = st.tabs(["📥 Vložit data", "🔮 PREDIKCE ZÁPASU", "🏆 Žebříček", "🗑️ Správa dat"])

with tabs[0]:
    st.subheader("📋 Rychlé vložení setu")
    raw_text = st.text_area("Vložte text z Tipsportu:", height=150)
    if st.button("🚀 Uložit do databáze"):
        if raw_text:
            result = parse_live_text(raw_text)
            if result:
                new_entry = {"id": str(datetime.datetime.now().timestamp()), "A": result["A"], "B": result["B"], "sequence": result["sequence"], "starter": result["starter"], "win": result["win"], "score": result["score"], "timestamp": str(datetime.datetime.now())}
                st.session_state.data.append(new_entry)
                save_data(st.session_state.data)
                st.success(f"Uloženo: {result['A']} vs {result['B']} ({result['score']})")

with tabs[1]:
    st.subheader("🔮 Analýza a Predikce příštího setu")
    elos = calculate_elos()
    c1, c2 = st.columns(2)
    with c1: tA = st.text_input("Hráč A").upper()
    with c2: tB = st.text_input("Hráč B").upper()
    
    if tA and tB:
        eA, eB = elos.get(tA, BASE_ELO), elos.get(tB, BASE_ELO)
        stats = predict_stats(eA, eB)
        
        col_res, col_over = st.columns(2)
        with col_res:
            st.info(f"🏆 Vítěz setu: **{tA if stats['probA'] > stats['probB'] else tB}**")
            st.write(f"Šance {tA}: {round(stats['probA']*100)}%")
            st.write(f"Šance {tB}: {round(stats['probB']*100)}%")
            st.metric("Fair Kurz", round(1/stats['probA'] if stats['probA']>0 else 0, 2))
        
        with col_over:
            st.warning(f"🔢 Body v setu (Over/Under 18.5)")
            st.write(f"VÍCE než 18.5 bodu: **{round(stats['over18_5']*100)}%**")
            st.write(f"MÉNĚ než 18.5 bodu: **{round(stats['under18_5']*100)}%**")
            st.write(f"Odhadované skóre: **{stats['expected_score']}**")

with tabs[2]:
    st.subheader("🏆 Elo Žebříček")
    current_elos = calculate_elos()
    for r, (n, v) in enumerate(sorted(current_elos.items(), key=lambda x: x[1], reverse=True)):
        st.write(f"{r+1}. **{n}** — {int(v)} Elo")

with tabs[3]:
    st.subheader("📜 Historie")
    for i in range(len(st.session_state.data)-1, -1, -1):
        entry = st.session_state.data[i]
        st.write(f"{entry.get('timestamp','?')[:16]} | **{entry.get('A','?')}** vs **{entry.get('B','?')}** ({entry.get('score','?')})")
        if st.button("Smazat", key=f"del_{i}"):
            st.session_state.data.pop(i)
            save_data(st.session_state.data)
            st.rerun()

st.sidebar.write(f"Sety v paměti: {len(st.session_state.data)}")
