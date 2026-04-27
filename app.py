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

# --- 2. LOGIKA PREDIKCE ---
def get_win_prob(eloA, eloB):
    return 1 / (1 + 10 ** ((eloB - eloA) / 400))

def predict_stats(eloA, eloB):
    pA_win_match = get_win_prob(eloA, eloB)
    pA_point = 0.5 + (pA_win_match - 0.5) * 0.2
    prob_over_18_5 = min(max((pA_point * (1-pA_point)) * 3.5, 0.3), 0.7)
    return {
        "probA": pA_win_match, "probB": 1 - pA_win_match,
        "over18_5": prob_over_18_5, "under18_5": 1 - prob_over_18_5,
        "expected_score": "11:9" if pA_win_match > 0.5 else "9:11"
    }

# --- 3. ROBUSTNÍ SMART PARSER v9.7 ---
def parse_live_text(text):
    # 1. Předčištění textu - odstranění balastu a milestonů
    lines = text.split('\n')
    filtered_lines = []
    forbidden = ["milestone-logo", "kurzy", "průběh", "nejsázenější", "statistiky", "moje tikety", "set", "začátek zápasu"]
    
    for l in lines:
        clean_l = l.strip()
        if not clean_l or any(f in clean_l.lower() for f in forbidden):
            continue
        if clean_l.lower().startswith("konec"): # Vynechá "Konec zápasu" i "Konec X. setu"
            continue
        filtered_lines.append(clean_l)

    if len(filtered_lines) < 2: return None

    # Jména jsou první dva validní řádky
    pA_name = normalize_name(filtered_lines[0])
    pB_name = normalize_name(filtered_lines[1])

    # 2. Slepování rozbitého skóre (číslo : číslo přes více řádků)
    full_text = " ".join(filtered_lines)
    # Odstraníme přebytečné mezery kolem dvojteček pro snadnější regex
    full_text = re.sub(r'\s*:\s*', ':', full_text)
    
    # Najdeme všechna skóre ve formátu ČÍSLO:ČÍSLO
    # Tento regex ignoruje skóre v závorkách (rekapitulace), pokud by tam zůstaly
    all_scores = re.findall(r'(\d+):(\d+)', full_text)
    
    if not all_scores: return None

    # Převedeme na čísla
    points = [(int(a), int(b)) for a, b in all_scores]

    # Tipsport řadí od nejnovějšího (11:9) k nejstaršímu (0:0) -> otočíme
    if (points[0][0] + points[0][1]) > (points[-1][0] + points[-1][1]):
        points.reverse()

    # 3. Logika unikátní sekvence bodů
    sequence, last_a, last_b, unique_points = [], 0, 0, []
    
    for a, b in points:
        # Ignorujeme stavy setů (např. 1:1, 2:1), které se pletou do cesty
        # Ve stolním tenise set končí 11 (nebo 10:10+). Malá skóre jako 1:1 uprostřed 
        # výpisu bodů jsou podezřelá, pokud následují po vysokých bodech.
        if unique_points:
            prev_sum = unique_points[-1][0] + unique_points[-1][1]
            curr_sum = a + b
            if curr_sum <= prev_sum and curr_sum < 4: # Pravděpodobně stav setů (např. 1:2)
                continue
        
        if not unique_points or (a, b) != unique_points[-1]:
            unique_points.append((a, b))

    for a, b in unique_points:
        if a > last_a: sequence.append("A")
        elif b > last_b: sequence.append("B")
        last_a, last_b = a, b

    # Detekce podání
    detected_starter = "A"
    if "první podání" in text.lower():
        serve_match = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text, re.IGNORECASE)
        if serve_match:
            found_name = normalize_name(serve_match.group(1))
            if found_name and (found_name in pB_name or pB_name in found_name):
                detected_starter = "B"

    return {
        "A": pA_name, "B": pB_name, 
        "score": f"{last_a}:{last_b}", 
        "win": 1 if last_a > last_b else 0, 
        "sequence": sequence, "starter": detected_starter
    }

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

# --- 4. UI STREAMLIT ---
st.set_page_config(page_title="TT STAR PREDICTOR v9.7", layout="wide")
st.title("🏓 TT STAR - VŠEUMĚL v9.7")

tabs = st.tabs(["📥 Vložit data", "🔮 PREDIKCE ZÁPASU", "🏆 Žebříček", "🗑️ Správa dat"])

with tabs[0]:
    st.subheader("📋 Rychlé vložení setu")
    st.write("Vložte data jednoho setu (včetně jmen a bodů).")
    raw_text = st.text_area("Vložte text z Tipsportu:", height=250)
    if st.button("🚀 Uložit do databáze"):
        if raw_text:
            result = parse_live_text(raw_text)
            if result and len(result["sequence"]) > 0:
                new_entry = {
                    "id": str(datetime.datetime.now().timestamp()), 
                    "A": result["A"], "B": result["B"], 
                    "sequence": result["sequence"], "starter": result["starter"], 
                    "win": result["win"], "score": result["score"], 
                    "timestamp": str(datetime.datetime.now())
                }
                st.session_state.data.append(new_entry)
                save_data(st.session_state.data)
                st.success(f"Uloženo: {result['A']} vs {result['B']} ({result['score']})")
            else:
                st.error("Chyba při čtení bodů. Ujistěte se, že kopírujete data pro jeden konkrétní set.")

with tabs[1]:
    st.subheader("🔮 Analýza a Predikce")
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
            st.write(f"Šance {tA}: {round(stats['probA']*100)}% | Šance {tB}: {round(stats['probB']*100)}%")
        with col_over:
            st.warning(f"🔢 Body v setu")
            st.write(f"VÍCE než 18.5: **{round(stats['over18_5']*100)}%**")
            st.write(f"Odhad skóre: **{stats['expected_score']}**")

with tabs[2]:
    st.subheader("🏆 Elo Žebříček")
    current_elos = calculate_elos()
    for r, (n, v) in enumerate(sorted(current_elos.items(), key=lambda x: x[1], reverse=True)):
        st.write(f"{r+1}. **{n}** — {int(v)} Elo")

with tabs[3]:
    st.subheader("📜 Historie")
    for i in range(len(st.session_state.data)-1, -1, -1):
        e = st.session_state.data[i]
        st.write(f"{e.get('A')} vs {e.get('B')} | {e.get('score')} | {e.get('timestamp')[:16]}")
        if st.button("Smazat", key=f"del_{i}"):
            st.session_state.data.pop(i)
            save_data(st.session_state.data)
            st.rerun()
