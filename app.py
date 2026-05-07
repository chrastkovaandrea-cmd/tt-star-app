import streamlit as st
import json, os, re, datetime, math, unicodedata
import pandas as pd
import io

# --- KONFIGURACE ---
DATA_FILE = "tt_star_ultra_v17.json"
st.set_page_config(page_title="TT STAR ANALYTIK PRO", page_icon="🏓", layout="wide")

def normalize_name(name):
    if not name or pd.isna(name): return ""
    name = str(name).strip().upper()
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[A-Z]\.\s*', '', name)
    return re.sub(r'[^A-Z\s]', '', name).strip()

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

# --- GLICKO-2 VÝPOČET ---
@st.cache_data(show_spinner="Přepočítávám žebříček...")
def get_ratings(data_list):
    ratings = {}
    BASE_R, BASE_RD, BASE_VOL = 1500, 350, 0.06
    if not data_list: return {}
    
    sorted_data = sorted(data_list, key=lambda x: str(x.get('timestamp', '')))
    q = math.log(10) / 400
    
    for d in sorted_data:
        pA, pB, score = d.get('A'), d.get('B'), d.get('score')
        if not pA or not pB or ":" not in str(score): continue
        
        pA, pB = normalize_name(pA), normalize_name(pB)
        for p in [pA, pB]:
            if p not in ratings: 
                ratings[p] = {"r": BASE_R, "rd": BASE_RD, "vol": BASE_VOL, "count": 0}
        
        try:
            ptsA, ptsB = map(int, str(score).split(':'))
            actual_winA = 1 if ptsA > ptsB else 0
            win_weight = 1.0 + (min(abs(ptsA - ptsB), 9) / 20.0)
            
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

# --- ROZHRANÍ ---
t1, t2, t3, t4 = st.tabs(["📥 Vkládání", "🔮 Predikce", "🏆 Žebříček", "⚙️ Správa"])

with t1:
    st.subheader("Ruční vkládání zápasu")
    raw_in = st.text_area("Vlož text zápasu (formát z webu):", height=100, key="txt_area")
    m_first = st.selectbox("Kdo podával v 1. SETU?", ["Hráč 1 (Horní)", "Hráč 2 (Dolní)"])
    
    if st.button("🚀 ULOŽIT ZÁPAS"):
        if raw_in:
            try:
                parts = raw_in.split('|')
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
                st.rerun()
            except Exception as e: st.error(f"Chyba: {e}")

with t3:
    ratings = get_ratings(st.session_state.data)
    if ratings:
        df_view = pd.DataFrame([{"Hráč": k, "Rating": int(v["r"]), "Z": v["count"]} for k, v in ratings.items()])
        st.dataframe(df_view.sort_values("Rating", ascending=False), use_container_width=True, hide_index=True)

with t4:
    st.subheader("⚙️ Správa, Import a Export")
    
    col_imp, col_exp = st.columns(2)
    
    with col_imp:
        st.markdown("### 📥 Import")
        up = st.file_uploader("Vyberte soubor pro nahrání", type=None)
        if up is not None:
            if st.button("✅ POTVRDIT IMPORT"):
                try:
                    bytes_data = up.read()
                    try: text_data = bytes_data.decode('utf-8-sig')
                    except: text_data = bytes_data.decode('cp1250')
                    
                    df = pd.read_csv(io.StringIO(text_data), sep=None, engine='python')
                    df.columns = [str(c).strip() for c in df.columns]
                    
                    # Mapování sloupců
                    if 'A' not in df.columns or 'B' not in df.columns:
                        df = df.rename(columns={df.columns[0]: 'A', df.columns[1]: 'B', df.columns[2]: 'score'})
                    
                    df['A'] = df['A'].apply(normalize_name)
                    df['B'] = df['B'].apply(normalize_name)
                    
                    new_rows = df.where(pd.notnull(df), None).to_dict('records')
                    st.session_state.data = new_rows
                    save_data(new_rows)
                    st.success(f"Nahráno {len(new_rows)} řádků.")
                    st.rerun()
                except Exception as e: st.error(f"Chyba: {e}")

    with col_exp:
        st.markdown("### 📤 Export")
        if st.session_state.data:
            # Převedeme aktuální data v paměti na CSV
            df_export = pd.DataFrame(st.session_state.data)
            csv_buffer = io.StringIO()
            df_export.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            
            st.write(f"Aktuální počet řádků: **{len(st.session_state.data)}**")
            st.download_button(
                label="💾 STÁHNOUT AKTUÁLNÍ DATA (CSV)",
                data=csv_buffer.getvalue(),
                file_name=f"tt_star_backup_{datetime.datetime.now().strftime('%d_%m_%H_%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("Žádná data k exportu.")

    st.write("---")
    if st.button("🧨 SMAZAT VŠECHNA DATA", use_container_width=True):
        st.session_state.data = []
        save_data([])
        st.rerun()
