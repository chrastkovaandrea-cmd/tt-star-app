import streamlit as st
import unicodedata
import json
import os
import requests
import re
from collections import Counter

# --- KONFIGURACE ---
DATA_FILE = "data.json"

def normalize_name(name):
    if not name: return ""
    name = name.strip()
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = " ".join(name.split())
    return name

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# Inicializace dat v session_state, aby se stránka pořád neresetovala
if 'data' not in st.session_state:
    st.session_state.data = load_data()

st.title("🏓 TT STAR PRO MODEL")

# --- OCR FUNKCE ---
def ocr_space(image_file):
    api_key = "helloworld"  # Doporučuji získat vlastní klíč na ocr.space
    payload = {
        "apikey": api_key,
        "language": "eng",
        "isOverlayRequired": False,
    }
    res = requests.post("https://api.ocr.space/parse/image",
                        files={"file": image_file},
                        data=payload)
    result = res.json()
    if result.get("ParsedResults"):
        return result["ParsedResults"][0]["ParsedText"]
    return ""

# --- PARSOVÁNÍ TIPSPORTU ---
def parse_tipsport(text):
    matches = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    for i in range(len(lines)):
        line = lines[i]
        if " - " in line:
            try:
                players = line.split("-")
                A = normalize_name(players[0])
                B = normalize_name(players[1])

                next_line = lines[i+1]
                set_match = re.search(r"(\d):(\d)", next_line)
                score_match = re.search(r"\((.*?)\)", next_line)

                odds_line = lines[i+2]
                odds = re.findall(r"\d+\.\d+", odds_line)

                if set_match and score_match and len(odds) >= 2:
                    matches.append({
                        "A": A, "B": B,
                        "sets": set_match.group(),
                        "scores": score_match.group(1),
                        "oddsA": float(odds[0]),
                        "oddsB": float(odds[1])
                    })
            except Exception:
                continue
    return matches

# --- UI: SCREENSHOT ---
st.subheader("📸 Upload Tipsport screenshot")
img_file = st.file_uploader("Upload image", type=["png", "jpg", "jpeg"])

if img_file:
    st.image(img_file, caption="Nahraný screenshot", width=300)
    if st.button("🔍 Analyzovat fotku"):
        with st.spinner("Čtu text z obrázku..."):
            detected_text = ocr_space(img_file)
            parsed_matches = parse_tipsport(detected_text)
            
            if parsed_matches:
                st.session_state.temp_matches = parsed_matches
                st.success(f"Nalezeno zápasů: {len(parsed_matches)}")
            else:
                st.error("Nepodařilo se rozpoznat žádné zápasy. Zkuste lepší kvalitu.")

if 'temp_matches' in st.session_state:
    for idx, m in enumerate(st.session_state.temp_matches):
        st.write(f"**{m['A']} vs {m['B']}** ({m['sets']})")
    
    if st.button("💾 Uložit vše do modelu"):
        for m in st.session_state.temp_matches:
            diff = abs(m["oddsA"] - m["oddsB"])
            for s in m["scores"].split(","):
                try:
                    a, b = s.strip().split(":")
                    st.session_state.data.append({
                        "A": m["A"], "B": m["B"],
                        "score": f"{a}:{b}",
                        "points": int(a) + int(b),
                        "diff": diff,
                        "sets": m["sets"],
                        "first_point": "A" if int(a) > 0 else "B", # Zjednodušená logika
                        "last_point": "A" if int(a) > int(b) else "B",
                        "parity": "even" if (int(a)+int(b)) % 2 == 0 else "odd"
                    })
                except: continue
        save_data(st.session_state.data)
        st.success("Data uložena!")
        del st.session_state.temp_matches

st.divider()

# --- UI: RUČNÍ PŘIDÁNÍ ---
st.subheader("📥 Add training match manually")
block = st.text_area("Vložte text (Hráč vs Hráč / Kurzy / Skóre):", 
                   "Novák vs Černý\n1.66 vs 1.89\n3:1\n11:9,10:12,11:8,11:7")

if st.button("Save manual match"):
    try:
        lines = block.strip().split("\n")
        A, B = lines[0].split("vs")
        oA, oB = lines[1].split("vs")
        sets = lines[2]
        scores = lines[3]

        diff = abs(float(oA) - float(oB))
        for s in scores.split(","):
            a, b = s.strip().split(":")
            st.session_state.data.append({
                "A": normalize_name(A), "B": normalize_name(B),
                "score": f"{a}:{b}", "points": int(a)+int(b),
                "diff": diff, "sets": sets,
                "first_point": "A" if int(a) > int(b) else "B", # Příklad logiky
                "last_point": "A" if int(a) > int(b) else "B",
                "parity": "even" if (int(a)+int(b))%2==0 else "odd"
            })
        save_data(st.session_state.data)
        st.success("Zápas uložen!")
    except Exception as e:
        st.error(f"Chyba formátu: {e}")

st.divider()

# --- UI: PREDIKCE ---
st.header("📊 Prediction Engine")
if len(st.session_state.data) < 5:
    st.info(f"Máš uloženo {len(st.session_state.data)} setů. Potřebuješ jich víc pro analýzu.")
else:
    col1, col2 = st.columns(2)
    with col1:
        pA_input = st.text_input("Hráč A")
        oA_input = st.number_input("Kurz A", value=1.8)
    with col2:
        pB_input = st.text_input("Hráč B")
        oB_input = st.number_input("Kurz B", value=1.8)

    if st.button("🔮 Spočítat predikci"):
        A_norm = normalize_name(pA_input)
        B_norm = normalize_name(pB_input)
        
        # Filtrování dat
        relevant = [x for x in st.session_state.data if x["A"] == A_norm or x["B"] == A_norm or x["A"] == B_norm or x["B"] == B_norm]
        
        if not relevant:
            st.warning("Tito hráči v databázi ještě nejsou. Používám globální data.")
            relevant = st.session_state.data

        scores = [x["score"] for x in relevant]
        counts = Counter(scores)
        total = sum(counts.values())

        st.subheader("Pravděpodobnosti setů")
        for s, c in counts.most_common(5):
            st.write(f"**{s}** : {round((c/total)*100, 1)}%")

        # Over / Under
        line = 18.5
        over = sum(1 for x in relevant if x["points"] > line) / len(relevant)
        st.metric("Over 18.5", f"{round(over*100, 1)}%")

st.sidebar.write(f"Databáze obsahuje: {len(st.session_state.data)} setů")
