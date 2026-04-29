import streamlit as st
import json, os, re, datetime, math, unicodedata
import pandas as pd
from io import StringIO

# --- CONFIG & INITIALIZATION ---
DATA_FILE = "tt_star_ultra_v17.json"
BASE_R, BASE_RD, BASE_VOL = 1500, 350, 0.06

st.set_page_config(page_title="TT STAR ANALYTIK v17.1", page_icon="🏓", layout="wide")

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)
    return re.sub(r'[^A-Z\s]', '', name.upper()).strip()

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    st.session_state.data = json.load(open(DATA_FILE, "r")) if os.path.exists(DATA_FILE) else []

# --- POKROČILÁ MATEMATIKA GLICKO-2 ---
def get_ratings():
    ratings = {}
    sorted_data = sorted(st.session_state.data, key=lambda x: str(x.get('timestamp', '')))
    for d in sorted_data:
        pA, pB, score = d['A'], d['B'], d['score']
        if not pA or not pB: continue
        for p in [pA, pB]:
            if p not in ratings: ratings[p] = {"r": BASE_R, "rd": BASE_RD, "vol": BASE_VOL, "count": 0}
        ptsA, ptsB = map(int, score.split(':'))
        margin = abs(ptsA - ptsB)
        win_weight = 1.0 + (min(margin, 9) / 20.0) 
        actual_winA = 1 if ptsA > ptsB else 0
        rA, rdA, rB, rdB = ratings[pA]["r"], ratings[pA]["rd"], ratings[pB]["r"], ratings[pB]["rd"]
        q = math.log(10) / 400
        gB = 1 / math.sqrt(1 + 3 * (q * rdB / math.pi)**2)
        expA = 1 / (1 + 10**(gB * (rA - rB) / -400))
        dA = (q**2 * gB**2 * expA * (1 - expA))**-1
        ratings[pA]["r"] += (q / (1/rdA**2 + 1/dA)) * gB * (actual_winA - expA) * win_weight
        ratings[pA]["rd"] = max(30, math.sqrt(1 / (1/rdA**2 + 1/dA)))
        ratings[pA]["count"] += 1
        gA = 1 / math.sqrt(1 + 3 * (q * rdA / math.pi)**2)
        ratings[pB]["r"] += (q / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1)) * gA * ((1-actual_winA) - (1-expA)) * win_weight
        ratings[pB]["rd"] = max(30, math.sqrt(1 / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1)))
        ratings[pB]["count"] += 1
    return ratings

# --- UI TABS ---
t1, t2, t3, t4 = st.tabs(["📥 Vložit Zápas", "🔮 Predikce & Value", "🏆 Žebříček", "⚙️ Historie & Správa"])

with t1:
    raw_in = st.text_area("Vlož sem text od Gemini:", height=100)
    m_first = st.selectbox("Kdo podával v 1. SETU?", ["Hráč 1 (Horní)", "Hráč 2 (Dolní)"])
    if st.button("🚀 ULOŽIT VŠECHNY SETY"):
        try:
            parts = raw_in.split('|')
            names = parts[0].split('-')
            p1_name = normalize_name(names[0])
            p2_name = normalize_name(names[1])
            sets_raw = re.search(r'\((.*?)\)', parts[1]).group(1)
            sets = [s.strip() for s in sets_raw.split(',')]
            odds_raw = re.findall(r'\d+\.\d+', parts[-1])
            o1, o2 = odds_raw[0], odds_raw[1] if len(odds_raw) >= 2 else ("0", "0")
            ts = parts[2].strip() if len(parts) > 2 else datetime.datetime.now().strftime("%d.%m. %H:%M")
            for i, s in enumerate(sets):
                current_starter = ("A" if "Hráč 1" in m_first else "B") if (i+1)%2 != 0 else ("B" if "Hráč 1" in m_first else "A")
                st.session_state.data.append({"A": p1_name, "B": p2_name, "score": s, "win": 1 if int(s.split(':')[0]) > int(s.split(':')[1]) else 0, "starter": current_starter, "set_num": i+1, "timestamp": ts, "odds": f"{o1}/{o2}"})
            save_data(st.session_state.data); st.success("Uloženo!"); st.rerun()
        except: st.error("Chyba formátu.")

with t2:
    ratings = get_ratings()
    c1, c2 = st.columns(2)
    selA = c1.selectbox("Hráč A", sorted(list(ratings.keys()))) if ratings else c1.text_input("Jméno A")
    selB = c2.selectbox("Hráč B", sorted(list(ratings.keys()))) if ratings else c2.text_input("Jméno B")
    colA, colB, colC = st.columns(3)
    curr_odds_win = colA.number_input("Kurz A", 1.01, 20.0, 1.85); curr_odds_over = colB.number_input("Kurz Over 18.5", 1.01, 20.0, 1.85); live_server = colC.radio("Podává:", ["Hráč A", "Hráč B"])
    if selA and selB and selA != selB:
        rA, rB = ratings.get(selA, {"r":1500,"rd":350}), ratings.get(selB, {"r":1500,"rd":350})
        q = math.log(10)/400; gB = 1/math.sqrt(1+3*(q*rB["rd"]/math.pi)**2); probA = 1/(1+10**(gB*(rA["r"]-rB["r"])/-400))
        probA = min(max(probA + (0.06 if live_server == "Hráč A" else -0.06), 0.01), 0.99)
        st.metric(f"Šance {selA}", f"{round(probA*100,1)}%")
        if (probA * curr_odds_win) > 1.05: st.success(f"🔥 VALUE VÝHRA: +{round(((probA*curr_odds_win)-1)*100,1)}%")
        sc = {"3:0": probA**3, "3:1": 3*probA**3*(1-probA), "3:2": 6*probA**3*(1-probA)**2, "0:3": (1-probA)**3, "1:3": 3*(1-probA)**3*probA, "2:3": 6*(1-probA)**3*probA**2}
        pOver = (sc["3:1"]*0.7) + (sc["1:3"]*0.7) + sc["3:2"] + sc["2:3"]
        st.write(f"**Over 18.5:** {round(pOver*100,1)}%"); st.info(f"Odhad bodů: {11 if probA > 0.5 else round(11*(probA/0.5))} : {11 if probA < 0.5 else round(11*((1-probA)/0.5))}")

with t3:
    ratings = get_ratings(); search = st.text_input("🔍 Hledat")
    if ratings:
        df = pd.DataFrame([{"Hráč": k, "Rating": int(v["r"]), "RD": int(v["rd"]), "Z": v["count"]} for k, v in ratings.items()])
        if search: df = df[df['Hráč'].str.contains(search.upper())]
        st.dataframe(df.sort_values("Rating", ascending=False), use_container_width=True, hide_index=True)

with t4:
    st.subheader("📦 Záloha a Obnova")
    c1, c2 = st.columns(2)
    if st.session_state.data:
        csv = pd.DataFrame(st.session_state.data).to_csv(index=False).encode('utf-8-sig')
        c1.download_button("📤 STÁHNOUT ZÁLOHU (CSV)", data=csv, file_name="tt_star_backup.csv", mime="text/csv")
    
    uploaded_file = c2.file_uploader("📥 Nahrát soubor zálohy", type="csv")
    if uploaded_file is not None:
        if st.button("✅ OBNOVIT DATA ZE SOUBORU"):
            df_load = pd.read_csv(uploaded_file)
            st.session_state.data = df_load.to_dict('records')
            save_data(st.session_state.data); st.success("Data byla obnovena!"); st.rerun()

    st.write("---")
    for i, row in enumerate(st.session_state.data[::-1]):
        idx = len(st.session_state.data) - 1 - i
        with st.expander(f"{row['A']} vs {row['B']} | {row['score']} | 🎾 Podával: {row['A'] if row['starter']=='A' else row['B']}"):
            c1, c2, c3 = st.columns(3)
            editA = c1.text_input("Hráč A", row['A'], key=f"eA{idx}"); editB = c2.text_input("Hráč B", row['B'], key=f"eB{idx}"); editS = c3.text_input("Skóre", row['score'], key=f"eS{idx}")
            editStart = st.selectbox("Podával:", [editA, editB], index=0 if row['starter']=="A" else 1, key=f"eSt{idx}")
            if st.button("Uložit", key=f"btn{idx}"):
                st.session_state.data[idx].update({"A": editA.upper(), "B": editB.upper(), "score": editS, "starter": "A" if editStart == editA else "B"})
                save_data(st.session_state.data); st.rerun()
            if st.button("Smazat", key=f"del{idx}"): st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()
