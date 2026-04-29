import streamlit as st
import json, os, re, datetime, math, unicodedata
import pandas as pd

# --- CONFIG ---
DATA_FILE = "tt_star_data.json"
st.set_page_config(page_title="TT STAR v17.2", page_icon="🏓", layout="wide")

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'[^A-Z\s]', '', name.upper()).strip()
    return name.strip()

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f: st.session_state.data = json.load(f)
    else:
        st.session_state.data = []

# --- GLICKO-2 ---
def get_ratings():
    ratings = {}
    BASE_R, BASE_RD = 1500, 350
    for d in st.session_state.data:
        pA, pB, score = d['A'], d['B'], d['score']
        for p in [pA, pB]:
            if p not in ratings: ratings[p] = {"r": BASE_R, "rd": BASE_RD, "count": 0}
        ptsA, ptsB = map(int, score.split(':'))
        actual_winA = 1 if ptsA > ptsB else 0
        rA, rdA, rB, rdB = ratings[pA]["r"], ratings[pA]["rd"], ratings[pB]["r"], ratings[pB]["rd"]
        q = math.log(10)/400
        gB = 1/math.sqrt(1 + 3*(q*rdB/math.pi)**2)
        expA = 1/(1 + 10**(gB*(rA-rB)/-400))
        dA = (q**2 * gB**2 * expA * (1-expA))**-1
        ratings[pA]["r"] += (q/(1/rdA**2 + 1/dA)) * gB * (actual_winA - expA)
        ratings[pA]["rd"] = max(30, math.sqrt(1/(1/rdA**2 + 1/dA)))
        ratings[pA]["count"] += 1
        gA = 1/math.sqrt(1 + 3*(q*rdA/math.pi)**2)
        ratings[pB]["r"] += (q/(1/rdB**2 + (q**2 * gA**2 * expA * (1-expA))**-1)) * gA * ((1-actual_winA) - (1-expA))
        ratings[pB]["rd"] = max(30, math.sqrt(1/(1/rdB**2 + (q**2 * gA**2 * expA * (1-expA))**-1)))
        ratings[pB]["count"] += 1
    return ratings

# --- UI ---
t1, t2, t3, t4 = st.tabs(["📥 Vložit Zápas", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

with t1:
    raw_in = st.text_area("Vlož text od Gemini:", height=100)
    m_first = st.selectbox("Kdo podával v 1. SETU?", ["Hráč 1 (Horní)", "Hráč 2 (Dolní)"])
    if st.button("🚀 ULOŽIT ZÁPAS"):
        try:
            parts = raw_in.split('|')
            names = parts[0].split('-')
            p1, p2 = normalize_name(names[0]), normalize_name(names[1])
            sets = re.search(r'\((.*?)\)', parts[1]).group(1).split(',')
            for i, s in enumerate(sets):
                s = s.strip()
                starter = ("A" if "Hráč 1" in m_first else "B") if (i+1)%2 != 0 else ("B" if "Hráč 1" in m_first else "A")
                st.session_state.data.append({"A": p1, "B": p2, "score": s, "starter": starter, "timestamp": parts[2].strip() if len(parts)>2 else ""})
            save_data(st.session_state.data); st.success("Uloženo!"); st.rerun()
        except: st.error("Chyba formátu.")

with t2:
    ratings = get_ratings()
    if ratings:
        c1, c2 = st.columns(2)
        selA = c1.selectbox("Hráč A", sorted(ratings.keys()))
        selB = c2.selectbox("Hráč B", sorted(ratings.keys()))
        if selA != selB:
            rA, rB = ratings[selA]["r"], ratings[selB]["r"]
            probA = 1/(1 + 10**((rB-rA)/400))
            st.metric(f"Šance {selA}", f"{round(probA*100,1)}%")
            st.write(f"Odhad bodů: {11 if probA > 0.5 else round(11*(probA/0.5))} : {11 if probA < 0.5 else round(11*((1-probA)/0.5))}")

with t3:
    ratings = get_ratings()
    if ratings:
        df = pd.DataFrame([{"Hráč": k, "Rating": int(v["r"]), "Z": v["count"]} for k, v in ratings.items()])
        st.dataframe(df.sort_values("Rating", ascending=False), use_container_width=True, hide_index=True)

with t4:
    st.subheader("📦 Záloha dat")
    if st.session_state.data:
        csv = pd.DataFrame(st.session_state.data).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📤 STÁHNOUT ZÁLOHU (CSV)", data=csv, file_name="tt_star_backup.csv")
    
    up = st.file_uploader("📥 Nahrát zálohu (CSV)", type="csv")
    if up and st.button("✅ OBNOVIT DATA"):
        st.session_state.data = pd.read_csv(up).to_dict('records')
        save_data(st.session_state.data); st.rerun()
    
    if st.button("🗑️ SMAZAT VŠE"):
        st.session_state.data = []; save_data([]); st.rerun()
