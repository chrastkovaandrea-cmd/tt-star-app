import streamlit as st
import json, os, re, datetime, math, unicodedata
import pandas as pd
import io

# --- KONFIGURACE ---
DATA_FILE = "tt_star_ultra_v17.json"
st.set_page_config(page_title="TT STAR ANALYTIK PRO", page_icon="🏓", layout="wide")

def normalize_name(name):
    if not name or pd.isna(name): return ""
    name = str(name)
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)
    return re.sub(r'[^A-Z\s]', '', name.upper()).strip()

def save_data(data):
    with open(DATA_FILE, "w") as f: 
        json.dump(data, f, indent=4)
    st.cache_data.clear()

if 'data' not in st.session_state:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: st.session_state.data = json.load(f)
        except: st.session_state.data = []
    else:
        st.session_state.data = []

# --- GLICKO-2 MATEMATIKA ---
@st.cache_data(show_spinner="Aktualizuji ratingy...")
def get_ratings(data_list):
    ratings = {}
    BASE_R, BASE_RD, BASE_VOL = 1500, 350, 0.06
    if not data_list: return {}
    
    sorted_data = sorted(data_list, key=lambda x: str(x.get('timestamp', '')))
    q = math.log(10) / 400
    
    for d in sorted_data:
        pA, pB, score = d.get('A'), d.get('B'), d.get('score')
        if not pA or not pB or ":" not in str(score): continue
        
        # Očištění jmen pro jistotu během výpočtu
        pA, pB = normalize_name(pA), normalize_name(pB)
        
        for p in [pA, pB]:
            if p not in ratings: 
                ratings[p] = {"r": BASE_R, "rd": BASE_RD, "vol": BASE_VOL, "count": 0}
        
        try:
            ptsA, ptsB = map(int, str(score).split(':'))
            margin = abs(ptsA - ptsB)
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
    st.info("Zde můžete vkládat jednotlivé výsledky ručně. Pro hromadný import použijte záložku Správa.")
    if "input_val" not in st.session_state: st.session_state.input_val = ""
    def clear_input():
        st.session_state.input_val = ""
        if "txt_area" in st.session_state: st.session_state.txt_area = ""

    raw_in = st.text_area("Vlož text zápasu (formát z webu):", value=st.session_state.input_val, height=100, key="txt_area")
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
                for i, s in enumerate(sets):
                    starter = ("A" if "Hráč 1" in m_first else "B") if (i + 1) % 2 != 0 else ("B" if "Hráč 1" in m_first else "A")
                    clean_score = s.strip().replace('-', ':')
                    temp_new_sets.append({"A": p1_n, "B": p2_n, "score": clean_score, "starter": starter, "timestamp": ts, "odds": f"{o1}/{o2}"})
                
                st.session_state.data.extend(temp_new_sets)
                save_data(st.session_state.data)
                st.success(f"Uloženo {len(temp_new_sets)} setů!")
                clear_input()
                st.rerun()
            except Exception as e: st.error(f"Chyba: {e}")

with t2:
    ratings = get_ratings(st.session_state.data)
    if ratings:
        player_list = sorted(list(ratings.keys()))
        col_sel1, col_sel2 = st.columns(2)
        selA = col_sel1.selectbox("Hráč A", player_list, key="pred_sel_A")
        selB = col_sel2.selectbox("Hráč B", player_list, index=min(1, len(player_list)-1), key="pred_sel_B")
        
        col_o1, col_o2, col_o3 = st.columns(3)
        kWinA = col_o1.number_input(f"Kurz na {selA}", 1.01, 20.0, 1.85, key="odds_input_A")
        kWinB = col_o2.number_input(f"Kurz na {selB}", 1.01, 20.0, 1.85, key="odds_input_B")
        live_s = col_o3.radio("Servis začíná:", [selA, selB], key="service_radio")
        
        if selA != selB:
            rA, rB = ratings[selA], ratings[selB]
            q = math.log(10)/400
            rd_combined = math.sqrt(rA["rd"]**2 + rB["rd"]**2)
            g_comb = 1 / math.sqrt(1 + 3 * (q * rd_combined / math.pi)**2)
            
            p_set_base = 1 / (1 + 10**(g_comb * (rA["r"] - rB["r"]) / -400))
            p_set = min(max(p_set_base + (0.04 if live_s == selA else -0.04), 0.05), 0.95)
            
            sc = {
                "3:0": p_set**3, "3:1": 3 * (p_set**3) * (1-p_set), "3:2": 6 * (p_set**3) * ((1-p_set)**2),
                "0:3": (1-p_set)**3, "1:3": 3 * ((1-p_set)**3) * p_set, "2:3": 6 * ((1-p_set)**3) * (p_set**2)
            }
            
            probA = sc["3:0"] + sc["3:1"] + sc["3:2"]
            probB = 1 - probA
            fairA, fairB = 1/probA if probA > 0 else 100, 1/probB if probB > 0 else 100
            
            winner = selA if probA > probB else selB
            win_pct = max(probA, probB) * 100
            valA = "🟢" if kWinA > fairA else "❌"
            valB = "🟢" if kWinB > fairB else "❌"
            
            st.markdown(f"### 🏆 Predikce: **{winner}** ({win_pct:.1f}%)")
            
            c1, c2 = st.columns(2)
            c1.metric(f"Kurz {selA}", f"{kWinA}", f"Férový: {fairA:.2f} {valA}")
            c2.metric(f"Kurz {selB}", f"{kWinB}", f"Férový: {fairB:.2f} {valB}")

with t3:
    ratings = get_ratings(st.session_state.data)
    if ratings:
        df_view = pd.DataFrame([{"Hráč": k, "Rating": int(v["r"]), "RD": int(v["rd"]), "Z": v["count"]} for k, v in ratings.items()])
        st.dataframe(df_view.sort_values("Rating", ascending=False), use_container_width=True, hide_index=True)

with t4:
    st.subheader("⚙️ Správa a Import")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📥 Nahrát CSV soubor")
        up = st.file_uploader("Vyber CSV (jakýkoliv formát)", type="csv")
        if up and st.button("✅ IMPORTOVAT SOUBOR"):
            try:
                # Načtení bez ohledu na kódování
                bytes_data = up.read()
                try: text_data = bytes_data.decode('utf-8-sig')
                except: text_data = bytes_data.decode('cp1250')
                
                # Flexibilní načtení: zkusíme čárku i středník
                df_up = pd.read_csv(io.StringIO(text_data), sep=None, engine='python')
                
                # Vyčištění jmen sloupců (odstraníme mezery a tečky)
                df_up.columns = [str(c).strip() for c in df_up.columns]
                
                # Klíčová oprava: Mapování sloupců podle obsahu
                # Hledáme sloupce, které by mohly být A, B a score
                final_df = pd.DataFrame()
                if 'A' in df_up.columns and 'B' in df_up.columns:
                    final_df['A'] = df_up['A']
                    final_df['B'] = df_up['B']
                else: # Pokud se jmenují jinak, vezmeme první dva
                    final_df['A'] = df_up.iloc[:, 0]
                    final_df['B'] = df_up.iloc[:, 1]
                
                if 'score' in df_up.columns: final_df['score'] = df_up['score']
                else: final_df['score'] = df_up.iloc[:, 2]
                
                # Přidáme zbytek sloupců, pokud existují
                for col in df_up.columns:
                    if col not in ['A', 'B', 'score']:
                        final_df[col] = df_up[col]

                # Normalizace jmen v celém souboru
                final_df['A'] = final_df['A'].apply(normalize_name)
                final_df['B'] = final_df['B'].apply(normalize_name)
                
                st.session_state.data = final_df.where(pd.notnull(final_df), None).to_dict('records')
                save_data(st.session_state.data)
                st.success(f"Úspěšně naimportováno {len(st.session_state.data)} řádků!")
                st.rerun()
            except Exception as e: st.error(f"Chyba při importu: {e}")
            
    with col2:
        st.subheader("📤 Záloha")
        if st.session_state.data:
            csv_out = pd.DataFrame(st.session_state.data).to_csv(index=False).encode('utf-8-sig')
            st.download_button("STÁHNOUT AKTUÁLNÍ DATA", data=csv_out, file_name="tt_star_backup.csv")

    st.write("---")
    if st.button("🧨 SMAZAT VŠECHNA DATA", use_container_width=True):
        st.session_state.data = []
        save_data([])
        st.rerun()
