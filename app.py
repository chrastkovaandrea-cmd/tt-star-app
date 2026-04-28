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
BASE_R, BASE_RD = 1500, 350

st.set_page_config(page_title="TT STAR ANALYTIK", page_icon="🏓", layout="wide")

# --- 2. POMOCNÉ FUNKCE ---
def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)
    return name.strip().upper()

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    st.session_state.data = json.load(open(DATA_FILE, "r")) if os.path.exists(DATA_FILE) else []

def get_glicko():
    ratings = {}
    for d in sorted(st.session_state.data, key=lambda x: x.get('timestamp', '')):
        pA, pB, winA = d['A'], d['B'], d['win']
        for p in [pA, pB]:
            if p not in ratings: ratings[p] = {"r": BASE_R, "rd": BASE_RD}
        rA, rdA, rB, rdB = ratings[pA]["r"], ratings[pA]["rd"], ratings[pB]["r"], ratings[pB]["rd"]
        q = math.log(10) / 400
        gB = 1 / math.sqrt(1 + 3 * (q * rdB / math.pi)**2)
        expA = 1 / (1 + 10**(gB * (rA - rB) / -400))
        dA = (q**2 * gB**2 * expA * (1 - expA))**-1
        ratings[pA]["r"] += (q / (1/rdA**2 + 1/dA)) * gB * (winA - expA)
        ratings[pA]["rd"] = math.sqrt(1 / (1/rdA**2 + 1/dA))
        gA = 1 / math.sqrt(1 + 3 * (q * rdA / math.pi)**2)
        ratings[pB]["r"] += (q / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1)) * gA * ((1-winA) - (1-expA))
        ratings[pB]["rd"] = math.sqrt(1 / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1))
    return ratings

# --- 3. UI APLIKACE ---
t1, t2, t3, t4 = st.tabs(["📥 Vložit Zápas", "🔮 Predikce & Kurzy", "🏆 Žebříček", "⚙️ Správa"])

with t1:
    st.subheader("Hromadné vložení (Tipsport formát)")
    raw_in = st.text_area("Vložte text zápasu:", height=250, placeholder="24. 4. 2026 | 8:00\nsety\n1...")
    m_first = st.selectbox("Kdo podával v 1. SETU?", ["Hráč 1 (Horní v textu)", "Hráč 2 (Dolní v textu)"])
    
    if st.button("🚀 ULOŽIT ZÁPAS"):
        try:
            dt_match = re.search(r'(\d+\.\s*\d+\.\s*\d+)\s*\|\s*(\d+:\d+)', raw_in)
            ts = f"{dt_match.group(1)} {dt_match.group(2)}" if dt_match else str(datetime.datetime.now())
            
            lines = [l.strip() for l in raw_in.split('\n') if l.strip()]
            names = []
            for l in lines:
                clean_l = re.sub(r'[\d\t:|]+', '', l).strip()
                if len(clean_l) > 5 and "sety" not in clean_l.lower():
                    names.append(normalize_name(clean_l))
            
            p1_name, p2_name = names[0], names[1]
            all_numbers = re.findall(r'\d+', raw_in)
            if dt_match: all_numbers = all_numbers[5:]
            
            points = all_numbers[2:]
            half = len(points) // 2
            p1_pts = points[:half]
            p2_pts = points[half:]
            
            for i in range(len(p1_pts)):
                set_n = i + 1
                starter = "A" if (m_first.startswith("Hráč 1") and set_n % 2 != 0) or (m_first.startswith("Hráč 2") and set_n % 2 == 0) else "B"
                st.session_state.data.append({
                    "A": p1_name, "B": p2_name, "score": f"{p1_pts[i]}:{p2_pts[i]}",
                    "win": 1 if int(p1_pts[i]) > int(p2_pts[i]) else 0,
                    "starter": starter, "set_num": set_n, "timestamp": ts
                })
            save_data(st.session_state.data); st.success(f"Uloženo: {p1_name} vs {p2_name}"); st.rerun()
        except: st.error("Chyba formátu! Zkontrolujte, zda jste vložila správný text.")

with t2:
    st.subheader("🔮 Glicko-2 & Sázky")
    ratings = get_glicko()
    c1, c2 = st.columns(2)
    pA = c1.text_input("Hráč A").upper()
    pB = c2.text_input("Hráč B").upper()
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    s_side = col1.radio("Aktuálně podává v setu:", ["Hráč A", "Hráč B"])
    kA = col2.number_input("Kurz na vítězství A", 1.01, 10.0, 1.85)
    kO = col3.number_input("Kurz na Over 18.5", 1.01, 10.0, 1.85)

    if pA and pB:
        rA = ratings.get(pA, {"r": 1500, "rd": 350})
        rB = ratings.get(pB, {"r": 1500, "rd": 350})
        q = math.log(10) / 400
        gB = 1 / math.sqrt(1 + 3 * (q * rB["rd"] / math.pi)**2)
        probA = 1 / (1 + 10**(gB * (rA["r"] - rB["r"]) / -400))
        probA = min(max(probA + (0.05 if s_side == "Hráč A" else -0.05), 0.01), 0.99)
        
        v_l, v_r = st.columns(2)
        with v_l:
            st.metric(f"Šance {pA}", f"{round(probA*100, 1)}%")
            valA = (probA * kA) - 1
            st.write(f"Fair kurz: **{round(1/probA, 2)}**")
            if valA > 0: st.success(f"✅ VALUE: +{round(valA*100,1)}%")
            
            st.write("---")
            st.write("**Odhady výsledku zápasu:**")
            sc = {"3:0": probA**3, "3:1": 3*probA**3*(1-probA), "3:2": 6*probA**3*(1-probA)**2,
                  "0:3": (1-probA)**3, "1:3": 3*(1-probA)**3*probA, "2:3": 6*(1-probA)**3*probA**2}
            for k, v in sc.items(): st.write(f"{k} — {round(v*100,1)}%")

        with v_r:
            probO = max(0.2, 0.85 - (abs(rA["r"] - rB["r"]) / 500))
            st.metric("Pravděpodobnost Over 18.5", f"{round(probO*100, 1)}%")
            if (probO * kO) - 1 > 0: st.success("✅ VALUE NA OVER")

with t3:
    ratings = get_glicko()
    if ratings:
        df = pd.DataFrame([{"Hráč": k, "Glicko": int(v["r"]), "RD": int(v["rd"])} for k, v in ratings.items()])
        st.dataframe(df.sort_values("Glicko", ascending=False), use_container_width=True)

with t4:
    st.download_button("📥 STÁHNOUT ZÁLOHU", data=json.dumps(st.session_state.data), file_name="tt_data.json")
    up = st.file_uploader("📤 NAHRÁT ZÁLOHU", type="json")
    if up: st.session_state.data = json.load(up); save_data(st.session_state.data); st.rerun()
