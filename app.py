import streamlit as st
import json
import os
import re
import datetime
import math
import pandas as pd
import unicodedata

# --- 1. KONFIGURACE ---
DATA_FILE = "tt_star_ultra_v10.json"
BASE_R = 1500
BASE_RD = 350

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)
    return name.strip().upper()

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: st.session_state.data = json.load(f)
    else: st.session_state.data = []

# --- 2. GLICKO-2 LOGIKA ---
def get_glicko():
    ratings = {}
    for d in sorted(st.session_state.data, key=lambda x: x.get('timestamp', '')):
        pA, pB, winA = d['A'], d['B'], d['win']
        for p in [pA, pB]:
            if p not in ratings: ratings[p] = {"r": BASE_R, "rd": BASE_RD}
        
        rA, rdA = ratings[pA]["r"], ratings[pA]["rd"]
        rB, rdB = ratings[pB]["r"], ratings[pB]["rd"]
        q = math.log(10) / 400
        gB = 1 / math.sqrt(1 + 3 * (q * rdB / math.pi)**2)
        expA = 1 / (1 + 10**(gB * (rA - rB) / -400))
        dA = (q**2 * gB**2 * expA * (1 - expA))**-1
        ratings[pA]["r"] += (q / (1/rdA**2 + 1/dA)) * gB * (winA - expA)
        ratings[pA]["rd"] = math.sqrt(1 / (1/rdA**2 + 1/dA))
        
        gA = 1 / math.sqrt(1 + 3 * (q * rdA / math.pi)**2)
        expB = 1 - expA
        dB = (q**2 * gA**2 * expB * (1 - expB))**-1
        ratings[pB]["r"] += (q / (1/rdB**2 + 1/dB)) * gA * ((1-winA) - expB)
        ratings[pB]["rd"] = math.sqrt(1 / (1/rdB**2 + 1/dB))
    return ratings

# --- 3. PREDIKCE SKÓRE ZÁPASU ---
def predict_match_score(pWin):
    # pWin je pravděpodobnost výhry jednoho setu
    p30 = pWin**3
    p31 = 3 * (pWin**3) * (1-pWin)
    p32 = 6 * (pWin**3) * ((1-pWin)**2)
    p03 = (1-pWin)**3
    p13 = 3 * ((1-pWin)**3) * pWin
    p23 = 6 * ((1-pWin)**3) * (pWin**2)
    return {"3:0": p30, "3:1": p31, "3:2": p32, "0:3": p03, "1:3": p13, "2:3": p23}

# --- 4. UI ---
st.set_page_config(page_title="TT STAR v14.2", layout="wide")
st.title("🏓 TT STAR - FINÁLNÍ ANALYTIK")

t1, t2, t3, t4 = st.tabs(["📥 Vložit Zápas", "🔮 Predikce", "🏆 Žebříček", "⚙️ Možnosti"])

with t1:
    st.subheader("Hromadné vložení zápasu")
    raw_in = st.text_area("Vložte text zápasu:", height=150, placeholder="24. 4. 2026 | 8:00\nKoblížek Martin 3 11 6 11...")
    c1, c2 = st.columns(2)
    with c1: first_server = st.selectbox("Kdo začal podávat v 1. SETU?", ["Hráč 1 (Horní)", "Hráč 2 (Dolní)"])
    
    if st.button("🚀 ULOŽIT CELÝ ZÁPAS"):
        try:
            # Extrakce data a času
            dt_match = re.search(r'(\d+\.\s*\d+\.\s*\d+)\s*\|\s*(\d+:\d+)', raw_in)
            ts = f"{dt_match.group(1)} {dt_match.group(2)}" if dt_match else str(datetime.datetime.now())
            
            # Vyčištění jmen a bodů
            clean_text = re.sub(r'sety\d+', '', raw_in)
            lines = [l.strip() for l in clean_text.split('\n') if len(re.findall(r'\d+', l)) > 1]
            
            name1 = normalize_name(re.sub(r'\d+', '', lines[0]))
            name2 = normalize_name(re.sub(r'\d+', '', lines[1]))
            pts1 = re.findall(r'\d+', lines[0])[1:] # Přeskočíme celkový počet setů
            pts2 = re.findall(r'\d+', lines[1])[1:]
            
            for i in range(len(pts1)):
                set_n = i + 1
                starter = "A" if (first_server.startswith("Hráč 1") and set_n % 2 != 0) or (first_server.startswith("Hráč 2") and set_n % 2 == 0) else "B"
                st.session_state.data.append({
                    "A": name1, "B": name2, "score": f"{pts1[i]}:{pts2[i]}",
                    "win": 1 if int(pts1[i]) > int(pts2[i]) else 0,
                    "starter": starter, "set_num": set_n, "timestamp": ts
                })
            save_data(st.session_state.data)
            st.success("Zápas úspěšně uložen!"); st.rerun()
        except: st.error("Chyba! Zkontrolujte, zda text obsahuje jména a body.")

with t2:
    st.subheader("🔮 Predikce Glicko-2 & Kurzy")
    ratings = get_glicko()
    colA, colB = st.columns(2)
    with colA: pA = st.text_input("Hráč A").upper()
    with colB: pB = st.text_input("Hráč B").upper()
    
    c_k1, c_k2, c_k3 = st.columns(3)
    with c_k1: s_side = st.radio("Podává teď:", ["Hráč A", "Hráč B"])
    with c_k2: kA = st.number_input("Kurz na vítězství A", 1.01, 10.0, 1.85)
    with c_k3: kO = st.number_input("Kurz na Over 18.5", 1.01, 10.0, 1.85)

    if pA and pB:
        rA = ratings.get(pA, {"r": 1500, "rd": 350})
        rB = ratings.get(pB, {"r": 1500, "rd": 350})
        
        # Výpočet pravděpodobnosti setu
        q = math.log(10) / 400
        gB = 1 / math.sqrt(1 + 3 * (q * rB["rd"] / math.pi)**2)
        probA = 1 / (1 + 10**(gB * (rA["r"] - rB["r"]) / -400))
        probA = probA + 0.05 if s_side == "Hráč A" else probA - 0.05
        probA = min(max(probA, 0.01), 0.99)
        
        v1, v2 = st.columns(2)
        with v1:
            st.metric(f"Vítěz setu {pA}", f"{round(probA*100, 1)}%")
            valA = (probA * kA) - 1
            st.write(f"Fair: {round(1/probA, 2)}")
            if valA > 0: st.success(f"✅ VALUE: +{round(valA*100,1)}%")
            
            st.write("---")
            st.write("**Pravděpodobnost výsledku zápasu:**")
            scores = predict_match_score(probA)
            for s, p in scores.items():
                st.write(f"{s}: **{round(p*100, 1)}%**")
        
        with v2:
            probO = max(0.2, 0.85 - (abs(rA["r"] - rB["r"]) / 500))
            st.metric("Over 18.5 v setu", f"{round(probO*100, 1)}%")
            valO = (probO * kO) - 1
            if valO > 0: st.success(f"✅ VALUE OVER: +{round(valO*100,1)}%")

with t3:
    ratings = get_glicko()
    if ratings:
        df = pd.DataFrame([{"Hráč": k, "Glicko": int(v["r"]), "Spolehlivost (RD)": int(v["rd"])} for k, v in ratings.items()])
        st.dataframe(df.sort_values("Glicko", ascending=False), use_container_width=True)

with t4:
    st.download_button("📥 STÁHNOUT DATA", data=json.dumps(st.session_state.data), file_name="tt_data.json")
    up = st.file_uploader("📤 NAHRÁT ZÁLOHU", type="json")
    if up: st.session_state.data = json.load(up); save_data(st.session_state.data); st.rerun()
    if st.button("🗑️ SMAZAT VŠE"): st.session_state.data = []; save_data([]); st.rerun()
