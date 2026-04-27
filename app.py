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
    # Odstraní diakritiku, převede na velké a smaže iniciály (Mi.Beneš -> BENES)
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
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

# --- 2. SMART PARSER v9.1 (S automatickou detekcí směru a podání) ---
def parse_live_text(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) < 2: return None

    # Jména hráčů (první dva řádky)
    pA_name = normalize_name(lines[0])
    pB_name = normalize_name(lines[1])

    # Detekce podání z textu (např. "první podání Mi.Beneš")
    detected_starter = "A" # Default
    serve_match = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text)
    if serve_match:
        found_name = normalize_name(serve_match.group(1))
        # Pokud se nalezené jméno u podání shoduje s Hráčem B
        if found_name in pB_name or pB_name in found_name:
            detected_starter = "B"
        else:
            detected_starter = "A"

    # Extrakce bodů (hledá X : Y)
    all_scores = re.findall(r'(\d+)\s*:\s*(\d+)', text)
    if not all_scores: return None

    points = [(int(a), int(b)) for a, b in all_scores]

    # --- INTELIGENTNÍ DETEKCE SMĚRU ---
    # Podíváme se na první a poslední nalezené skóre, abychom věděli, jestli se kopírovalo od konce
    first_p = points[0]
    last_p = points[-1]
    
    # Pokud má první skóre vyšší součet než poslední, jde to od konce -> otočíme chronologicky
    if (first_p[0] + first_p[1]) > (last_p[0] + last_p[1]):
        points.reverse()

    # Rekonstrukce sekvence bod po bodu
    sequence = []
    last_a, last_b = 0, 0
    unique_points = []
    
    for p in points:
        # Odstranění duplicit (pokud je skóre v textu víckrát pod sebou)
        if not unique_points or p != unique_points[-1]:
            # Ochrana: Ignorujeme "setové" stavy jako 1:1, pokud už jsme uprostřed bodové série
            if len(unique_points) > 0:
                current_sum = p[0] + p[1]
                last_sum = unique_points[-1][0] + unique_points[-1][1]
                if current_sum < last_sum:
                    continue # Přeskočíme nesmyslně malé skóre (pravděpodobně stav setů)
            
            unique_points.append(p)

    # Převod skóre na sekvenci (A/B)
    for a, b in unique_points:
        if a > last_a: 
            sequence.append("A")
        elif b > last_b: 
            sequence.append("B")
        last_a, last_b = a, b

    return {
        "A": pA_name, 
        "B": pB_name, 
        "score": f"{last_a}:{last_b}", 
        "win": 1 if last_a > last_b else 0, 
        "sequence": sequence,
        "starter": detected_starter
    }

def calculate_elos():
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

# --- 3. UI ---
st.set_page_config(page_title="TT STAR ULTRA v9.1", layout="wide")
st.title("🏓 TT STAR - AUTOMATIC ANALYZER v9.1")

tabs = st.tabs(["📥 Vložit data", "📊 Analýza", "🏆 Žebříček"])

with tabs[0]:
    st.subheader("📋 Vložení textu (Tipsport / Live)")
    st.info("Nyní můžete kopírovat text shora dolů i zdola nahoru. Model si pořadí bodů sám srovná.")
    
    raw_text = st.text_area("Vložte text zápasu sem:", height=300)
    
    if st.button("🚀 Analyzovat a Uložit set"):
        if raw_text:
            result = parse_live_text(raw_text)
            if result and len(result['sequence']) > 0:
                new_entry = {
                    "A": result["A"], "B": result["B"],
                    "sequence": result["sequence"],
                    "starter": result["starter"],
                    "win": result["win"],
                    "timestamp": str(datetime.datetime.now())
                }
                st.session_state.data.append(new_entry)
                save_data(st.session_state.data)
                
                st.success(f"✅ Set úspěšně uložen! {result['A']} vs {result['B']} ({result['score']})")
                st.write(f"ℹ️ První podání (detekováno): **Hráč {result['starter']}**")
                st.code(f"Sekvence bodů: {''.join(result['sequence'])}")
                st.balloons()
            else:
                st.error("❌ Nepodařilo se rozpoznat data. Zkontrolujte, zda jste zkopírovali jména i body.")

with tabs[1]:
    st.subheader("🔎 Hledání Value Betu")
    elos = calculate_elos()
    c1, c2 = st.columns(2)
    with c1:
        target_A = st.text_input("Hráč A").upper()
        odds_A = st.number_input("Kurz sázkovky na Hráče A", value=2.0, step=0.01)
    with c2:
        target_B = st.text_input("Hráč B").upper()
    
    if target_A and target_B:
        eA = elos.get(target_A, BASE_ELO)
        eB = elos.get(target_B, BASE_ELO)
        prob_A = 1 / (1 + 10 ** ((eB - eA) / 400))
        fair_odds = 1 / prob_A
        st.write(f"### Elo Rating: {int(eA)} vs {int(eB)}")
        st.metric("Fair Kurz (Dle historie)", round(fair_odds, 2))
        
        edge = (odds_A / fair_odds) - 1
        if edge > 0.05: 
            st.success(f"🔥 VALUE BET ZJIŠTĚN: +{round(edge*100, 1)}% na {target_A}")
        else: 
            st.warning(f"Edge: {round(edge*100, 1)}% (Sázka nemá hodnotu)")

with tabs[2]:
    st.subheader("🏆 Aktuální Elo Žebříček")
    current_elos = calculate_elos()
    if current_elos:
        # Seřazení hráčů podle Elo bodů od nejvyššího
        sorted_ranking = sorted(current_elos.items(), key=lambda x: x[1], reverse=True)
        for r, (n, v) in enumerate(sorted_ranking):
            st.write(f"{r+1}. **{n}** — {int(v)} Elo bodů")
    else:
        st.info("V databázi zatím nejsou žádná data.")

st.sidebar.write(f"Sety v paměti: {len(st.session_state.data)}")
