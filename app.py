import streamlit as st
import json, os, re, datetime, math, unicodedata
import pandas as pd

# --- CONFIG & INITIALIZATION ---
DATA_FILE = "tt_star_ultra_v17.json"
BASE_R, BASE_RD, BASE_VOL = 1500, 350, 0.06

st.set_page_config(page_title="TT STAR ANALYTIK v17", page_icon="🏓", layout="wide")

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name) # Odstraní J. z J.MARTINKO
    return re.sub(r'[^A-Z\s]', '', name.upper()).strip()

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    st.session_state.data = json.load(open(DATA_FILE, "r")) if os.path.exists(DATA_FILE) else []

# --- POKROČILÁ MATEMATIKA GLICKO-2 (S ČASOVOU VÁHOU A BODY) ---
def get_ratings():
    ratings = {}
    # Seřadíme data chronologicky
    sorted_data = sorted(st.session_state.data, key=lambda x: str(x.get('timestamp', '')))
    
    for d in sorted_data:
        pA, pB, score = d['A'], d['B'], d['score']
        if not pA or not pB: continue
        
        for p in [pA, pB]:
            if p not in ratings: 
                ratings[p] = {"r": BASE_R, "rd": BASE_RD, "vol": BASE_VOL, "count": 0, "last_ts": None}
        
        ptsA, ptsB = map(int, score.split(':'))
        # Suverenita výhry (bodový rozdíl ovlivňuje dopad na rating)
        margin = abs(ptsA - ptsB)
        win_weight = 1.0 + (min(margin, 9) / 20.0) 
        
        # Časová váha (velmi zjednodušeně: novější zápasy mírně zvyšují volatilitu)
        actual_winA = 1 if ptsA > ptsB else 0
        
        # Glicko-2 Update (zjednodušený model pro streamované zpracování)
        rA, rdA, rB, rdB = ratings[pA]["r"], ratings[pA]["rd"], ratings[pB]["r"], ratings[pB]["rd"]
        q = math.log(10) / 400
        gB = 1 / math.sqrt(1 + 3 * (q * rdB / math.pi)**2)
        expA = 1 / (1 + 10**(gB * (rA - rB) / -400))
        
        dA = (q**2 * gB**2 * expA * (1 - expA))**-1
        # Aplikace váhy suverenity
        changeA = (q / (1/rdA**2 + 1/dA)) * gB * (actual_winA - expA) * win_weight
        
        ratings[pA]["r"] += changeA
        ratings[pA]["rd"] = max(30, math.sqrt(1 / (1/rdA**2 + 1/dA)))
        ratings[pA]["count"] += 1
        
        # Update pro Hráče B
        gA = 1 / math.sqrt(1 + 3 * (q * rdA / math.pi)**2)
        changeB = (q / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1)) * gA * ((1-actual_winA) - (1-expA)) * win_weight
        ratings[pB]["r"] += changeB
        ratings[pB]["rd"] = max(30, math.sqrt(1 / (1/rdB**2 + (q**2 * gA**2 * expA * (1 - expA))**-1)))
        ratings[pB]["count"] += 1
        
    return ratings

# --- UI TABS ---
t1, t2, t3, t4 = st.tabs(["📥 Vložit Zápas", "🔮 Predikce & Value", "🏆 Žebříček", "⚙️ Historie & Správa"])

with t1:
    st.subheader("Vložit text ze screenshotu")
    raw_in = st.text_area("Vlož sem text od Gemini (např. Limonov Anton - Boccard Sam | 3:2 (12:10...) | Kurzy: 1.15, 4.34)", height=100)
    m_first = st.selectbox("Kdo podával v 1. SETU?", ["Hráč 1 (Horní)", "Hráč 2 (Dolní)"])
    
    if st.button("🚀 ULOŽIT VŠECHNY SETY"):
        try:
            # PARSER: Limonov Anton - Boccard Sam | 3:2 (12:10, 8:11) | Dnes 21:55 | Kurzy: 1.15, 4.34
            parts = raw_in.split('|')
            names = parts[0].split('-')
            p1_name = normalize_name(names[0])
            p2_name = normalize_name(names[1])
            
            # Najdeme body v závorkách
            sets_raw = re.search(r'\((.*?)\)', parts[1]).group(1)
            sets = [s.strip() for s in sets_raw.split(',')]
            
            # Najdeme kurzy
            odds_raw = re.findall(r'\d+\.\d+', parts[-1])
            o1, o2 = odds_raw[0], odds_raw[1] if len(odds_raw) >= 2 else ("0", "0")
            
            ts = parts[2].strip() if len(parts) > 2 else datetime.datetime.now().strftime("%d.%m. %H:%M")

            for i, s in enumerate(sets):
                # LOGIKA PODÁNÍ: Střídání po setu
                # Set 1, 3, 5 = m_first | Set 2, 4 = ten druhý
                if (i + 1) % 2 != 0:
                    current_starter = "A" if "Hráč 1" in m_first else "B"
                else:
                    current_starter = "B" if "Hráč 1" in m_first else "A"
                
                st.session_state.data.append({
                    "A": p1_name, "B": p2_name, "score": s,
                    "win": 1 if int(s.split(':')[0]) > int(s.split(':')[1]) else 0,
                    "starter": current_starter, "set_num": i+1, "timestamp": ts,
                    "odds": f"{o1}/{o2}"
                })
            save_data(st.session_state.data)
            st.success(f"Uloženo {len(sets)} setů pro {p1_name} vs {p2_name}")
            st.rerun()
        except Exception as e:
            st.error(f"Chyba parseru: Ujisti se, že vkládáš text přesně podle vzoru. ({e})")

with t2:
    ratings = get_ratings()
    c1, c2 = st.columns(2)
    selA = c1.selectbox("Hráč A (Horní)", sorted(list(ratings.keys()))) if ratings else c1.text_input("Jméno A")
    selB = c2.selectbox("Hráč B (Dolní)", sorted(list(ratings.keys()))) if ratings else c2.text_input("Jméno B")
    
    colA, colB, colC = st.columns(3)
    curr_odds_win = colA.number_input("Kurz na Výhru A", 1.01, 20.0, 1.85)
    curr_odds_over = colB.number_input("Kurz na Over 18.5", 1.01, 20.0, 1.85)
    live_server = colC.radio("Kdo podává PRÁVĚ TEĎ?", ["Hráč A", "Hráč B"])

    if selA and selB and selA != selB:
        rA, rB = ratings.get(selA, {"r":1500,"rd":350}), ratings.get(selB, {"r":1500,"rd":350})
        # Výpočet šancí
        q = math.log(10)/400; gB = 1/math.sqrt(1+3*(q*rB["rd"]/math.pi)**2)
        probA = 1/(1+10**(gB*(rA["r"]-rB["r"])/-400))
        # Live bonus za podání (cca 6% v ping-pongu)
        probA = min(max(probA + (0.06 if live_server == "Hráč A" else -0.06), 0.01), 0.99)
        
        st.metric(f"Pravděpodobnost {selA}", f"{round(probA*100,1)}%")
        if (probA * curr_odds_win) > 1.05: st.success(f"🔥 VALUE VÝHRA: +{round(((probA*curr_odds_win)-1)*100,1)}%")

        # Simulace bodů a Overu
        # 3:0, 3:1, 3:2 atd.
        sc = {"3:0": probA**3, "3:1": 3*probA**3*(1-probA), "3:2": 6*probA**3*(1-probA)**2, 
              "0:3": (1-probA)**3, "1:3": 3*(1-probA)**3*probA, "2:3": 6*(1-probA)**3*probA**2}
        pOver = (sc["3:1"]*0.7) + (sc["1:3"]*0.7) + sc["3:2"] + sc["2:3"]
        
        st.write(f"**Šance na Over 18.5 bodů:** {round(pOver*100,1)}%")
        if (pOver * curr_odds_over) > 1.05: st.success(f"🔥 VALUE OVER: +{round(((pOver*curr_odds_over)-1)*100,1)}%")
        
        st.write("**Odhad přesného bodového skóre v setu:**")
        exp_ptsA = 11 if probA > 0.5 else round(11 * (probA/0.5))
        exp_ptsB = 11 if probA < 0.5 else round(11 * ((1-probA)/0.5))
        st.info(f"Předpokládaný výsledek setu: {max(exp_ptsA, 0)} : {max(exp_ptsB, 0)}")

with t3:
    ratings = get_ratings()
    search = st.text_input("🔍 Hledat hráče v žebříčku")
    if ratings:
        df = pd.DataFrame([{"Hráč": k, "Rating": int(v["r"]), "RD": int(v["rd"]), "Zápasů": v["count"]} for k, v in ratings.items()])
        if search: df = df[df['Hráč'].str.contains(search.upper())]
        st.dataframe(df.sort_values("Rating", ascending=False), use_container_width=True, hide_index=True)

with t4:
    st.subheader("Správa historie")
    if st.session_state.data:
        # Export
        csv = pd.DataFrame(st.session_state.data).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 STÁHNOUT DATA (CSV pro Excel)", data=csv, file_name="tt_star_data.csv", mime="text/csv")
        
        if st.button("🗑️ SMAZAT CELOU DATABÁZI"):
            if st.checkbox("Potvrdit smazání všeho"): st.session_state.data = []; save_data([]); st.rerun()
            
        st.write("---")
        for i, row in enumerate(st.session_state.data[::-1]):
            idx = len(st.session_state.data) - 1 - i
            starter_name = row['A'] if row['starter'] == "A" else row['B']
            with st.expander(f"{row['timestamp']} | {row['A']} vs {row['B']} | {row['score']} | 🎾 Podával: {starter_name}"):
                c1, c2, c3 = st.columns(3)
                editA = c1.text_input("Hráč A", row['A'], key=f"eA{idx}")
                editB = c2.text_input("Hráč B", row['B'], key=f"eB{idx}")
                editS = c3.text_input("Skóre", row['score'], key=f"eS{idx}")
                editStart = st.selectbox("Podával:", [editA, editB], index=0 if row['starter']=="A" else 1, key=f"eSt{idx}")
                if st.button("Uložit změny", key=f"btn{idx}"):
                    st.session_state.data[idx].update({"A": editA.upper(), "B": editB.upper(), "score": editS, "starter": "A" if editStart == editA else "B"})
                    save_data(st.session_state.data); st.rerun()
                if st.button("Smazat set", key=f"del{idx}"):
                    st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()
