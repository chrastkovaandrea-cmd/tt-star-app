import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import math

# --- 1. NASTAVENÍ A DATA ---
DATA_FILE = "tt_star_ultra_v9.json" 
BASE_ELO = 1500
K_FACTOR = 32
DEFAULT_SERVE_ADV = 0.04

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

# --- 2. VÝPOČTOVÉ JÁDRO ---

def calculate_advanced_stats():
    elos, serve_stats, h2h = {}, {}, {}
    now = datetime.datetime.now()
    # Důležité pro Elo: počítat od nejstarších po nejnovější
    sorted_data = sorted(st.session_state.data, key=lambda x: x.get('timestamp', '0'))
    
    for entry in sorted_data:
        pA, pB = entry.get("A"), entry.get("B")
        score, winA, starter = entry.get("score", "0:0"), entry.get("win", 0), entry.get("starter", "A")
        ts_str = entry.get("timestamp", now.isoformat())
        
        if not pA or not pB: continue
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        
        try:
            match_date = datetime.datetime.fromisoformat(ts_str)
            days_old = (now - match_date).days
            time_weight = 1.0 / (1 + (max(0, days_old) * 0.05))
        except: time_weight = 1.0

        try:
            sa, sb = map(int, score.split(':'))
            diff = abs(sa - sb)
        except: diff = 2
            
        exp_A = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        mov = math.log(diff + 1) * (2.2 / ((winA - exp_A) * 0.001 + 2.2)) if winA != exp_A else 1
        shift = K_FACTOR * (winA - exp_A) * mov * time_weight
        elos[pA] += shift
        elos[pB] -= shift

        for p, s in [(pA, "A"), (pB, "B")]:
            if p not in serve_stats: serve_stats[p] = {"wins": 0, "total": 0}
            if starter == s:
                serve_stats[p]["total"] += 1
                if (s == "A" and winA == 1) or (s == "B" and winA == 0): serve_stats[p]["wins"] += 1

        pair = tuple(sorted([pA, pB]))
        if pair not in h2h: h2h[pair] = {pA: 0, pB: 0}
        h2h[pair][pA if winA == 1 else pB] += 1

    return elos, serve_stats, h2h

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

# --- 3. PARSER ---
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
    if pts and (pts[0][0] + pts[0][1]) > (pts[-1][0] + pts[-1][1]): pts.reverse()
    starter = "A"
    serve_info = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text, re.IGNORECASE)
    if serve_info:
        found = normalize_name(serve_info.group(1))
        starter = "B" if (found in pB or pB in found) else "A"
    return {"A": pA, "B": pB, "score": f"{pts[-1][0]}:{pts[-1][1]}" if pts else "0:0", "win": 1 if pts and pts[-1][0] > pts[-1][1] else 0, "starter": starter, "set_num": set_num}

# --- 4. UI ---
st.set_page_config(page_title="TT STAR v10.8.1 ULTRA", layout="wide")
st.title("🏓 TT STAR - ULTRA ANALYTIK")

t1, t2, t3, t4 = st.tabs(["📥 Vložit Set", "🔮 Predikce & Value", "🏆 Žebříček", "⚙️ Historie"])

with t1:
    raw_in = st.text_area("Vložte text z Tipsportu:", height=150)
    c_d1, c_d2, c_d3 = st.columns(3)
    res = parse_live_text(raw_in) if raw_in else None
    with c_d1: m_date = st.date_input("Datum zápasu:", datetime.date.today())
    with c_d2: m_set = st.number_input("Číslo setu:", 1, 5, value=res['set_num'] if res else 1)
    with c_d3: m_start = st.selectbox("Kdo začal podávat?", ["A", "B"], index=0 if (res and res['starter']=="A") else 1)
    if st.button("🚀 Uložit set"):
        if res:
            dt = datetime.datetime.combine(m_date, datetime.datetime.now().time())
            st.session_state.data.append({"id": str(dt.timestamp()), "A": res["A"], "B": res["B"], "score": res["score"], "win": res["win"], "starter": m_start, "set_num": m_set, "timestamp": dt.isoformat()})
            save_data(st.session_state.data); st.success("Uloženo!"); st.rerun()

with t2:
    st.subheader("🔮 Analýza sázky")
    cur_elos, cur_serve, cur_h2h = calculate_advanced_stats()
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

        st.subheader("🎯 Odhad skóre setu")
        ex_sc = get_exact_score_probs(pA_w)
        cols = st.columns(5)
        for i, ((sa, sb), p) in enumerate(ex_sc):
            with cols[i]: st.info(f"**{sa}:{sb}**\n\n{round(p*100,1)}%")

        st.subheader("🏆 Přesný výsledek zápasu (sety)")
        p = pA_w
        r = [("3:0", p**3), ("3:1", 3*p**3*(1-p)), ("3:2", 6*p**3*(1-p)**2), ("2:3", 6*(1-p)**3*p**2), ("1:3", 3*(1-p)**3*p), ("0:3", (1-p)**3)]
        cols_r = st.columns(6)
        for i, (res_s, prob_s) in enumerate(r):
            with cols_r[i]: st.write(f"**{res_s}**"); st.write(f"{round(prob_s*100,1)}%")

with t3:
    cur_elos, _, _ = calculate_advanced_stats()
    sorted_ranking = sorted(cur_elos.items(), key=lambda x: x[1], reverse=True)
    for r, (n, v) in enumerate(sorted_ranking):
        st.write(f"{r+1}. **{n}** — {int(v)} pts")

with t4:
    st.subheader("⚙️ Správa Historie")
    for i in range(len(st.session_state.data)-1, -1, -1):
        d = st.session_state.data[i]
        ts_val = datetime.datetime.fromisoformat(d.get('timestamp', datetime.datetime.now().isoformat()))
        with st.expander(f"📝 {ts_val.strftime('%d.%m. %H:%M')} | {d['A']} vs {d['B']} ({d['score']})"):
            c_e1, c_e2 = st.columns(2)
            with c_e1:
                new_A = st.text_input("Hráč A", d['A'], key=f"nA_{i}").upper()
                new_B = st.text_input("Hráč B", d['B'], key=f"nB_{i}").upper()
                new_score = st.text_input("Skóre", d['score'], key=f"nS_{i}")
            with c_e2:
                new_date = st.date_input("Datum", ts_val.date(), key=f"nD_{i}")
                new_starter = st.selectbox("Podání", ["A", "B"], index=0 if d['starter']=="A" else 1, key=f"nst_{i}")
                if st.button("💾 Uložit změny", key=f"sv_{i}"):
                    st.session_state.data[i].update({"A": new_A, "B": new_B, "score": new_score, "starter": new_starter, "timestamp": datetime.datetime.combine(new_date, ts_val.time()).isoformat()})
                    try:
                        sa, sb = map(int, new_score.split(':'))
                        st.session_state.data[i]['win'] = 1 if sa > sb else 0
                    except: pass
                    save_data(st.session_state.data); st.rerun()
                if st.button("🗑️ Smazat záznam", key=f"dl_{i}"):
                    st.session_state.data.pop(i); save_data(st.session_state.data); st.rerun()
