import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import json, re, datetime, math, unicodedata

# --- CONFIG ---
st.set_page_config(page_title="TT STAR ANALYTIK v18.1 PRO", page_icon="🏓", layout="wide")

# Připojení ke Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)
    return re.sub(r'[^A-Z\s]', '', name.upper()).strip()

def load_data():
    try:
        # ttl=0 zajistí, že se data pokaždé načtou znovu z tabulky
        df = conn.read(worksheet="Data", ttl=0)
        return df.dropna(subset=['A']).to_dict('records')
    except:
        return []

def save_data(data_list):
    df = pd.DataFrame(data_list)
    conn.update(worksheet="Data", data=df)
    st.cache_data.clear()

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- GLICKO-2 S ČASOVOU VÁHOU A BODY ---
def get_ratings():
    ratings = {}
    BASE_R, BASE_RD = 1500, 350
    sorted_data = sorted(st.session_state.data, key=lambda x: str(x.get('timestamp', '')))
    for d in sorted_data:
        pA, pB, score = d['A'], d['B'], d['score']
        if not pA or not pB or ":" not in str(score): continue
        for p in [pA, pB]:
            if p not in ratings: ratings[p] = {"r": BASE_R, "rd": BASE_RD, "count": 0}
        
        try:
            ptsA, ptsB = map(int, str(score).split(':'))
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
        except: continue
    return ratings

# --- UI ---
t1, t2, t3, t4 = st.tabs(["📥 Vložit Zápas", "🔮 Predikce & Value", "🏆 Žebříček", "⚙️ Správa Historie"])

with t1:
    st.subheader("Nový zápas do Cloudu")
    raw_in = st.text_area("Vlož text od Gemini:", placeholder="Limonov - Boccard | 3:2 (12:10, 8:11...) | Kurzy: 1.15, 4.34")
    m_first = st.selectbox("Kdo podával v 1. SETU?", ["Hráč 1 (Horní)", "Hráč 2 (Dolní)"])
    if st.button("🚀 ULOŽIT DO TABULKY"):
        try:
            parts = raw_in.split('|')
            names = parts[0].split('-')
            p1_name, p2_name = normalize_name(names[0]), normalize_name(names[1])
            sets_raw = re.search(r'\((.*?)\)', parts[1]).group(1)
            sets = [s.strip() for s in sets_raw.split(',')]
            odds_raw = re.findall(r'\d+\.\d+', parts[-1])
            o1, o2 = odds_raw[0], odds_raw[1] if len(odds_raw) >= 2 else ("0", "0")
            ts = parts[2].strip() if len(parts) > 2 else datetime.datetime.now().strftime("%d.%m. %H:%M")
            
            for i, s in enumerate(sets):
                current_starter = ("A" if "Hráč 1" in m_first else "B") if (i+1)%2 != 0 else ("B" if "Hráč 1" in m_first else "A")
                st.session_state.data.append({"A": p1_name, "B": p2_name, "score": s, "win": 1 if int(s.split(':')[0]) > int(s.split(':')[1]) else 0, "starter": current_starter, "set_num": i+1, "timestamp": ts, "odds": f"{o1}/{o2}"})
            save_data(st.session_state.data)
            st.success("Synchronizováno s Google Sheets!"); st.rerun()
        except: st.error("Chyba formátu.")

with t2:
    ratings = get_ratings()
    c1, c2 = st.columns(2)
    selA = c1.selectbox("Hráč A", sorted(list(ratings.keys()))) if ratings else c1.text_input("Hráč A")
    selB = c2.selectbox("Hráč B", sorted(list(ratings.keys()))) if ratings else c2.text_input("Hráč B")
    colA, colB, colC = st.columns(3)
    kWin = colA.number_input("Kurz Výhra A", 1.01, 20.0, 1.85)
    kOver = colB.number_input("Kurz Over 18.5", 1.01, 20.0, 1.85)
    live_s = colC.radio("Podává:", ["Hráč A", "Hráč B"])
    
    if selA and selB and selA != selB:
        rA, rB = ratings.get(selA, {"r":1500,"rd":350}), ratings.get(selB, {"r":1500,"rd":350})
        q = math.log(10)/400; gB = 1/math.sqrt(1+3*(q*rB["rd"]/math.pi)**2); probA = 1/(1+10**(gB*(rA["r"]-rB["r"])/-400))
        probA = min(max(probA + (0.06 if live_s == "Hráč A" else -0.06), 0.01), 0.99)
        st.metric(f"Šance {selA}", f"{round(probA*100,1)}%")
        if (probA * kWin) > 1.05: st.success(f"🔥 VALUE VÝHRA: +{round(((probA*kWin)-1)*100,1)}%")
        sc = {"3:0": probA**3, "3:1": 3*probA**3*(1-probA), "3:2": 6*probA**3*(1-probA)**2, "0:3": (1-probA)**3, "1:3": 3*(1-probA)**3*probA, "2:3": 6*(1-probA)**3*probA**2}
        pOver = (sc["3:1"]*0.7) + (sc["1:3"]*0.7) + sc["3:2"] + sc["2:3"]
        st.write(f"**Over 18.5:** {round(pOver*100,1)}%")
        if (pOver * kOver) > 1.05: st.success(f"🔥 VALUE OVER: +{round(((pOver*kOver)-1)*100,1)}%")
        st.info(f"Odhad bodů: {11 if probA > 0.5 else round(11*(probA/0.5))} : {11 if probA < 0.5 else round(11*((1-probA)/0.5))}")

with t3:
    ratings = get_ratings(); search = st.text_input("🔍 Hledat")
    if ratings:
        df = pd.DataFrame([{"Hráč": k, "Rating": int(v["r"]), "RD": int(v["rd"]), "Z": v["count"]} for k, v in ratings.items()])
        if search: df = df[df['Hráč'].str.contains(search.upper())]
        st.dataframe(df.sort_values("Rating", ascending=False), use_container_width=True, hide_index=True)

with t4:
    st.subheader("📦 Cloudová Správa")
    if st.button("🔄 REFRESH Z TABULKY"):
        st.session_state.data = load_data(); st.rerun()
    
    up = st.file_uploader("Nahrát CSV zálohu do Cloudu", type="csv")
    if up and st.button("⬆️ POTVRDIT NAHRÁNÍ"):
        st.session_state.data = pd.read_csv(up).to_dict('records')
        save_data(st.session_state.data); st.success("Nahráno do Google Sheets!"); st.rerun()

    st.write("---")
    # Zobrazení historie s možností EDITACE
    for i, row in enumerate(st.session_state.data[::-1]):
        idx = len(st.session_state.data) - 1 - i
        with st.expander(f"{row['A']} vs {row['B']} | {row['score']} | 🎾 Podával: {row['A'] if row['starter']=='A' else row['B']}"):
            c1, c2, c3 = st.columns(3)
            eA = c1.text_input("A", row['A'], key=f"a{idx}"); eB = c2.text_input("B", row['B'], key=f"b{idx}"); eS = c3.text_input("Score", row['score'], key=f"s{idx}")
            eSt = st.selectbox("Podával:", [eA, eB], index=0 if row['starter']=="A" else 1, key=f"st{idx}")
            if st.button("Uložit změny", key=f"save{idx}"):
                st.session_state.data[idx].update({"A": eA.upper(), "B": eB.upper(), "score": eS, "starter": "A" if eSt == eA else "B"})
                save_data(st.session_state.data); st.rerun()
            if st.button("Smazat", key=f"del{idx}"):
                st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()
