import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import math

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

# --- 2. VÝPOČTY S ANALÝZOU BODŮ ---
def calculate_elos():
    elos = {}
    for entry in st.session_state.data:
        pA, pB = entry.get("A"), entry.get("B")
        score = entry.get("score", "0:0")
        if not pA or not pB: continue
        
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        
        # Získání bodů ze skóre (např. 11:5)
        try:
            ptsA, ptsB = map(int, score.split(':'))
            point_diff = abs(ptsA - ptsB)
        except:
            point_diff = 2 # Defaultní minimální rozdíl
            
        exp_A = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        actual_A = entry.get("win", 0)
        
        # --- ANALÝZA BODŮ (MOV - Margin of Victory) ---
        # Násobitel, který zvětšuje váhu výsledku podle dominance (11:1 vs 12:10)
        # Logaritmus zajistí, že extrémní rozdíly (třeba 11:0) neshodí systém
        mov_multiplier = math.log(point_diff + 1) * (2.2 / ((actual_A - exp_A) * 0.001 + 2.2)) if actual_A != exp_A else 1
        
        shift = K_FACTOR * (actual_A - exp_A) * mov_multiplier
        elos[pA] += shift
        elos[pB] -= shift
    return elos

def predict_stats(eloA, eloB, starter="A"):
    pA_win = 1 / (1 + 10 ** ((eloB - eloA) / 400))
    pA_win = pA_win + SERVE_ADVANTAGE if starter == "A" else pA_win - SERVE_ADVANTAGE
    pA_win = min(max(pA_win, 0.02), 0.98)
    
    # Odhad pravděpodobnosti bodů pro Over/Under
    # Pokud jsou Elo u sebe, je vyšší šance na těsný výsledek (Over)
    elo_diff = abs(eloA - eloB)
    prob_over = max(0.2, 0.85 - (elo_diff / 600)) 
    
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
    if (pts[0][0] + pts[0][1]) > (pts[-1][0]
