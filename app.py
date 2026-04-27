import streamlit as st
import unicodedata
import json
import os
import re
import datetime

# --- 1. NASTAVENÍ A DATA ---
DATA_FILE = "tt_star_ultra_v9.json"
BASE_ELO = 1500
K_FACTOR = 32

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z][a-z]?\.', '', name) 
    return name.strip().upper()

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- 2. SMART PARSER ---
def parse_live_text(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) < 2: return None
    pA_name = normalize_name(lines[0])
    pB_name = normalize_name(lines[1])
    detected_starter = "A"
    serve_match = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text)
    if serve_match:
        found_name = normalize_name(serve_match.group(1))
        if found_name in pB_name or pB_name in found_name:
            detected_starter = "B"
    all_scores = re.findall(r'(\d+)\s*:\s*(\d+)', text)
    if not all_scores: return None
    points = [(int(a), int(b)) for a, b in all_scores]
    if (points[0][0] + points[0][1]) > (points[-1][0] + points[-1][1]):
        points.reverse()
    sequence = []
    last_a, last_b = 0, 0
    unique_points = []
    for p in points:
        if not unique_points or p != unique_points[-1]:
            if len(unique_points) > 0:
                if (p[0] + p[1]) < (unique_points[-1][0] + unique_points[-1][1]): continue
            unique_points.append(p)
    for a, b in unique_points:
        if a > last_a: sequence.append("A")
        elif b > last_b: sequence.append("B")
        last_a, last_b = a, b
    return {"A": pA_name, "B": pB_name, "score": f"{last_a}:{last_b}", "win": 1 if last_a > last_b else 0, "sequence": sequence, "starter": detected_starter}

def calculate_elos():
    elos = {}
    for entry in st.session_state.data:
        pA, pB = entry["A"], entry["B"]
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        exp_A = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        actual_A = entry["win"]
        shift = K_FACTOR * (actual_A - exp_A)
        elos[pA] += shift
        elos[pB] -= shift
    return elos

# --- 3. UI ---
st.set_page_config(page_title="TT STAR ULTRA v9.2", layout="wide")
st.title("🏓 TT STAR ANALYZER v9.2")

tabs = st.tabs(["📥 Vložit data", "📊 Analýza", "🏆 Žebříček", "🗑️ Správa dat"])

with tabs[0]:
    st.subheader("📋 Vložení textu")
    raw_text = st.text_area("Vložte text zápasu:", height=200)
    if st.button("🚀 Analyzovat a Uložit set"):
        if raw_text:
            result = parse_live_text(raw_text)
            if result:
                new_entry = {"id": str(datetime.datetime.now().timestamp()), "A": result["A"], "B": result["B"], "sequence": result["sequence"], "starter": result["starter"], "win": result["win"], "score": result["score"], "timestamp": str(datetime.datetime.now())}
                st.session_state.data.append(new_entry)
                save_data(st.session_state.data)
                st.success(f"Uloženo: {result['A']} vs {result['B']} ({result['score']})")
                st.balloons()

with tabs[1]:
    st.subheader("🔎 Hledání Value Betu")
    elos = calculate_elos()
    c1, c2 = st.columns(2)
    with c1: target_A = st.text_input("Hráč A").upper(); odds_A = st.number_input("Kurz na A", value=2.0)
    with c2: target_B = st.text_input("Hráč B").upper()
    if target_A and target_B:
        eA, eB = elos.get(target_A, BASE_ELO), elos.get(target_B, BASE_ELO)
        prob_A = 1 / (1 + 10 ** ((eB - eA) / 400))
        fair_odds = 1 / prob_A
        st.write(f"### Elo: {int(eA)} vs {int(eB)} | Fair kurz: {round(fair_odds, 2)}")
        edge = (odds_A / fair_odds) - 1
        if edge > 0.05: st.success(f"🔥 VALUE: +{round(edge*100, 1)}%")

with tabs[2]:
    st.subheader("🏆 Žebříček")
    current_elos = calculate_elos()
    for r, (n, v) in enumerate(sorted(current_elos.items(), key=lambda x: x[1], reverse=True)):
        st.write(f"{r+1}. **{n}** — {int(v)} Elo")

with tabs[3]:
    st.subheader("📜 Historie a mazání")
    if not st.session_state.data:
        st.info("Žádná data k zobrazení.")
    else:
        # Zobrazíme seznam od nejnovějšího
        for i, entry in enumerate(reversed(st.session_state.data)):
            real_index = len(st.session_state.data) - 1 - i
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{entry['A']}** vs **{entry['B']}** ({entry['score']})")
            with col2:
                st.write(f"{entry['timestamp'][:16]}")
            with col3:
                if st.button("Smazat", key=f"del_{real_index}"):
                    st.session_state.data.pop(real_index)
                    save_data(st.session_state.data)
                    st.rerun() # Refresh stránky

st.sidebar.write(f"Sety v paměti: {len(st.session_state.data)}")
