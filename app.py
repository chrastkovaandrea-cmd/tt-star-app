import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import numpy as np

# --- 1. NASTAVENÍ A DATA ---
DATA_FILE = "tt_star_ultra_v8.json"
BASE_ELO = 1500
K_FACTOR = 32

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z][a-z]?\.', '', name) # Smaže "Mi." nebo "T."
    return name.strip().upper()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- 2. LOGIKA PODÁNÍ A ELO ---
def get_current_server(sequence_length, starter="A"):
    """Vypočítá, kdo má podávat."""
    if sequence_length >= 20: # Stav 10:10 a dál
        return starter if sequence_length % 2 == 0 else ("B" if starter == "A" else "A")
    cycle = (sequence_length // 2) % 2
    return starter if cycle == 0 else ("B" if starter == "A" else "A")

def calculate_elos():
    """Vypočítá aktuální Elo pro všechny hráče v databázi."""
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

# --- 3. SMART PARSER ---
def parse_live_text(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) < 2: return None

    pA = normalize_name(lines[0])
    pB = normalize_name(lines[1])

    all_scores = re.findall(r'(\d+)\s*:\s*(\d+)', text)
    if not all_scores: return None

    points = [(int(a), int(b)) for a, b in all_scores]
    points.reverse()

    sequence = []
    last_a, last_b = 0, 0
    unique_points = []
    for p in points:
        if not unique_points or p != unique_points[-1]:
            unique_points.append(p)

    for a, b in unique_points:
        if a > last_a: sequence.append("A")
        elif b > last_b: sequence.append("B")
        last_a, last_b = a, b

    return {"A": pA, "B": pB, "score": f"{last_a}:{last_b}", "win": 1 if last_a > last_b else 0, "sequence": sequence}

# --- 4. UI STREAMLIT ---
st.set_page_config(page_title="TT STAR ULTRA v8", layout="wide")
st.title("🏓 TT STAR - SMART ANALYZER v8")

tabs = st.tabs(["📥 Rychlé Vložení", "📊 Predikce & Value", "🏆 Žebříček"])

# --- TAB: VLOŽENÍ ---
with tabs[0]:
    st.subheader("📋 Vložit text ze zápasu")
    raw_text = st.text_area("Sem vlož text (jména + body):", height=250)
    starter = st.radio("Kdo v tomto setu začal podávat?", ["A", "B"], horizontal=True)
    
    if st.button("⚡ Analyzovat a uložit"):
        if raw_text:
            result = parse_live_text(raw_text)
            if result and len(result['sequence']) > 0:
                new_entry = {
                    "A": result["A"], "B": result["B"],
                    "sequence": result["sequence"],
                    "starter": starter,
                    "win": result["win"],
                    "timestamp": str(datetime.datetime.now())
                }
                st.session_state.data.append(new_entry)
                save_data(st.session_state.data)
                st.success(f"Uloženo: {result['A']} vs {result['B']} ({result['score']})")
                st.balloons()
            else:
                st.error("Chyba: Parser nenašel skóre. Zkopíruj text znovu.")

# --- TAB: PREDIKCE ---
with tabs[1]:
    st.subheader("🔎 Hledání Value Betu")
    elos = calculate_elos()
    
    col1, col2 = st.columns(2)
    with col1:
        target_A = st.text_input("Hráč A").upper()
        odds_A = st.number_input("Kurz sázkovky na A", value=1.85)
    with col2:
        target_B = st.text_input("Hráč B").upper()

    if target_A and target_B:
        eA = elos.get(target_A, BASE_ELO)
        eB = elos.get(target_B, BASE_ELO)
        
        prob_A = 1 / (1 + 10 ** ((eB - eA) / 400))
        fair_odds = 1 / prob_A
        
        st.divider()
        st.write(f"### Elo: {int(eA)} vs {int(eB)}")
        st.metric("Fair Kurz", round(fair_odds, 2))
        
        edge = (odds_A / fair_odds) - 1
        if edge > 0.05:
            st.success(f"🔥 VALUE BET: +{round(edge*100, 1)}% na {target_A}")
        else:
            st.warning(f"Edge: {round(edge*100, 1)}% (Nevýhodné)")

# --- TAB: ŽEBŘÍČEK ---
with tabs[2]:
    st.subheader("🏆 Aktuální Elo Ranking")
    elos = calculate_elos()
    if elos:
        sorted_ranking = sorted(elos.items(), key=lambda x: x[1], reverse=True)
        for r, (name, val) in enumerate(sorted_ranking):
            st.write(f"{r+1}. **{name}** — {int(val)} bodů")
    else:
        st.info("Databáze je prázdná.")

st.sidebar.write(f"V databázi: {len(st.session_state.data)} setů")
