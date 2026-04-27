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
SERVE_ADVANTAGE = 0.04  # Zvýšeno na 4% pro reálnější vliv podání

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

# --- 2. LOGIKA PREDIKCE S VÁHOU PODÁNÍ ---
def get_win_prob(eloA, eloB):
    return 1 / (1 + 10 ** ((eloB - eloA) / 400))

def predict_stats(eloA, eloB, starter="A"):
    pA_win_match = get_win_prob(eloA, eloB)
    
    # Aplikace výhody podání do výpočtu pravděpodobnosti
    if starter == "A":
        pA_win_match += SERVE_ADVANTAGE
    else:
        pA_win_match -= SERVE_ADVANTAGE
    
    pA_win_match = min(max(pA_win_match, 0.02), 0.98)
    # Odhad pravděpodobnosti bodu
    pA_point = 0.5 + (pA_win_match - 0.5) * 0.15 
    
    prob_over_18_5 = min(max((pA_point * (1-pA_point)) * 3.8, 0.25), 0.75)

    return {
        "probA": pA_win_match, "probB": 1 - pA_win_match,
        "over18_5": prob_over_18_5, "under18_5": 1 - prob_over_18_5,
        "expected_score": "11:8" if pA_win_match > 0.55 else ("8:11" if pA_win_match < 0.45 else "11:9")
    }

# --- 3. SMART PARSER v9.9 (LOGIKA STŘÍDÁNÍ PODÁNÍ) ---
def parse_live_text(text):
    # Vyčištění řádků
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Detekce čísla setu z textu (např. "1. SET" nebo "Konec 2. setu")
    set_number = 1
    set_match = re.search(r'(\d+)\.\s*set', text, re.IGNORECASE)
    if set_match:
        set_number = int(set_match.group(1))

    # Základní filtrace balastu
    forbidden = ["milestone-logo", "kurzy", "průběh", "statistiky", "tikety", "vítěz", "začátek zápasu"]
    clean_lines = [l for l in lines if not any(f in l.lower() for f in forbidden) and not l.lower().startswith("konec")]

    if len(clean_lines) < 2: return None
    pA_name = normalize_name(clean_lines[0])
    pB_name = normalize_name(clean_lines[1])

    # Slepování skóre
    full_content = " ".join(clean_lines)
    full_content = re.sub(r'\s*:\s*', ':', full_content)
    all_scores = re.findall(r'(\d+):(\d+)', full_content)
    if not all_scores: return None

    points = [(int(a), int(b)) for a, b in all_scores]
    if (points[0][0] + points[0][1]) > (points[-1][0] + points[-1][1]):
        points.reverse()

    # --- LOGIKA PODÁNÍ ---
    detected_starter = None
    
    # 1. Zkusíme najít informaci přímo v textu (typicky jen 1. set)
    serve_info = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text, re.IGNORECASE)
    if serve_info:
        found_name = normalize_name(serve_info.group(1))
        detected_starter = "B" if (found_name in pB_name or pB_name in found_name) else "A"
    
    # 2. Pokud v textu info není, podíváme se do historie na tento zápas
    if not detected_starter:
        match_history = [d for d in st.session_state.data if (d['A'] == pA_name and d['B'] == pB_name)]
        if match_history:
            # Najdeme 1. set tohoto zápasu
            first_set = next((s for s in match_history if s.get('set_num') == 1), match_history[0])
            first_starter = first_set['starter']
            # Pravidlo střídání: Lichý set = stejný startér jako v 1. setu, Sudý set = opačný
            if set_number % 2 == 1:
                detected_starter = first_starter
            else:
                detected_starter = "B" if first_starter == "A" else "A"
        else:
            detected_starter = "A" # Default, pokud nemáme info

    # Rekonstrukce sekvence
    sequence, last_a, last_b, unique_points = [], 0, 0, []
    for a, b in points:
        if unique_points and (a + b) <= (unique_points[-1][0] + unique_points[-1][1]) and (a+b) < 3: continue
        if not unique_points or (a, b) != unique_points[-1]:
            unique_points.append((a, b))
    
    for a, b in unique_points:
        if a > last_a: sequence.append("A")
        elif b > last_b: sequence.append("B")
        last_a, last_b = a, b

    return {
        "A": pA_name, "B": pB_name, "score": f"{last_a}:{last_b}", 
        "win": 1 if last_a > last_b else 0, "sequence": sequence, 
        "starter": detected_starter, "set_num": set_number
    }

# --- 4. UI ---
st.set_page_config(page_title="TT STAR PREDICTOR v9.9", layout="wide")
st.title("🏓 TT STAR - VŠEUMĚL v9.9")

t1, t2, t3, t4 = st.tabs(["📥 Vložit data", "🔮 PREDIKCE", "🏆 Žebříček", "🗑️ Správa"])

with t1:
    raw_input = st.text_area("Vložte data setu (z Tipsportu):", height=200)
    if st.button("🚀 Analyzovat a uložit"):
        res = parse_live_text(raw_input)
        if res:
            new_entry = {
                "id": str(datetime.datetime.now().timestamp()),
                "A": res["A"], "B": res["B"], "score": res["score"],
                "win": res["win"], "sequence": res["sequence"],
                "starter": res["starter"], "set_num": res["set_num"],
                "timestamp": str(datetime.datetime.now())
            }
            st.session_state.data.append(new_entry)
            save_data(st.session_state.data)
            st.success(f"Uložen {res['set_num']}. SET: {res['A']} vs {res['B']} ({res['score']}). Začínal podávat: {res['starter']}")

with t2:
    st.subheader("🔮 Predikce s vlivem podání")
    elos = calculate_elos()
    c1, c2, c3 = st.columns(3)
    with c1: pA = st.text_input("Hráč A").upper()
    with c2: pB = st.text_input("Hráč B").upper()
    with c3:
        # Inteligentní předpověď podávajícího
        current_set_guess = 1
        relevant = [d for d in st.session_state.data if (d['A']==pA and d['B']==pB)]
        if relevant:
            current_set_guess = max([d.get('set_num', 0) for d in relevant]) + 1
        
        st.write(f"Předpokládaný set: {current_set_guess}.")
        # Výpočet kdo má podávat
        starter_guess = "A"
        if relevant:
            first_set = next((s for s in relevant if s.get('set_num') == 1), relevant[0])
            if current_set_guess % 2 == 0:
                starter_guess = "B" if first_set['starter'] == "A" else "A"
            else:
                starter_guess = first_set['starter']
        
        final_starter = st.radio("Kdo bude v tomto setu podávat?", ["A", "B"], index=0 if starter_guess=="A" else 1)

    if pA and pB:
        stats = predict_stats(elos.get(pA, BASE_ELO), elos.get(pB, BASE_ELO), final_starter)
        st.divider()
        col_a, col_b = st.columns(2)
        col_a.metric(f"Šance {pA}", f"{round(stats['probA']*100)}%")
        col_b.metric(f"Šance {pB}", f"{round(stats['probB']*100)}%")
        st.warning(f"Doporučení: Sázet na **{pA if stats['probA'] > stats['probB'] else pB}** při kurzu vyšším než {round(1/max(stats['probA'], stats['probB']), 2)}")

# --- Ostatní funkce (calculate_elos atd.) jsou shodné jako v předchozí verzi ---
