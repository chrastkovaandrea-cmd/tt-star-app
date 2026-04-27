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
SERVE_ADVANTAGE = 0.04  # 4% bonus pro hráče, který začíná set podáním

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

# --- 2. LOGIKA VÝPOČTŮ ---
def calculate_elos():
    elos = {}
    for entry in st.session_state.data:
        pA, pB = entry.get("A"), entry.get("B")
        if not pA or not pB: continue
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        
        exp_A = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        actual_A = entry.get("win", 0)
        shift = K_FACTOR * (actual_A - exp_A)
        elos[pA] += shift
        elos[pB] -= shift
    return elos

def predict_stats(eloA, eloB, starter="A"):
    pA_win_match = 1 / (1 + 10 ** ((eloB - eloA) / 400))
    
    # Aplikace výhody podání
    if starter == "A":
        pA_win_match += SERVE_ADVANTAGE
    else:
        pA_win_match -= SERVE_ADVANTAGE
    
    pA_win_match = min(max(pA_win_match, 0.02), 0.98)
    pA_point = 0.5 + (pA_win_match - 0.5) * 0.15 
    prob_over_18_5 = min(max((pA_point * (1-pA_point)) * 3.8, 0.25), 0.75)

    return {
        "probA": pA_win_match, "probB": 1 - pA_win_match,
        "over18_5": prob_over_18_5, "under18_5": 1 - prob_over_18_5,
        "expected_score": "11:9" if pA_win_match > 0.5 else "9:11"
    }

# --- 3. SMART PARSER v9.9 ---
def parse_live_text(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Detekce čísla setu
    set_number = 1
    set_match = re.search(r'(\d+)\.\s*SET', text, re.IGNORECASE)
    if set_match:
        set_number = int(set_match.group(1))

    forbidden = ["milestone-logo", "kurzy", "průběh", "statistiky", "tikety", "vítěz", "začátek zápasu", "nejsázenější"]
    clean_lines = []
    for l in lines:
        if any(f in l.lower() for f in forbidden): continue
        if l.lower().startswith("konec"): continue
        if l in [".", ":"]: continue
        clean_lines.append(l)

    if len(clean_lines) < 2: return None
    pA_name = normalize_name(clean_lines[0])
    pB_name = normalize_name(clean_lines[1])

    # Slepování skóre a hledání bodů
    full_content = " ".join(clean_lines)
    full_content = re.sub(r'\s*:\s*', ':', full_content)
    all_scores = re.findall(r'(\d+):(\d+)', full_content)
    if not all_scores: return None

    points = [(int(a), int(b)) for a, b in all_scores]
    if (points[0][0] + points[0][1]) > (points[-1][0] + points[-1][1]):
        points.reverse()

    # Logika podání (hledání startéra)
    detected_starter = None
    serve_info = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text, re.IGNORECASE)
    if serve_info:
        found_name = normalize_name(serve_info.group(1))
        detected_starter = "B" if (found_name in pB_name or pB_name in found_name) else "A"
    
    # Automatické střídání podle historie zápasu
    if not detected_starter:
        match_history = [d for d in st.session_state.data if (d['A'] == pA_name and d['B'] == pB_name)]
        if match_history:
            first_set = next((s for s in match_history if s.get('set_num') == 1), match_history[0])
            first_starter = first_set['starter']
            detected_starter = first_starter if set_number % 2 == 1 else ("B" if first_starter == "A" else "A")
        else:
            detected_starter = "A"

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

# --- 4. UI STREAMLIT ---
st.set_page_config(page_title="TT STAR PREDICTOR v9.9", layout="wide")
st.title("🏓 TT STAR - VŠEUMĚL v9.9")

t1, t2, t3, t4 = st.tabs(["📥 Vložit data", "🔮 PREDIKCE", "🏆 Žebříček", "🗑️ Správa"])

with t1:
    st.subheader("📥 Vložení výsledků")
    raw_input = st.text_area("Vložte text z Tipsportu:", height=200)
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
            st.success(f"Uloženo! {res['set_num']}. set | Podával: {res['starter']}")

with t2:
    st.subheader("🔮 Predikce")
    current_elos = calculate_elos()
    c1, c2, c3 = st.columns(3)
    with c1: pA = st.text_input("Hráč A").upper()
    with c2: pB = st.text_input("Hráč B").upper()
    with c3:
        # Odhad podávajícího
        starter_guess = "A"
        relevant = [d for d in st.session_state.data if (d['A']==pA and d['B']==pB)]
        if relevant:
            next_set = max([d.get('set_num', 0) for d in relevant]) + 1
            first_s = next((s for s in relevant if s.get('set_num') == 1), relevant[0])
            if next_set % 2 == 0: starter_guess = "B" if first_s['starter'] == "A" else "A"
            else: starter_guess = first_s['starter']
        
        final_starter = st.radio("Kdo bude podávat?", ["A", "B"], index=0 if starter_guess=="A" else 1)

    if pA and pB:
        stats = predict_stats(current_elos.get(pA, BASE_ELO), current_elos.get(pB, BASE_ELO), final_starter)
        st.divider()
        col_res, col_odds = st.columns(2)
        with col_res:
            st.metric(f"Šance {pA}", f"{round(stats['probA']*100)}%")
            st.metric(f"Šance {pB}", f"{round(stats['probB']*100)}%")
        with col_odds:
            st.write(f"Fair kurz na vítěze: **{round(1/max(stats['probA'], 0.01), 2)}**")
            st.write(f"Pravděpodobnost Over 18.5: **{round(stats['over18_5']*100)}%**")

with t3:
    st.subheader("🏆 Žebříček")
    active_elos = calculate_elos()
    for r, (n, v) in enumerate(sorted(active_elos.items(), key=lambda x: x[1], reverse=True)):
        st.write(f"{r+1}. **{n}** — {int(v)} Elo")

with t4:
    st.subheader("🗑️ Historie")
    for i in range(len(st.session_state.data)-1, -1, -1):
        d = st.session_state.data[i]
        st.write(f"{d.get('A')} vs {d.get('B')} | {d.get('score')} | Set: {d.get('set_num')}")
        if st.button("Smazat", key=f"del_{i}"):
            st.session_state.data.pop(i)
            save_data(st.session_state.data)
            st.rerun()
