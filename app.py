import streamlit as st
import json, os, re, datetime, math, unicodedata
import pandas as pd

# --- KONFIGURACE ---
DATA_FILE = "tt_star_ultra_v17.json"
st.set_page_config(page_title="TT STAR ANALYTIK PRO", page_icon="🏓", layout="wide")

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)
    return re.sub(r'[^A-Z\s]', '', name.upper()).strip()

def save_data(data):
    with open(DATA_FILE, "w") as f: 
        json.dump(data, f, indent=4)
    st.cache_data.clear() # Vymaže mezipaměť, aby se po uložení vše hned přepočítalo

if 'data' not in st.session_state:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: st.session_state.data = json.load(f)
        except: st.session_state.data = []
    else:
        st.session_state.data = []

# --- CHYTŘEJŠÍ GLICKO-2 MATEMATIKA S CACHE ---
@st.cache_data(show_spinner="Aktualizuji ratingy...")
def get_ratings(data_list):
    ratings = {}
    BASE_R, BASE_RD, BASE_VOL = 1500, 350, 0.06
    if not data_list: return {}
    
    sorted_data = sorted(data_list, key=lambda x: str(x.get('timestamp', '')))
    q = math.log(10) / 400
    
    for d in sorted_data:
        pA, pB, score = d['A'], d['B'], d['score']
        if not pA or not pB or ":" not in str(score): continue
        
        for p in [pA, pB]:
            if p not in ratings: 
                ratings[p] = {"r": BASE_R, "rd": BASE_RD, "vol": BASE_VOL, "count": 0}
        
        try:
            ptsA, ptsB = map(int, str(score).split(':'))
            margin = abs(ptsA - ptsB)
            # Bodová marže ovlivňuje váhu růstu ratingu
            win_weight = 1.0 + (min(margin, 9) / 20.0) 
            actual_winA = 1 if ptsA > ptsB else 0
            
            rA, rdA = ratings[pA]["r"], ratings[pA]["rd"]
            rB, rdB = ratings[pB]["r"], ratings[pB]["rd"]
            
            gB = 1 / math.sqrt(1 + 3 * (q * rdB / math.pi)**2)
            expA = 1 / (1 + 10**(gB * (rA - rB) / -400))
            dA_inv = q**2 * gB**2 * expA * (1 - expA)
            
            ratings[pA]["r"] += (q / (1/rdA**2 + dA_inv)) * gB * (actual_winA - expA) * win_weight
            ratings[pA]["rd"] = max(30, math.sqrt(1 / (1/rdA**2 + dA_inv)))
            ratings[pA]["count"] += 1
            
            gA = 1 / math.sqrt(1 + 3 * (q * rdA / math.pi)**2)
            dB_inv = q**2 * gA**2 * expA * (1 - expA)
            
            ratings[pB]["r"] += (q / (1/rdB**2 + dB_inv)) * gA * ((1-actual_winA) - (1-expA)) * win_weight
            ratings[pB]["rd"] = max(30, math.sqrt(1 / (1/rdB**2 + dB_inv)))
            ratings[pB]["count"] += 1
        except: continue
    return ratings

# --- HLAVNÍ ROZHRANÍ ---
t1, t2, t3, t4 = st.tabs(["📥 Vkládání", "🔮 Predikce", "🏆 Žebříček", "⚙️ Správa"])

with t1:
    if "input_val" not in st.session_state: st.session_state.input_val = ""
    def clear_input():
        st.session_state.input_val = ""
        if "txt_area" in st.session_state: st.session_state.txt_area = ""

    raw_in = st.text_area("Vlož text zápasu:", value=st.session_state.input_val, height=100, key="txt_area")
    c_del, _ = st.columns([1, 4])
    c_del.button("🗑️ Smazat text", on_click=clear_input)

    m_first = st.selectbox("Kdo podával v 1. SETU?", ["Hráč 1 (Horní)", "Hráč 2 (Dolní)"])
    
    if st.button("🚀 ULOŽIT ZÁPAS"):
        current_input = st.session_state.txt_area
        if current_input:
            try:
                parts = current_input.split('|')
                names = parts[0].split('-')
                p1_n, p2_n = normalize_name(names[0]), normalize_name(names[1])
                sets_raw = re.search(r'\((.*?)\)', parts[1]).group(1)
                sets = [s.strip() for s in sets_raw.split(',')]
                odds_raw = re.findall(r'\d+\.\d+', parts[-1])
                o1, o2 = (odds_raw[0], odds_raw[1]) if len(odds_raw) >= 2 else ("0", "0")
                ts = parts[2].strip() if len(parts) > 2 else datetime.datetime.now().strftime("%d.%m. %H:%M")
                
                temp_new_sets = []
                skip_count = 0
                # Super rychlá kontrola duplicit
                existing_keys = {f"{d['A']}{d['B']}{d['score']}{d['timestamp']}" for d in st.session_state.data}

                for i, s in enumerate(sets):
                    starter = ("A" if "Hráč 1" in m_first else "B") if (i + 1) % 2 != 0 else ("B" if "Hráč 1" in m_first else "A")
                    clean_score = s.strip().replace('-', ':')
                    new_set = {"A": p1_n, "B": p2_n, "score": clean_score, "starter": starter, "timestamp": ts, "odds": f"{o1}/{o2}"}
                    if f"{p1_n}{p2_n}{clean_score}{ts}" not in existing_keys:
                        temp_new_sets.append(new_set)
                    else: skip_count += 1

                if temp_new_sets:
                    st.session_state.data.extend(temp_new_sets)
                    save_data(st.session_state.data)
                    st.success(f"Uloženo {len(temp_new_sets)} setů!")
                    if skip_count > 0: st.info(f"Vynecháno {skip_count} duplicit.")
                    clear_input()
                    st.rerun()
            except Exception as e: st.error(f"Chyba: {e}")

with t2:
    ratings = get_ratings(st.session_state.data)
    if ratings:
        c1, c2 = st.columns(2)
        selA = c1.selectbox("Hráč A", sorted(list(ratings.keys())))
        selB = c2.selectbox("Hráč B", sorted(list(ratings.keys())))
        
        colA, colB, colC = st.columns(3)
        kWin = colA.number_input("Kurz na A", 1.01, 20.0, 1.85)
        kOver = colB.number_input("Kurz Over 18.5", 1.01, 20.0, 1.85)
        live_s = colC.radio("Právě podává:", [selA, selB])
        
        if selA != selB:
            rA, rB = ratings[selA], ratings[selB]
            q = math.log(10)/400
            
            # VYLEPŠENÍ: Zohlednění RD obou hráčů v predikci (pojistka nejistoty)
            rd_combined = math.sqrt(rA["rd"]**2 + rB["rd"]**2)
            g_comb = 1 / math.sqrt(1 + 3 * (q * rd_combined / math.pi)**2)
            
            # Pravděpodobnost výhry jednoho setu
            p_set = 1 / (1 + 10**(g_comb * (rA["r"] - rB["r"]) / -400))
            
            # Vliv podání
            p_set = min(max(p_set + (0.05 if live_s == selA else -0.05), 0.01), 0.99)
            
            # Pravděpodobnosti přesných výsledků (Zápas na 3 vítězné)
            sc = {
                "3:0": p_set**3,
                "3:1": 3 * (p_set**3) * (1-p_set),
                "3:2": 6 * (p_set**3) * ((1-p_set)**2),
                "0:3": (1-p_set)**3,
                "1:3": 3 * ((1-p_set)**3) * p_set,
                "2:3": 6 * ((1-p_set)**3) * (p_set**2)
            }
            
            probA_total = sc["3:0"] + sc["3:1"] + sc["3:2"]
            st.metric(f"Celková šance na výhru {selA}", f"{round(probA_total*100,1)}%")
            
            if (probA_total * kWin) > 1.05:
                st.success(f"🔥 VALUE VÝHRA (EV: {round(probA_total*kWin,2)})")
            
            st.write("---")
            st.subheader("🎯 Pravděpodobnost přesného výsledku")
            r_cols = st.columns(6)
            for i, (res, val) in enumerate(sc.items()):
                r_cols[i].metric(res, f"{round(val*100,1)}%")

            st.write("---")
            pOver = sc["3:1"] + sc["3:2"] + sc["1:3"] + sc["2:3"]
            st.write(f"**Šance na Over 3.5 setu (18.5+ bodu):** {round(pOver*100,1)}%")
            if (pOver * kOver) > 1.05:
                st.info(f"📈 Výhodný Over (EV: {round(pOver*kOver,2)})")
    else:
        st.warning("Nejdříve vlož nějaká data.")

with t3:
    ratings = get_ratings(st.session_state.data)
    if ratings:
        search = st.text_input("🔍 Hledat hráče")
        df = pd.DataFrame([{"Hráč": k, "Rating": int(v["r"]), "RD": int(v["rd"]), "Z": v["count"]} for k, v in ratings.items()])
        if search: df = df[df['Hráč'].str.contains(search.upper())]
        st.dataframe(df.sort_values("Rating", ascending=False), use_container_width=True, hide_index=True)

with t4:
    c_up, c_down = st.columns(2)
    with c_down:
        st.subheader("📤 Záloha")
        if st.session_state.data:
            csv = pd.DataFrame(st.session_state.data).to_csv(index=False).encode('utf-8-sig')
            st.download_button("STÁHNOUT CSV", data=csv, file_name="tt_star_backup.csv")
    with c_up:
        st.subheader("📥 Obnova")
        up = st.file_uploader("Nahrát CSV", type="csv")
        if up and st.button("✅ POTVRDIT NAHRÁNÍ"):
            df_up = pd.read_csv(up)
            st.session_state.data = df_up.to_dict('records')
            save_data(st.session_state.data)
            st.rerun()
    
    st.write("---")
    st.subheader("🕒 Historie (posledních 50)")
    recent = st.session_state.data[::-1][:50]
    for i, row in enumerate(recent):
        idx = len(st.session_state.data) - 1 - i
        with st.expander(f"{row['A']} vs {row['B']} | {row['score']} ({row['timestamp']})"):
            ca, cb, cc = st.columns(3)
            nA = ca.text_input("Hráč A", row['A'], key=f"nA{idx}")
            nB = cb.text_input("Hráč B", row['B'], key=f"nB{idx}")
            nS = cc.text_input("Skóre", row['score'], key=f"nS{idx}")
            if st.button("Uložit", key=f"s{idx}"):
                st.session_state.data[idx].update({"A": nA.upper(), "B": nB.upper(), "score": nS})
                save_data(st.session_state.data)
                st.rerun()
            if st.button("Smazat", key=f"d{idx}"):
                st.session_state.data.pop(idx)
                save_data(st.session_state.data)
                st.rerun()
