import streamlit as st
import json
import os
import re
import datetime
import math
import pandas as pd
import unicodedata

# --- CONFIG ---
DATA_FILE = "tt_star_ultra_v10.json"
BASE_R, BASE_RD = 1500, 350

st.set_page_config(page_title="TT STAR ANALYTIK", page_icon="🏓", layout="wide")

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)
    name = re.sub(r'[^A-Z\s]', '', name.upper())
    return name.strip()

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    st.session_state.data = json.load(open(DATA_FILE, "r")) if os.path.exists(DATA_FILE) else []

def get_ratings():
    ratings = {}
    for d in sorted(st.session_state.data, key=lambda x: str(x.get('timestamp', ''))):
        pA, pB, winA = d['A'], d['B'], d['win']
        if not pA or not pB: continue
        for p in [pA, pB]:
            if p not in ratings: ratings[p] = {"r": BASE_R, "rd": BASE_RD}
        rA, rdA, rB, rdB = ratings[pA]["r"], ratings[pA]["rd"], ratings[pB]["r"], ratings[pB]["rd"]
        q = math.log(10) / 400
        gB = 1 / math.sqrt(1 + 3 * (q * rdB / math.pi)**2)
        expA = 1 / (1 + 10**(gB * (rA - rB) / -400))
        dA = (q**2 * gB**2 * expA * (1 - expA))**-1
        ratings[pA]["r"] += (q / (1/rdA**2 + 1/dA)) * gB * (winA - expA)
        ratings[pA]["rd"] = max(30, math.sqrt(1 / (1/rdA**2 + 1/dA)))
        gA = 1 / math.sqrt(1 + 3 * (q * rdA / math.pi)**2)
        ratings[pB]["r"] += (q / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1)) * gA * ((1-winA) - (1-expA))
        ratings[pB]["rd"] = max(30, math.sqrt(1 / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1)))
    return ratings

# --- UI ---
t1, t2, t3, t4 = st.tabs(["📥 Vložit", "🔮 Predikce", "🏆 Žebříček", "⚙️ Správa"])

with t1:
    raw_in = st.text_area("Vložte text zápasu:", height=200, key="input_area")
    m_first = st.selectbox("Podával v 1. SETU?", ["Hráč 1", "Hráč 2"])
    if st.button("🚀 ULOŽIT"):
        if raw_in:
            try:
                dt_match = re.search(r'(\d+\.\s*\d+\.\s*\d+)\s*\|\s*(\d+:\d+)', raw_in)
                ts = f"{dt_match.group(1)} {dt_match.group(2)}" if dt_match else str(datetime.datetime.now().strftime("%d. %m. %Y | %H:%M"))
                lines = [l.strip() for l in raw_in.split('\n') if l.strip()]
                names = []
                for l in lines:
                    c_l = re.sub(r'[\d\t:|]+', '', l).strip()
                    if len(c_l) > 4 and "sety" not in c_l.lower(): names.append(normalize_name(c_l))
                p1_n, p2_n = names[0], names[1]
                nums = re.findall(r'\d+', raw_in)
                if dt_match: nums = nums[5:]
                pts = nums[2:]
                half = len(pts) // 2
                p1_p, p2_p = pts[:half], pts[half:]
                for i in range(len(p1_p)):
                    start = "A" if (m_first == "Hráč 1" and (i+1)%2 != 0) or (m_first == "Hráč 2" and (i+1)%2 == 0) else "B"
                    st.session_state.data.append({"A": p1_n, "B": p2_n, "score": f"{p1_p[i]}:{p2_p[i]}", "win": 1 if int(p1_p[i]) > int(p2_p[i]) else 0, "starter": start, "set_num": i+1, "timestamp": ts})
                save_data(st.session_state.data)
                st.success("Uloženo!")
                st.rerun()
            except: st.error("Chyba formátu! Zkontrolujte text.")

with t2:
    ratings = get_ratings()
    c1, c2 = st.columns(2)
    pA, pB = c1.text_input("Hráč A").upper(), c2.text_input("Hráč B").upper()
    col1, col2, col3 = st.columns(3)
    s_side = col1.radio("Podává:", ["Hráč A", "Hráč B"])
    kA, kO = col2.number_input("Kurz A", 1.01, 10.0, 1.85), col3.number_input("Kurz Over 18.5", 1.01, 10.0, 1.85)
    if pA and pB:
        rA, rB = ratings.get(pA, {"r":1500,"rd":350}), ratings.get(pB, {"r":1500,"rd":350})
        q = math.log(10)/400; gB = 1/math.sqrt(1+3*(q*rB["rd"]/math.pi)**2)
        probA = 1/(1+10**(gB*(rA["r"]-rB["r"])/-400))
        probA = min(max(probA + (0.05 if s_side == "Hráč A" else -0.05), 0.01), 0.99)
        st.metric(f"Šance {pA}", f"{round(probA*100,1)}%")
        if (probA*kA)-1 > 0: st.success(f"VALUE: +{round(((probA*kA)-1)*100,1)}% (Fair: {round(1/probA,2)})")
        sc = {"3:0": probA**3, "3:1": 3*probA**3*(1-probA), "3:2": 6*probA**3*(1-probA)**2, "0:3": (1-probA)**3, "1:3": 3*(1-probA)**3*probA, "2:3": 6*(1-probA)**3*probA**2}
        st.write("**Odhady:** " + " | ".join([f"{k}: {round(v*100,0)}%" for k, v in sc.items()]))

with t3:
    ratings = get_ratings()
    if ratings:
        df = pd.DataFrame([{"Hráč": k, "Glicko": int(v["r"]), "RD": int(v["rd"])} for k, v in ratings.items() if k.strip()])
        st.dataframe(df.sort_values("Glicko", ascending=False), use_container_width=True, hide_index=True)

with t4:
    st.subheader("⚙️ Správa historie")
    if st.session_state.data:
        for i, row in enumerate(st.session_state.data[::-1]):
            idx = len(st.session_state.data) - 1 - i
            with st.expander(f"{row['timestamp']} | {row['A']} vs {row['B']} | {row['score']}"):
                c1, c2, c3 = st.columns(3)
                new_A = c1.text_input("Hráč A", row['A'], key=f"editA_{idx}")
                new_B = c2.text_input("Hráč B", row['B'], key=f"editB_{idx}")
                new_S = c3.text_input("Skóre", row['score'], key=f"editS_{idx}")
                if st.button("Uložit změny", key=f"save_{idx}"):
                    st.session_state.data[idx]['A'] = new_A.upper()
                    st.session_state.data[idx]['B'] = new_B.upper()
                    st.session_state.data[idx]['score'] = new_S
                    st.session_state.data[idx]['win'] = 1 if int(new_S.split(':')[0]) > int(new_S.split(':')[1]) else 0
                    save_data(st.session_state.data); st.rerun()
                if st.button("Smazat zápas", key=f"del_{idx}"):
                    st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()
