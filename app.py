import streamlit as st
import json, os, re, datetime, math, unicodedata
import pandas as pd
import io

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
                existing_keys = {f"{d['A']}{d['B']}{d['score']}{d['timestamp']}" for d in st.session_state.data}
                temp_new_sets = []
                for i, s in enumerate(sets):
                    starter = ("A" if "Hráč 1" in m_first else "B") if (i + 1) % 2 != 0 else ("B" if "Hráč 1" in m_first else "A")
                    clean_score = s.strip().replace('-', ':')
                    if f"{p1_n}{p2_n}{clean_score}{ts}" not in existing_keys:
                        temp_new_sets.append({"A": p1_n, "B": p2_n, "score": clean_score, "starter": starter, "timestamp": ts, "odds": f"{o1}/{o2}"})
                if temp_new_sets:
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
                "3:0": p_set**3,
                "3:1": 3 * (p_set**3) * (1-p_set),
                "3:2": 6 * (p_set**3) * ((1-p_set)**2),
                "0:3": (1-p_set)**3,
                "1:3": 3 * ((1-p_set)**3) * p_set,
                "2:3": 6 * ((1-p_set)**3) * (p_set**2)
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
            c1.metric(f"Kurz {selA}", f"{kWinA}", f"Férový: {fairA:.2f} {valA}", delta_color="normal")
            c2.metric(f"Kurz {selB}", f"{kWinB}", f"Férový: {fairB:.2f} {valB}", delta_color="normal")
            
            st.write("---")
            best_res = max(sc, key=sc.get)
            sets_count = int(best_res.split(':')[0]) + int(best_res.split(':')[1])
            
            st.subheader(f"📊 Odhadovaný výsledek: {best_res} ({sets_count} sety)")
            
            s_cols = st.columns(sets_count)
            for i in range(sets_count):
                if probA > 0.65: scores = ["11:7", "11:5", "11:8", "11:6", "11:9"]
                elif probA < 0.35: scores = ["7:11", "5:11", "8:11", "6:11", "9:11"]
                else: scores = ["11:9", "9:11", "12:10", "8:11", "11:8"]
                
                s_cols[i].markdown(f"**{i+1}. SET**")
                s_cols[i].code(scores[i])

            st.write("---")
            st.subheader("🎯 Šance na přesný výsledek")
            res_cols = st.columns(6)
            for i, (res, val) in enumerate(sc.items()):
                res_cols[i].metric(res, f"{val*100:.1f}%")
        else:
            st.error("Vyber dva rozdílné hráče!")
    else:
        st.warning("Nejdříve vlož nějaká data.")

with t3:
    ratings = get_ratings(st.session_state.data)
    if ratings:
        search = st.text_input("🔍 Hledat hráče")
        df_view = pd.DataFrame([{"Hráč": k, "Rating": int(v["r"]), "RD": int(v["rd"]), "Z": v["count"]} for k, v in ratings.items()])
        if search: df_view = df_view[df_view['Hráč'].str.contains(search.upper())]
        st.dataframe(df_view.sort_values("Rating", ascending=False), use_container_width=True, hide_index=True)

with t4:
    c_up, c_down = st.columns(2)
    with c_down:
        st.subheader("📤 Záloha")
        if st.session_state.data:
            csv = pd.DataFrame(st.session_state.data).to_csv(index=False).encode('utf-8-sig')
            st.download_button("STÁHNOUT CSV", data=csv, file_name="tt_star_backup.csv")
    
    with c_up:
        st.subheader("📥 Obnova / Nahrání")
        up = st.file_uploader("Nahrát vyčištěné CSV", type="csv")
        if up and st.button("✅ POTVRDIT NAHRÁNÍ"):
            try:
                # Robustní načtení: zkusíme UTF-8 se signaturou i bez
                raw_bytes = up.read()
                try:
                    text = raw_bytes.decode('utf-8-sig')
                except:
                    text = raw_bytes.decode('cp1250')
                
                df_up = pd.read_csv(io.StringIO(text), sep=None, engine='python')
                
                # OPRAVA: Odstranění neviditelných znaků z názvů sloupců
                df_up.columns = [col.encode('ascii', 'ignore').decode('ascii').strip() if isinstance(col, str) else col for col in df_up.columns]
                
                # Mapování sloupců pokud se jmenují jinak
                rename_map = {'A': 'A', 'B': 'B', 'score': 'score'} # Přidat další pokud Gemini změní jména
                df_up = df_up.rename(columns=rename_map)

                if not {'A', 'B', 'score'}.issubset(df_up.columns):
                    # Nouzový plán: pokud jména nesedí, zkusíme první 3 sloupce
                    df_up.columns = ['A', 'B', 'score'] + list(df_up.columns[3:])
                
                # Vyčištění dat od NaN a mezer
                df_up = df_up.where(pd.notnull(df_up), None)
                new_data = df_up.to_dict('records')
                
                st.session_state.data = new_data
                save_data(st.session_state.data)
                st.success(f"Úspěšně nahráno {len(new_data)} řádků!")
                st.rerun()
            except Exception as e:
                st.error(f"Chyba při nahrávání: {e}")
    
    st.write("---")
    st.subheader("🕒 Historie (posledních 50)")
    recent = st.session_state.data[::-1][:50]
    for i, row in enumerate(recent):
        idx = len(st.session_state.data) - 1 - i
        with st.expander(f"{row.get('A', '???')} vs {row.get('B', '???')} | {row.get('score', '???')} ({row.get('timestamp', '???')})"):
            ca, cb, cc = st.columns(3)
            nA = ca.text_input("Hráč A", row.get('A', ''), key=f"nA{idx}")
            nB = cb.text_input("Hráč B", row.get('B', ''), key=f"nB{idx}")
            nS = cc.text_input("Skóre", row.get('score', ''), key=f"nS{idx}")
            col_save, col_del = st.columns(2)
            if col_save.button("Uložit", key=f"s{idx}"):
                st.session_state.data[idx].update({"A": nA.upper(), "B": nB.upper(), "score": nS})
                save_data(st.session_state.data)
                st.rerun()
            if col_del.button("Smazat", key=f"d{idx}"):
                st.session_state.data.pop(idx)
                save_data(st.session_state.data)
                st.rerun()
