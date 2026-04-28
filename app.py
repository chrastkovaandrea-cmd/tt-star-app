import streamlit as st
import json, os, re, datetime, math, unicodedata
import pandas as pd

# --- CONFIG ---
DATA_FILE = "tt_star_ultra_v10.json"
BASE_R, BASE_RD = 1500, 350

st.set_page_config(page_title="TT STAR ANALYTIK PRO", page_icon="🏓", layout="wide")

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)
    return re.sub(r'[^A-Z\s]', '', name.upper()).strip()

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
            if p not in ratings: ratings[p] = {"r": BASE_R, "rd": BASE_RD, "count": 0}
        rA, rdA, rB, rdB = ratings[pA]["r"], ratings[pA]["rd"], ratings[pB]["r"], ratings[pB]["rd"]
        q = math.log(10) / 400
        gB = 1 / math.sqrt(1 + 3 * (q * rdB / math.pi)**2)
        expA = 1 / (1 + 10**(gB * (rA - rB) / -400))
        dA = (q**2 * gB**2 * expA * (1 - expA))**-1
        ratings[pA]["r"] += (q / (1/rdA**2 + 1/dA)) * gB * (winA - expA)
        ratings[pA]["rd"] = max(30, math.sqrt(1 / (1/rdA**2 + (q**2 * gB**2 * expA * (1 - expA))**-1)))
        ratings[pA]["count"] += 1
        gA = 1 / math.sqrt(1 + 3 * (q * rdA / math.pi)**2)
        ratings[pB]["r"] += (q / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1)) * gA * ((1-winA) - (1-expA))
        ratings[pB]["rd"] = max(30, math.sqrt(1 / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1)))
        ratings[pB]["count"] += 1
    return ratings

t1, t2, t3, t4 = st.tabs(["📥 Vkládání", "🔮 Predikce & Live", "🏆 Žebříček", "⚙️ Správa & Export"])

with t1:
    raw_in = st.text_area("Vložte text zápasu (jména a body):", height=150)
    m_first = st.selectbox("Kdo podával v 1. SETU?", ["Hráč 1 (Horní)", "Hráč 2 (Dolní)"])
    if st.button("🚀 ULOŽIT"):
        try:
            lines = [l.strip() for l in raw_in.split('\n') if l.strip() and "|" not in l]
            p_data = []
            for l in lines:
                nums = re.findall(r'\d+', l); name = re.sub(r'[\d\t:|]+', '', l).strip()
                if name and nums: p_data.append({"name": normalize_name(name), "pts": nums})
            if len(p_data) >= 2:
                p1, p2 = p_data[0], p_data[1]
                for i in range(min(len(p1["pts"]), len(p2["pts"]))):
                    start = "A" if (m_first.startswith("Hráč 1") and (i+1)%2 != 0) or (m_first.startswith("Hráč 2") and (i+1)%2 == 0) else "B"
                    st.session_state.data.append({"A": p1["name"], "B": p2["name"], "score": f"{p1['pts'][i]}:{p2['pts'][i]}", "win": 1 if int(p1['pts'][i]) > int(p2['pts'][i]) else 0, "starter": start, "set_num": i+1, "timestamp": datetime.datetime.now().strftime("%d.%m. %H:%M")})
                save_data(st.session_state.data); st.success("Uloženo!"); st.rerun()
        except: st.error("Chyba formátu.")

with t2:
    ratings = get_ratings()
    pA = st.selectbox("Hráč A", sorted(list(ratings.keys()))) if ratings else st.text_input("Hráč A")
    pB = st.selectbox("Hráč B", sorted(list(ratings.keys()))) if ratings else st.text_input("Hráč B")
    s_side = st.radio("Kdo podává?", ["Hráč A", "Hráč B"])
    kO = st.number_input("Kurz Over 18.5", 1.01, 10.0, 1.85)
    
    if pA and pB and pA != pB:
        rA, rB = ratings.get(pA, {"r":1500,"rd":350}), ratings.get(pB, {"r":1500,"rd":350})
        q = math.log(10)/400; gB = 1/math.sqrt(1+3*(q*rB["rd"]/math.pi)**2)
        probA = 1/(1+10**(gB*(rA["r"]-rB["r"])/-400))
        probA = min(max(probA + (0.05 if s_side == "Hráč A" else -0.05), 0.01), 0.99)
        sc = {"3:0": probA**3, "3:1": 3*probA**3*(1-probA), "3:2": 6*probA**3*(1-probA)**2, "0:3": (1-probA)**3, "1:3": 3*(1-probA)**3*probA, "2:3": 6*(1-probA)**3*probA**2}
        pOver = (sc["3:1"]*0.65) + (sc["1:3"]*0.65) + sc["3:2"] + sc["2:3"]
        st.metric(f"Šance {pA}", f"{round(probA*100,1)}%")
        st.write(f"**Over 18.5:** {round(pOver*100,1)}% " + (f"✅ VALUE" if (pOver*kO)>1 else ""))

with t3:
    ratings = get_ratings()
    search = st.text_input("🔍 Hledat")
    if ratings:
        df = pd.DataFrame([{"Hráč": k, "Glicko": int(v["r"]), "RD": int(v["rd"]), "Z": v["count"]} for k, v in ratings.items()])
        if search: df = df[df['Hráč'].str.contains(search.upper())]
        st.dataframe(df.sort_values("Glicko", ascending=False), use_container_width=True, hide_index=True)

with t4:
    if st.session_state.data:
        csv = pd.DataFrame(st.session_state.data).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 STÁHNOUT DATA (CSV pro Excel)", data=csv, file_name="tt_star_data.csv", mime="text/csv")
        if st.button("🗑️ SMAZAT VŠE"):
            if st.checkbox("Opravdu?"): st.session_state.data = []; save_data([]); st.rerun()
    st.write("---")
    for i, row in enumerate(st.session_state.data[::-1]):
        idx = len(st.session_state.data) - 1 - i
        with st.expander(f"{row['A']} vs {row['B']} ({row['score']})"):
            if st.button("Smazat", key=f"d{idx}"): st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()
