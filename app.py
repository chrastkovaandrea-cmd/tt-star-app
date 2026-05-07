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
    st.info("Ruční vkládání zápasu")
    raw_in = st.text_area("Text zápasu:", height=100, key="txt_area")
    m_first = st.selectbox("Podání v 1. setu:", ["Hráč 1", "Hráč 2"])
    if st.button("🚀 ULOŽIT"):
        # ... (zde zůstává tvoje původní logika vkládání)
        pass

with t3:
    ratings = get_ratings(st.session_state.data)
    if ratings:
        df_view = pd.DataFrame([{"Hráč": k, "Rating": int(v["r"]), "Zápasů": v["count"]} for k, v in ratings.items()])
        st.dataframe(df_view.sort_values("Rating", ascending=False), use_container_width=True)

with t4:
    st.subheader("⚙️ Import a Oprava dat")
    
    # TADY JE TA ZMĚNA: type=None povolí i "tmavé" soubory
    up = st.file_uploader("Vyberte soubor (i ten upravený/merged)", type=None)
    
    if up is not None:
        if st.button("✅ NAHRÁT A OPRAVIT SOUBOR"):
            try:
                bytes_data = up.read()
                # Zkusíme různé dekódování
                try: text_data = bytes_data.decode('utf-8-sig')
                except: text_data = bytes_data.decode('cp1250')
                
                # Načtení - sep=None zkusí čárku i středník
                df = pd.read_csv(io.StringIO(text_data), sep=None, engine='python')
                
                # --- INTELIGENTNÍ OPRAVA SLOUPCŮ ---
                # Přejmenujeme sloupce, pokud jsou tam ty z merged verze
                df.columns = [str(c).strip() for c in df.columns]
                
                mapping = {}
                # Najdeme sloupec pro Hráče A
                for c in df.columns:
                    if c.lower() in ['a', 'player_a', 'hrac1', 'hrac_a']: mapping[c] = 'A'
                    if c.lower() in ['b', 'player_b', 'hrac2', 'hrac_b']: mapping[c] = 'B'
                    if c.lower() in ['score', 'vysledek', 'skore']: mapping[c] = 'score'
                
                if mapping:
                    df = df.rename(columns=mapping)
                
                # Pokud po mapování nemáme A, B, score, vezmeme prostě první 3 sloupce
                if 'A' not in df.columns or 'B' not in df.columns:
                    df = df.rename(columns={df.columns[0]: 'A', df.columns[1]: 'B', df.columns[2]: 'score'})

                # Vyčištění dat
                df['A'] = df['A'].apply(normalize_name)
                df['B'] = df['B'].apply(normalize_name)
                
                # Převedení na JSON formát pro model
                new_data = df.where(pd.notnull(df), None).to_dict('records')
                st.session_state.data = new_data
                save_data(new_data)
                
                st.success(f"Hotovo! Nahráno a opraveno {len(new_data)} řádků.")
                st.rerun()
                
            except Exception as e:
                st.error(f"Chyba při zpracování: {e}")

    st.write("---")
    if st.button("🧨 SMAZAT VŠE"):
        st.session_state.data = []
        save_data([])
        st.rerun()
