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

# --- 2. POKROČILÉ VÝPOČTY ---

def calculate_advanced_stats():
    elos = {}
    player_serve_stats = {}
    h2h = {}
    now = datetime.datetime.now()
    
    # Seřazení podle data zápasu
    sorted_data = sorted(st.session_state.data, key=lambda x: x.get('timestamp', '0'))
    
    for entry in sorted_data:
        pA, pB = entry.get("A"), entry.get("B")
        score = entry.get("score", "0:0")
        winA = entry.get("win", 0)
        starter = entry.get("starter", "A")
        ts_str = entry.get("timestamp", str(now.isoformat()))
        
        if not pA or not pB: continue
        if pA not in elos: elos[pA] = BASE_ELO
        if pB not in elos: elos[pB] = BASE_ELO
        
        # 1. Časová váha (Recency Bias)
        try:
            match_date = datetime.datetime.fromisoformat(ts_str)
            days_old = (now - match_date).days
            time_weight = 1.0 / (1 + (max(0, days_old) * 0.05))
        except: time_weight = 1.0

        try:
            sa, sb = map(int, score.split(':'))
            point_diff = abs(sa - sb)
        except: point_diff = 2
            
        exp_A = 1 / (1 + 10 ** ((elos[pB] - elos[pA]) / 400))
        mov_multiplier = math.log(point_diff + 1) * (2.2 / ((winA - exp_A) * 0.001 + 2.2)) if winA != exp_A else 1
        
        shift = K_FACTOR * (winA - exp_A) * mov_multiplier * time_weight
        elos[pA] += shift
        elos[pB] -= shift

        # 2. Osobní podání
        for p, s in [(pA, "A"), (pB, "B")]:
            if p not in player_serve_stats: player_serve_stats[p] = {"wins": 0, "total": 0}
            if starter == s:
                player_serve_stats[p]["total"] += 1
                if (s == "A" and winA == 1) or (s == "B" and winA == 0):
                    player_serve_stats[p]["wins"] += 1

        # 4. H2H
        pair = tuple(sorted([pA, pB]))
        if pair not in h2h: h2h[pair] = {pA: 0, pB: 0}
        if winA == 1: h2h[pair][pA] += 1
        else: h2h[pair][pB] += 1

    return elos, player_serve_stats, h2h

def predict_advanced(pA, pB, starter, elos, serve_stats, h2h):
    eloA = elos.get(pA, BASE_ELO)
    eloB = elos.get(pB, BASE_ELO)
    pA_win = 1 / (1 + 10 ** ((eloB - eloA) / 400))
    
    advA = (serve_stats.get(pA, {}).get("wins", 0) / max(1, serve_stats.get(pA, {}).get("total", 0))) * 0.1
    advB = (serve_stats.get(pB, {}).get("wins", 0) / max(1, serve_stats.get(pB, {}).get("total", 0))) * 0.1
    current_adv = (advA if starter == "A" else -advB)
    pA_win += (current_adv if current_adv != 0 else (DEFAULT_SERVE_ADV if starter == "A" else -DEFAULT_SERVE_ADV))
    
    pair = tuple(sorted([pA, pB]))
    if pair in h2h:
        total = h2h[pair][pA] + h2h[pair][pB]
        if total > 2:
            pA_win = (pA_win * 0.7) + ((h2h[pair][pA] / total) * 0.3)

    pA_win = min(max(pA_win, 0.02), 0.98)
    prob_over = max(0.20, 0.88 - (abs(eloA - eloB) / 450))
    return pA_win, prob_over

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
    if not scores: return None
    pts = [(int(a), int(b)) for a, b in scores]
    if (pts[0][0] + pts[0][1]) > (pts[-1][0] + pts[-1][1]): pts.reverse()
    starter = "A"
    serve_info = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text, re.IGNORECASE)
    if serve_info:
        found = normalize_name(serve_info.group(1))
        starter = "B" if (found in pB or pB in found) else "A"
    return {"A": pA, "B": pB, "score": f"{pts[-1][0]}:{pts[-1][1]}", "win": 1 if pts[-1][0] > pts[-1][1] else 0, "starter": starter, "set_num": set_num}

# --- 4. UI ---
st.set_page_config(page_title="TT STAR v10.6 PRO", layout="wide")
st.title("🏓 TT STAR - VŠEUMĚL v10.6 PRO")

t1, t2, t3, t4 = st.tabs(["📥 Vložit", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie"])

with t1:
    raw_in = st.text_area("Vložte text z Tipsportu:", height=150)
    col_d1, col_d2, col_d3 = st.columns(3)
    res = parse_live_text(raw_in) if raw_in else None
    
    with col_d1:
        manual_date = st.date_input("Datum zápasu:", datetime.date.today())
    with col_d2:
        manual_set = st.number_input("Číslo setu:", 1, 5, value=res['set_num'] if res else 1)
    with col_d3:
        manual_starter = st.selectbox("Kdo začal podávat?", ["A", "B"], index=0 if (res and res['starter']=="A") else 1)
        
    if st.button("🚀 Uložit set"):
        if res:
            # Ukládáme zvolené datum + aktuální čas pro zachování pořadí
            dt_combined = datetime.datetime.combine(manual_date, datetime.datetime.now().time())
            new_e = {"id": str(dt_combined.timestamp()), "A": res["A"], "B": res["B"], "score": res["score"], "win": res["win"], "starter": manual_starter, "set_num": manual_set, "timestamp": dt_combined.isoformat()}
            st.session_state.data.append(new_e)
            save_data(st.session_state.data)
            st.success(f"Uloženo k datu {manual_date.strftime('%d.%m.')}: {res['A']} vs {res['B']}")

with t2:
    st.subheader("🔮 Pokročilá Predikce")
    current_elos, serve_stats, h2h_data = calculate_advanced_stats()
    c1, c2, c3 = st.columns(3)
    with c1: pA_in = st.text_input("Hráč A").upper()
    with c2: pB_in = st.text_input("Hráč B").upper()
    with c3:
        relevant = [d for d in st.session_state.data if (d.get('A')==pA_in and d.get('B')==pB_in) or (d.get('A')==pB_in and d.get('B')==pA_in)]
        suggested = "A"
        if relevant:
            last_s = sorted(relevant, key=lambda x: x.get('set_num', 1))[-1]
            next_s_num = last_s.get('set_num', 1) + 1
            f_set = next((s for s in sorted(relevant, key=lambda x: x.get('set_num', 1)) if s.get('set_num')==1), last_s)
            f_start = f_set.get('starter', "A")
            if f_set.get('A') != pA_in: f_start = "B" if f_start == "A" else "A"
            suggested = f_start if next_s_num % 2 == 1 else ("B" if f_start == "A" else "A")
        final_s = st.radio("Podává v tomto setu:", ["A", "B"], index=0 if suggested=="A" else 1)

    if pA_in and pB_in:
        probA, prob_over = predict_advanced(pA_in, pB_in, final_s, current_elos, serve_stats, h2h_data)
        st.write(f"Šance {pA_in}: **{round(probA*100)}%** | Šance {pB_in}: **{round((1-probA)*100)}%**")
        st.write(f"Pravděpodobnost Over 18.5: **{round(prob_over*100)}%**")

with t3:
    current_elos, _, _ = calculate_advanced_stats()
    for r, (n, v) in enumerate(sorted(current_elos.items(), key=lambda x: x[1], reverse=True)):
        st.write(f"{r+1}. **{n}** — {int(v)} pts")

with t4:
    st.subheader("⚙️ Správa Historie")
    for i in range(len(st.session_state.data)-1, -1, -1):
        d = st.session_state.data[i]
        name_A, name_B = d.get('A', 'Neznámý'), d.get('B', 'Neznámý')
        score, s_num, starter = d.get('score', '0:0'), d.get('set_num', 1), d.get('starter', 'A')
        ts_val = datetime.datetime.fromisoformat(d.get('timestamp', datetime.datetime.now().isoformat()))

        with st.expander(f"📝 {ts_val.strftime('%d.%m.')} | {name_A} vs {name_B} ({score})"):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                edit_score = st.text_input("Skóre", score, key=f"sc_{i}")
                edit_date = st.date_input("Datum", ts_val.date(), key=f"dt_{i}")
            with col_e2:
                edit_starter = st.selectbox("Podání", ["A", "B"], index=0 if starter=="A" else 1, key=f"st_{i}")
                if st.button("💾 Uložit", key=f"sv_{i}"):
                    st.session_state.data[i]['score'] = edit_score
                    st.session_state.data[i]['starter'] = edit_starter
                    # Uložíme nové datum se zachováním času
                    new_ts = datetime.datetime.combine(edit_date, ts_val.time())
                    st.session_state.data[i]['timestamp'] = new_ts.isoformat()
                    try:
                        sa, sb = map(int, edit_score.split(':'))
                        st.session_state.data[i]['win'] = 1 if sa > sb else 0
                    except: pass
                    save_data(st.session_state.data)
                    st.rerun()
                if st.button("🗑️ Smazat", key=f"dl_{i}"):
                    st.session_state.data.pop(i)
                    save_data(st.session_state.data)
                    st.rerun()
