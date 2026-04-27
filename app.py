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
    # Odstraní iniciály typu A. Jméno nebo J. Jméno
    name = re.sub(r'^[A-Z][a-z]?\.\s*', '', name) 
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

# --- 2. VÝPOČTY ELO ---
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

# --- 3. SMART PARSER v10.7 ---
def parse_live_text(text):
    # Odstranění zbytečného balastu
    text = re.sub(r'milestone-logo|Domů|Kurzy|Live|Soutěže|Komunita|Analýzy|Statistiky|Tikety|Moje tikety|Vyloučit se', '', text, flags=re.IGNORECASE)
    
    # Slepování rozbitého skóre (řeší i extrémní mezery)
    text = re.sub(r'(\d+)\s*\n*\s*:\s*\n*\s*(\d+)', r'\1:\2', text)
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Detekce setu
    set_num = 1
    set_match = re.search(r'(\d+)\.\s*set', text, re.IGNORECASE)
    if set_match: set_num = int(set_match.group(1))

    # Detekce jmen (hledáme jména, která nejsou běžná slova)
    # Ignorujeme známé balastní řádky
    ignored = ["STOLNÍ TENIS", "VÝSLEDKY", "TIKETY", "KURZ", "PRŮBĚH", "NEJSÁZENĚJŠÍ", "DOBA PŘIHLÁŠENÍ", "VÍTĚZ"]
    potential_names = []
    for l in lines:
        if len(l) > 3 and not any(ig in l.upper() for ig in ignored) and not re.search(r'\d+:\d+', l):
            potential_names.append(normalize_name(l))
    
    if len(potential_names) < 2: return None
    # První dvě jména, která najdeme, jsou obvykle soupeři
    pA, pB = potential_names[0], potential_names[1]

    # Hledání skóre
    scores = re.findall(r'(\d+):(\d+)', text)
    if not scores: return None
    
    pts = [(int(a), int(b)) for a, b in scores]
    # Pokud první skóre v textu vypadá jako konečné (např. 11:6), 
    # a poslední jako začátek (1:0), otočíme seznam pro správnou sekvenci
    if (pts[0][0] + pts[0][1]) > (pts[-1][0] + pts[-1][1]):
        pts.reverse()

    # Logika podání
    starter = "A" # Default
    # 1. Hledáme v textu "první podání"
    serve_info = re.search(r'první podání\s+([A-ZÁ-Ž][a-zá-ž]+)', text, re.IGNORECASE)
    if serve_info:
        found = normalize_name(serve_info.group(1))
        if found in pB or pB in found: starter = "B"
    else:
        # 2. Pokud není v textu, zkusíme najít 1. set v historii a střídat
        relevant = [d for d in st.session_state.data if (d.get('A')==pA and d.get('B')==pB)]
        if relevant:
            f_set = next((s for s in sorted(relevant, key=lambda x: x.get('set_num', 1)) if s.get('set_num')==1), None)
            if f_set:
                f_starter = f_set['starter']
                # Sudý set = opačný startér než v 1. setu
                if set_num % 2 == 0: starter = "B" if f_starter == "A" else "A"
                else: starter = f_starter

    return {
        "A": pA, "B": pB, 
        "score": f"{pts[-1][0]}:{pts[-1][1]}", 
        "win": 1 if pts[-1][0] > pts[-1][1] else 0, 
        "starter": starter, "set_num": set_num
    }

# --- 4. UI ---
st.set_page_config(page_title="TT STAR v10.7", layout="wide")
st.title("🏓 TT STAR - VŠEUMĚL v10.7")

t1, t2, t3, t4 = st.tabs(["📥 Vložit Set", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie"])

with t1:
    raw_in = st.text_area("Sem vložte celý zkopírovaný text z Tipsportu:", height=250)
    res = parse_live_text(raw_in) if raw_in else None
    
    if res:
        st.success(f"✅ Detekován zápas: {res['A']} vs {res['B']}")
        st.info(f"Skóre setu: {res['score']} | Set číslo: {res['set_num']}")
        
        col1, col2 = st.columns(2)
        with col1:
            m_set = st.number_input("Potvrdit číslo setu:", 1, 5, value=res['set_num'])
        with col2:
            m_start = st.selectbox("Potvrdit podávajícího:", ["A", "B"], index=0 if res['starter']=="A" else 1)
            
        if st.button("💾 ULOŽIT DO HISTORIE"):
            new_e = {"id": str(datetime.datetime.now().timestamp()), "A": res["A"], "B": res["B"], "score": res["score"], "win": res["win"], "starter": m_start, "set_num": m_set, "timestamp": str(datetime.datetime.now())}
            st.session_state.data.append(new_e)
            save_data(st.session_state.data)
            st.rerun()
    elif raw_in:
        st.warning("⚠️ Nepodařilo se automaticky načíst všechna data. Zkuste zkopírovat text znovu včetně jmen hráčů.")

# --- PREDCE, ŽEBŘÍČEK A HISTORIE (Zůstávají stejné, plně funkční) ---
with t2:
    st.subheader("🔮 Predikce")
    elos = calculate_elos()
    # ... (zbytek kódu predikce jako v 10.6)
