import streamlit as st
import unicodedata
import json
import os
import re
import datetime

# --- ZÁKLADNÍ FUNKCE ---
DATA_FILE = "tt_star_ultra_v7.json"

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    # Odstraní zkratky jako Mi. nebo T. a nechá jen příjmení
    name = re.sub(r'^[A-Z][a-z]?\.', '', name)
    return name.strip().upper()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- CHYTRÝ PARSER (To, co potřebuješ) ---
def parse_live_text(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # 1. Extrakce jmen (obvykle první dva řádky)
    player_a = normalize_name(lines[0])
    player_b = normalize_name(lines[1])
    
    # 2. Extrakce bodové sekvence
    # Hledáme vzory jako "11 : 7" nebo "11:7"
    points_found = []
    for line in lines:
        match = re.search(r'(\d+)\s*:\s*(\d+)', line)
        if match:
            a_pts = int(match.group(1))
            b_pts = int(match.group(2))
            points_found.append((a_pts, b_pts))
    
    if not points_found:
        return None
    
    # Seřadíme body od začátku (v textu jsou od konce)
    # Hledáme body, které se měnily (sekvence)
    points_found.reverse()
    
    sequence = []
    last_a, last_b = 0, 0
    for a, b in points_found:
        if a > last_a:
            sequence.append("A")
        elif b > last_b:
            sequence.append("B")
        last_a, last_b = a, b
        
    return {
        "A": player_a,
        "B": player_b,
        "score": f"{last_a}:{last_b}",
        "win": 1 if last_a > last_b else 0,
        "sequence": sequence
    }

# --- UI STREAMLIT ---
st.set_page_config(page_title="TT STAR SMART", layout="wide")
st.title("🏓 TT STAR - SMART ANALYZER v7")

tabs = st.tabs(["📥 Rychlé Vložení", "📊 Predikce", "🏆 Žebříček"])

with tabs[0]:
    st.subheader("📋 Vložit zkopírovaný text ze zápasu")
    raw_text = st.text_area("Sem vlož text z Tipsportu (včetně jmen a bodů):", height=300)
    
    if st.button("⚡ Analyzovat a uložit"):
        if raw_text:
            result = parse_live_text(raw_text)
            if result:
                st.write("### Nalezený výsledek:")
                st.write(f"Hráč A: **{result['A']}** | Hráč B: **{result['B']}**")
                st.write(f"Konečné skóre: {result['score']}")
                st.write(f"Počet bodů v sekvenci: {len(result['sequence'])}")
                
                # Uložení do databáze (každý set bereme jako záznam)
                st.session_state.data.append({
                    "A": result["A"],
                    "B": result["B"],
                    "sequence": result["sequence"],
                    "win": result["win"],
                    "timestamp": str(datetime.datetime.now())
                })
                save_data(st.session_state.data)
                st.success("Zápas úspěšně uložen do modelu!")
            else:
                st.error("Nepodařilo se rozpoznat skóre. Zkontroluj formát.")

with tabs[1]:
    # Tady zůstává tvůj kód pro predikci a Elo...
    st.info("Zde model používá data získaná z 'Rychlého vložení'.")
    # (Zde by pokračoval kód z předchozí verze pro Elo a Fair Kurz)

st.sidebar.write(f"V databázi je: {len(st.session_state.data)} setů")
