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
SERVE_ADVANTAGE = 0.04

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[.\s]+', '', name)
    name = re.sub(r'^[A-Z][a-z]?\.\s*', '', name) 
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
    # Ochrana: Nikdy neukládat, pokud jsou data prázdná a v session_state něco bylo
    if not data and st.session_state.get('data'):
        return
    with open(DATA_FILE, "w") as f: 
        json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- 2. VÝPOČTY ---
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

# --- 3. PARSER (Slepuje i rozházené skóre) ---
def parse_live_text(text):
    text = re.sub(r'milestone-logo|Domů|Kurzy|Live|Soutěže|Komunita|Analýzy|Statistiky|Tikety', '', text, flags=re.IGNORECASE)
    # Slepí rozházené skóre 11 : 6
    text = re.sub(r'(\d+)\s*\n*\s*[:]\s*\n*\s*(\d+)', r'\1:\2', text)
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    set_num = 1
    s_match = re.search(r'(\d+)\.\s*set', text, re.IGNORECASE)
    if s_match: set_num = int(s_match.group(1))

    potential_names = []
    ignored = ["STOLNÍ TENIS", "VÝSLEDKY", "TIKETY", "KURZ", "PRŮBĚH", "DOBA PŘIHLÁŠENÍ"]
    for l in lines:
        if len(l) > 3 and not any(ig in l.upper() for ig in ignored) and not re.search(r'\d+:\d+', l):
            potential_names.append(normalize_name(l))
    
    if len(potential_names) < 2: return None
    pA, pB = potential_names[0], potential_names[1]

    scores = re.findall(r'(\d+):(\d+)', text)
    if not scores: return None
    pts = [(int(a), int(b)) for a, b in scores]
    if (pts[0][0] + pts[0][1]) > (pts[-1][0] + pts[-1][1]): pts.reverse()

    starter = "A"
    serve_info = re.search(r'první podání\s+([A-ZÁ-Ž][a-zá-ž]+)', text, re.IGNORECASE)
    if serve_info:
        found = normalize_name(serve_info.group(1))
        if found in pB or pB in found: starter = "B"
    else:
        # Dopočet střídání podle historie
        relevant = [d for d in st.session_state.data if (d.get('A')==pA and d.get('B')==pB)]
        if relevant:
            f_set = next((s for s in sorted(relevant, key=lambda x: x.get('set_num', 1)) if s.get('set_num')==1), None)
            if f_set:
                f_st = f_set.get('starter', 'A')
                starter = f_st if set_num % 2 != 0 else ("B" if f_st == "A" else "A")

    return {"A": pA, "B": pB, "score": f"{pts[-1][0]}:{pts[-1][1]}", "win": 1 if pts[-1][0] > pts[-1][1] else 0, "starter": starter, "set_num": set_num}

# --- 4. UI ---
st.set_page_config(page_title="TT STAR v10.8", layout="wide")
st.title("🏓 TT STAR - VŠEUMĚL v10.8")

t1, t2, t3, t4 = st.tabs(["📥 Vložit", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie"])

with t1:
    raw_in = st.text_area("Vložte text z Tipsportu:", height=200)
    res = parse_live_text(raw_in) if raw_in else None
    if res:
        st.success(f"✅ {res['A']} vs {res['B']}")
        c1, c2 = st.columns(2)
        with c1: m_set = st.number_input("Set:", 1, 5, value=res['set_num'])
        with c2: m_start = st.selectbox("Podával:", ["A", "B"], index=0 if res['starter']=="A" else 1)
        if st.button("🚀 ULOŽIT ZÁPIS"):
            new_e = {"id": str(datetime.datetime.now().timestamp()), "A": res["A"], "B": res["B"], "score": res["score"], "win": res["win"], "starter": m_start, "set_num": m_set}
            st.session_state.data.append(new_e)
            save_data(st.session_state.data)
            st.rerun()

with t2:
    st.subheader("🔮 Predikce")
    current_elos = calculate_elos()
    pA_p = st.text_input("Hráč A").upper()
    pB_p = st.text_input("Hráč B").upper()
    if pA_p and pB_p:
        # Tady model využívá váhu podání
        starter_p = st.radio("Kdo začíná podávat v tomto setu?", ["A", "B"])
        pA_win = 1 / (1 + 10 ** ((current_elos.get(pB_p, 1500) - current_elos.get(pA_p, 1500)) / 400))
        pA_win = pA_win + SERVE_ADVANTAGE if starter_p == "A" else pA_win - SERVE_ADVANTAGE
        st.metric(f"Šance {pA_p}", f"{round(pA_win*100)}%")
        st.metric(f"Šance {pB_p}", f"{round((1-pA_win)*100)}%")

with t3:
    elostats = calculate_elos()
    for r, (n, v) in enumerate(sorted(elostats.items(), key=lambda x: x[1], reverse=True)):
        st.write(f"{r+1}. **{n}** — {int(v)} Elo")

with t4:
    st.subheader("⚙️ Správa a Úpravy")
    for i in range(len(st.session_state.data)-1, -1, -1):
        d = st.session_state.data[i]
        with st.expander(f"📝 {d.get('A')} vs {d.get('B')} (Set {d.get('set_num')})"):
            ed_sc = st.text_input("Skóre", d.get('score'), key=f"sc_{i}")
            ed_set = st.number_input("Set", 1, 5, value=d.get('set_num'), key=f"set_{i}")
            ed_st = st.selectbox("Podával",
