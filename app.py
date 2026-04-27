import streamlit as st
import unicodedata
import json
import os
import requests
import re
import numpy as np
from collections import Counter

# --- 1. ZÁKLADNÍ NASTAVENÍ A FUNKCE ---
DATA_FILE = "data.json"

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return " ".join(name.strip().split())

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- 2. MONTE CARLO SIMULACE (Nové!) ---
def monte_carlo_set_simulation(p_win_point, current_score=(0,0), iterations=2000):
    a_wins = 0
    simulated_scores = []
    for _ in range(iterations):
        s_a, s_b = current_score
        while True:
            if np.random.rand() < p_win_point: s_a += 1
            else: s_b += 1
            if (s_a >= 11 or s_b >= 11) and abs(s_a - s_b) >= 2: break
        simulated_scores.append(f"{s_a}:{s_b}")
        if s_a > s_b: a_wins += 1
    return a_wins / iterations, Counter(simulated_scores)

# --- 3. OCR A PARSOVÁNÍ ---
def ocr_space(image_file):
    payload = {"apikey": "helloworld", "language": "eng"}
    res = requests.post("https://api.ocr.space/parse/image", files={"file": image_file}, data=payload)
    result = res.json()
    return result["ParsedResults"][0]["ParsedText"] if result.get("ParsedResults") else ""

def auto_parse_tipsport(text):
    # Vylepšený regex pro automatické hledání zápasů
    pattern = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s?-\s?([A-Z][a-z]+(?:\s[A-Z][a-z]+)*).+?(\d:\d)\s?\(([\d:, ]+)\)"
    found = re.findall(pattern, text, re.DOTALL)
    matches = []
    for f in found:
        matches.append({"A": normalize_name(f[0]), "B": normalize_name(f[1]), "sets": f[2], "scores": f[3]})
    return matches

# --- 4. UI STREAMLIT ---
st.title("🏓 TT STAR PRO MODEL v2.0")

tabs = st.tabs(["📸 Nahrát data", "📊 Predikce", "⚡ Live Betting"])

# TAB 1: Nahrávání
with tabs[0]:
    img_file = st.file_uploader("Nahrát Tipsport screenshot", type=["png", "jpg", "jpeg"])
    if img_file:
        if st.button("🔍 Automaticky analyzovat"):
            text = ocr_space(img_file)
            parsed = auto_parse_tipsport(text)
            if parsed:
                st.session_state.temp_matches = parsed
                st.success(f"Nalezeno {len(parsed)} zápasů!")
            else: st.error("Nic nenalezeno. Zkus jiný screenshot.")
    
    if 'temp_matches' in st.session_state:
        for m in st.session_state.temp_matches:
            st.write(f"Zápas: {m['A']} - {m['B']} ({m['sets']})")
        if st.button("💾 Uložit vše do databáze"):
            for m in st.session_state.temp_matches:
                for s in m["scores"].split(","):
                    try:
                        a, b = s.strip().split(":")
                        st.session_state.data.append({
                            "A": m["A"], "B": m["B"], "score": f"{a}:{b}",
                            "points": int(a)+int(b), "win": 1 if int(a)>int(b) else 0
                        })
                    except: pass
            save_data(st.session_state.data)
            st.success("Uloženo!")

# TAB 2: Predikce před zápasem
with tabs[1]:
    st.subheader("Modelová predikce")
    pA = st.text_input("Hráč A (Jméno)")
    pB = st.text_input("Hráč B (Jméno)")
    
    if pA and pB:
        # Výpočet síly hráče z dat
        history = [x for x in st.session_state.data if x["A"] == normalize_name(pA) or x["B"] == normalize_name(pA)]
        if len(history) > 0:
            win_rate = sum([1 for x in history if x["win"] == 1]) / len(history)
            st.info(f"Historická úspěšnost setů {pA}: {round(win_rate*100, 1)}%")
            # Odhad pravděpodobnosti bodu (zjednodušeně)
            p_point = 0.45 + (win_rate * 0.1) 
        else:
            p_point = 0.50
            st.warning("Hráč nenalezen, používám neutrální kurz 50/50")

        win_p, scores = monte_carlo_set_simulation(p_point)
        st.metric("Šance na výhru setu", f"{round(win_p*100, 1)}%")

# TAB 3: LIVE BETTING
with tabs[2]:
    st.subheader("Point-by-Point simulace")
    l_a = st.number_input("Aktuální body A", value=0)
    l_b = st.number_input("Aktuální body B", value=0)
    strength = st.slider("Relativní síla A vs B", 0.40, 0.60, 0.50, 0.01)
    
    if st.button("🔮 Vypočítat Live šance"):
        win_p, scores = monte_carlo_set_simulation(strength, (l_a, l_b))
        st.write(f"### Aktuální šance na zisk setu: {round(win_p*100, 1)}%")
        
        st.write("**Pravděpodobné výsledky:**")
        for s, c in scores.most_common(3):
            st.write(f"{s} (šance {round((c/2000)*100, 1)}%)")

st.sidebar.write(f"Celkem setů v modelu: {len(st.session_state.data)}")
