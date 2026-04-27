import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import math # Potřeba pro výpočet dominance

# --- 1. NASTAVENÍ A DATA ---
DATA_FILE = "tt_star_ultra_v9.json" 
BASE_ELO = 1500
K_FACTOR = 32
SERVE_ADVANTAGE = 0.04

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

# --- 2. VÝPOČTY (AKTUALIZOVÁNO O BODY) ---
def calculate_elos():
    elos = {}
    for entry in st.session_state.data:
        pA, pB = entry.get("A"), entry.get("B")
        score = entry.get("score", "0:0")
        if not pA or not pB: continue
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        
        # Analýza dominance bodů
        try:
            sa, sb = map(int, score.split(':'))
            point_diff = abs(sa - sb)
        except:
            point_diff = 2
            
        exp_A = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        actual_A = entry.get("win", 0)
        
        # Násobitel dominance (MOV)
        mov_multiplier = math.log(point_diff + 1) * (2.2 / ((actual_A - exp_A) * 0.001 + 2.2)) if actual_A != exp_A else 1
        
        shift = K_FACTOR * (actual_A - exp_A) * mov_multiplier
        elos[pA] += shift
        elos[pB] -= shift
    return elos

def predict_stats(eloA, eloB, starter="A"):
    pA_win = 1 / (1 + 10 ** ((eloB - eloA) / 400))
    pA_win = pA_win + SERVE_ADVANTAGE if starter == "A" else pA_win - SERVE_ADVANTAGE
    pA_win = min(max(pA_win, 0.02), 0.98)
    
    # Over 18.5 založený na vyrovnanosti Elo
    elo_diff = abs(eloA - eloB)
    prob_over = max(0.25, 0.85 - (elo_diff / 500))
    
    return {"probA": pA_win, "probB": 1 - pA_win, "over18_5": prob_over}

# --- 3. PARSER ---
def parse_live_text(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    set_num = 1
    s_match = re.search(r'(\d+)\.\s*SET', text, re.IGNORECASE)
    if s_match: set_num = int(s_match.group(1))
    
    forbidden = ["milestone-logo", "kurzy", "průběh", "statistiky", "tikety", "začátek zápasu"]
    clean = [l for l in lines if not any(f in l.lower() for f in forbidden) and not l.lower().startswith("konec")]
    
    if len(clean) < 2: return None
    pA, pB = normalize_name(clean[0]), normalize_name(clean[1])
    
    full = re.sub(r'\s*:\s*', ':', " ".join(clean))
    scores = re.findall(r'(\d+):(\d+)', full)
    if not scores: return None
    pts = [(int(a), int(b)) for a, b in scores]
    if (pts[0][0] + pts[0][1]) > (pts[-1][0] + pts[-1][1]): pts.reverse()
    
    starter = "A"
    serve_info = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text, re.IGNORECASE)
    if serve_info:
        found = normalize_name(serve_info.group(1))
        starter = "B" if (found in pB or pB in found) else "A"
        
    return {"A": pA, "B": pB, "score": f"{pts[-1][0]}:{pts[-1][1]}", "win": 1 if pts[-1][0] > pts[-1][1] else 0, "starter": starter, "set_num": set_num}

# --- 4. UI ---
st.set_page_config(page_title="TT STAR v10.4", layout="wide")
st.title("🏓 TT STAR - VŠEUMĚL v10.4")

t1, t2, t3, t4 = st.tabs(["📥 Vložit", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie"])

with t1:
    raw_in = st.text_area("Vložte text z Tipsportu:", height=150)
    col_s1, col_s2 = st.columns(2)
    res = parse_live_text(raw_in) if raw_in else None
    
    with col_s1:
        manual_set = st.number_input("Číslo setu:", 1, 5, value=res['set_num'] if res else 1)
    with col_s2:
        manual_starter = st.selectbox("Kdo začal podávat?", ["A", "B"], index=0 if (res and res['starter']=="A") else 1)
        
    if st.button("🚀 Uložit set"):
        if res:
            new_e = {"id": str(datetime.datetime.now().timestamp()), "A": res["A"], "B": res["B"], "score": res["score"], "win": res["win"], "starter": manual_starter, "set_num": manual_set, "timestamp": str(datetime.datetime.now())}
            st.session_state.data.append(new_e)
            save_data(st.session_state.data)
            st.success(f"Uloženo: {res['A']} vs {res['B']}")

with t2:
    st.subheader("🔮 Predikce")
    elos = calculate_elos()
    c1, c2, c3 = st.columns(3)
    with c1: pA_in = st.text_input("Hráč A").upper()
    with c2: pB_in = st.text_input("Hráč B").upper()
    with c3:
        relevant = [d for d in st.session_state.data if (d.get('A')==pA_in and d.get('B')==pB_in) or (d.get('A')==pB_in and d.get('B')==pA_in)]
        suggested = "A"
        if relevant:
            last_s = sorted(relevant, key=lambda x: x.get('set_num', 1))[-1]
            next_s_num = last_s.get('set_num', 1) + 1
            f_set = next((s for s in sorted(relevant, key=lambda x: x.get('set_num', 1)) if s.get('set_num')==1), last_s)
            f_start = f_set.get('starter', "A")
            if f_set.get('A') != pA_in: f_start = "B" if f_start == "A" else "A"
            suggested = f_start if next_s_num % 2 == 1 else ("B" if f_start == "A" else "A")
        final_s = st.radio("Podává v tomto setu:", ["A", "B"], index=0 if suggested=="A" else 1)

    if pA_in and pB_in:
        s = predict_stats(elos.get(pA_in, BASE_ELO), elos.get(pB_in, BASE_ELO), final_s)
        st.write(f"Šance {pA_in}: **{round(s['probA']*100)}%** | Šance {pB_in}: **{round(s['probB']*100)}%**")
        st.write(f"Pravděpodobnost Over 18.5: **{round(s['over18_5']*100)}%**")

with t3:
    elostats = calculate_elos()
    for r, (n, v) in enumerate(sorted(elostats.items(), key=lambda x: x[1], reverse=True)):
        st.write(f"{r+1}. **{n}** — {int(v)}")

with t4:
    st.subheader("⚙️ Správa Historie")
    for i in range(len(st.session_state.data)-1, -1, -1):
        d = st.session_state.data[i]
        
        name_A, name_B = d.get('A', 'Neznámý'), d.get('B', 'Neznámý')
        score, s_num, starter = d.get('score', '0:0'), d.get('set_num', 1), d.get('starter', 'A')

        with st.expander(f"📝 {name_A} vs {name_B} ({score}) | Set: {s_num}"):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                edit_score = st.text_input("Upravit skóre", score, key=f"edit_sc_{i}")
                edit_starter = st.selectbox("Upravit podání", ["A", "B"], index=0 if starter=="A" else 1, key=f"edit_st_{i}")
            with col_e2:
                if st.button("💾 Uložit změny", key=f"save_btn_{i}"):
                    st.session_state.data[i]['score'] = edit_score
                    st.session_state.data[i]['starter'] = edit_starter
                    try:
                        sa, sb = map(int, edit_score.split(':'))
                        st.session_state.data[i]['win'] = 1 if sa > sb else 0
                    except: pass
                    save_data(st.session_state.data)
                    st.rerun()
                
                if st.button("🗑️ Smazat záznam", key=f"del_btn_{i}"):
                    st.session_state.data.pop(i)
                    save_data(st.session_state.data)
                    st.rerun()
