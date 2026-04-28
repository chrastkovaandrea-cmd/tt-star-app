import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import math
import pandas as pd

# --- 1. NASTAVENÍ A DATA ---
DATA_FILE = "tt_star_ultra_v9.json" 
BASE_ELO = 1500
K_FACTOR = 32
DEFAULT_SERVE_ADV = 0.04
BASE_RD = 350 

def normalize_name(name):
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'^[.\s]+', '', name)
    name = re.sub(r'^[A-Z][a-z]?\.', '', name) 
    return name.strip().upper()

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: 
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- 2. VÝPOČTOVÉ JÁDRO (ELO + GLICKO) ---
def calculate_advanced_stats():
    elos, glicko, serve_stats, h2h = {}, {}, {}, {}
    now = datetime.datetime.now()
    sorted_data = sorted(st.session_state.data, key=lambda x: x.get('timestamp', '0'))
    
    for entry in sorted_data:
        pA, pB = entry.get("A"), entry.get("B")
        score, winA, starter = entry.get("score", "0:0"), entry.get("win", 0), entry.get("starter", "A")
        ts_str = entry.get("timestamp", now.isoformat())
        if not pA or not pB: continue
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        if pA not in glicko: glicko[pA] = {"r": BASE_ELO, "rd": BASE_RD}
        if pB not in glicko: glicko[pB] = {"r": BASE_ELO, "rd": BASE_RD}

        exp_A = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        shift = K_FACTOR * (winA - exp_A)
        elos[pA] += shift
        elos[pB] -= shift

        rA, rdA, rB, rdB = glicko[pA]["r"], glicko[pA]["rd"], glicko[pB]["r"], glicko[pB]["rd"]
        ea_g = 1 / (1 + 10 ** ((rB - rA) / 400))
        glicko[pA]["r"] += (rdA / 10) * (winA - ea_g)
        glicko[pB]["r"] += (rdB / 10) * ((1 - winA) - (1 - ea_g))
        glicko[pA]["rd"] = max(30, rdA - 4)
        glicko[pB]["rd"] = max(30, rdB - 4)

        for p, s in [(pA, "A"), (pB, "B")]:
            if p not in serve_stats: serve_stats[p] = {"wins": 0, "total": 0}
            if starter == s:
                serve_stats[p]["total"] += 1
                if (s == "A" and winA == 1) or (s == "B" and winA == 0): serve_stats[p]["wins"] += 1
        pair = tuple(sorted([pA, pB]))
        if pair not in h2h: h2h[pair] = {pA: 0, pB: 0}
        h2h[pair][pA if winA == 1 else pB] += 1
    return elos, glicko, serve_stats, h2h

def predict_advanced(pA, pB, starter, elos, serve_stats, h2h):
    eloA, eloB = elos.get(pA, BASE_ELO), elos.get(pB, BASE_ELO)
    pA_win = 1 / (1 + 10 ** ((eloB - eloA) / 400))
    s_statA = serve_stats.get(pA, {"wins": 0, "total": 0})
    s_statB = serve_stats.get(pB, {"wins": 0, "total": 0})
    advA = (s_statA["wins"] / max(1, s_statA["total"])) * 0.1
    advB = (s_statB["wins"] / max(1, s_statB["total"])) * 0.1
    if (s_statA["total"] + s_statB["total"]) > 0:
        pA_win += (advA if starter == "A" else -advB)
    else:
        pA_win += (DEFAULT_SERVE_ADV if starter == "A" else -DEFAULT_SERVE_ADV)
    pair = tuple(sorted([pA, pB]))
    if pair in h2h:
        total = h2h[pair][pA] + h2h[pair][pB]
        if total > 2: pA_win = (pA_win * 0.7) + ((h2h[pair][pA] / total) * 0.3)
    pA_win = min(max(pA_win, 0.02), 0.98)
    prob_over = max(0.20, 0.88 - (abs(eloA - eloB) / 450))
    return pA_win, prob_over

def get_exact_score_probs(probA):
    lA = 11.0 if probA >= 0.5 else 11.0 * (probA / (1 - probA + 1e-9))
    lB = 11.0 if probA < 0.5 else 11.0 * ((1 - probA) / (probA + 1e-9))
    scores = []
    for b in range(10): scores.append(((11, b), (math.exp(-lA)*lA**11/math.factorial(11))*(math.exp(-lB)*lB**b/math.factorial(b))))
    for a in range(10): scores.append(((a, 11), (math.exp(-lA)*lA**a/math.factorial(a))*(math.exp(-lB)*lB**11/math.factorial(11))))
    total = sum(s[1] for s in scores)
    return sorted([(s[0], s[1]/total) for s in scores], key=lambda x: x[1], reverse=True)[:5]

def parse_live_text(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    set_num = 1
    s_match = re.search(r'(\d+)\.\s*SET', text, re.IGNORECASE)
    if s_match: set_num = int(s_match.group(1))
    forbidden = ["milestone-logo", "kurzy", "průběh", "statistiky", "tikety", "začátek zápasu"]
    clean = [l for l in lines if not any(f in l.lower() for f in forbidden) and not l.lower().startswith("konec")]
    if len(clean) < 2: return None
    pA, pB = normalize_name(clean[0]), normalize_name(clean[1])
    full = re.sub(r'\s*:\s*', ':', " ".join(clean))
    scores = re.findall(r'(\d+):(\d+)', full)
    pts = [(int(a), int(b)) for a, b in scores] if scores else []
    return {"A": pA, "B": pB, "score": f"{pts[-1][0]}:{pts[-1][1]}" if pts else "0:0", "win": 1 if pts and pts[-1][0] > pts[-1][1] else 0, "set_num": set_num}

# --- 4. UI ---
st.set_page_config(page_title="TT STAR v12.5 ULTRA", layout="wide")
st.title("🏓 TT STAR - ULTRA ANALYTIK")

t1, t2, t3, t4 = st.tabs(["📥 Vložit Set", "🔮 Predikce & Value", "🏆 Žebříček", "⚙️ Historie"])

with t1:
    raw_in = st.text_area("Vložte text z Tipsportu:", height=150)
    c_d1, c_d2, c_d3 = st.columns(3)
    res = parse_live_text(raw_in) if raw_in else None
    with c_d1: m_date = st.date_input("Datum zápasu:", datetime.date.today())
    with c_d2: m_set = st.number_input("Tento set č.:", 1, 5, value=res['set_num'] if res else 1)
    
    # TVOJE POŽADOVANÁ LOGIKA STŘÍDÁNÍ:
    with c_d3: m_first_match = st.selectbox("Kdo podával v 1. SETU zápasu?", ["A", "B"])
    
    # Výpočet: pokud je set lichý (1,3,5), podává ten co v prvním. Pokud sudý (2,4), podává ten druhý.
    if m_set % 2 != 0: 
        current_starter = m_first_match
    else: 
        current_starter = "B" if m_first_match == "A" else "A"
    
    st.warning(f"V {m_set}. setu automaticky podává: **Hráč {current_starter}**")

    if st.button("🚀 Uložit set"):
        if res:
            dt = datetime.datetime.combine(m_date, datetime.datetime.now().time())
            st.session_state.data.append({"id": str(dt.timestamp()), "A": res["A"], "B": res["B"], "score": res["score"], "win": res["win"], "starter": current_starter, "set_num": m_set, "timestamp": dt.isoformat()})
            save_data(st.session_state.data); st.success("Uloženo!"); st.rerun()

with t2:
    st.subheader("🔮 Analýza sázky")
    cur_elos, cur_glicko, cur_serve, cur_h2h = calculate_advanced_stats()
    col_in1, col_in2 = st.columns(2)
    with col_in1: pA_in = st.text_input("Hráč A").upper()
    with col_in2: pB_in = st.text_input("Hráč B").upper()
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1: final_s = st.radio("Podává v tomto setu:", ["A", "B"])
    with col_p2: oddsA = st.number_input("Aktuální kurz na vítěze A:", 1.0, 10.0, 1.85)
    with col_p3: oddsO = st.number_input("Aktuální kurz na Over 18.5:", 1.0, 10.0, 1.85)
    if pA_in and pB_in:
        pA_w, p_ov = predict_advanced(pA_in, pB_in, final_s, cur_elos, cur_serve, cur_h2h)
        v1, v2 = st.columns(2)
        with v1:
            valA = (pA_w * oddsA) - 1
            st.metric(f"Vítěz {pA_in}", f"{round(pA_w*100,1)}%", f"Fair: {round(1/pA_w,2)}")
            if valA > 0: st.success(f"✅ VALUE: +{round(valA*100,1)}%")
        with v2:
            valO = (p_ov * oddsO) - 1
            st.metric("Over 18.5 bodů", f"{round(p_ov*100,1)}%", f"Fair: {round(1/p_ov,2)}")
            if valO > 0: st.success(f"✅ VALUE: +{round(valO*100,1)}%")

with t3:
    st.subheader("Žebříček (Elo & Glicko)")
    elos, glicko, _, _ = calculate_advanced_stats()
    rows = []
    for p in elos:
        rows.append({"Hráč": p, "Elo": int(elos[p]), "Glicko": int(glicko[p]["r"]), "RD (Jistota)": int(glicko[p]["rd"])})
    df = pd.DataFrame(rows).sort_values("Glicko", ascending=False)
    st.dataframe(df, use_container_width=True)

with t4:
    st.subheader("⚙️ Správa Historie")
    st.download_button(label="📥 STÁHNOUT ZÁLOHU DO MOBILU", data=json.dumps(st.session_state.data, indent=4), file_name=f"tt_backup.json", mime="application/json")
    st.divider()
    for i in range(len(st.session_state.data)-1, -1, -1):
        d = st.session_state.data[i]
        with st.expander(f"📝 {d['A']} vs {d['B']} ({d['score']})"):
            if st.button("💾 Uložit", key=f"sv_{i}"): save_data(st.session_state.data); st.rerun()
            if st.button("🗑️ Smazat", key=f"dl_{i}"): st.session_state.data.pop(i); save_data(st.session_state.data); st.rerun()
