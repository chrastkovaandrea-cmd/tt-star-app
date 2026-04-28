import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import pandas as pd

# --- 1. ZÁKLADNÍ NASTAVENÍ A DATA ---
DATA_FILE = "tt_star_ultra_v10.json"
BASE_RATING = 1500
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
                d = json.load(f)
                return d if isinstance(d, list) else []
        except: return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- 2. PARSERY (Vkládání dat) ---
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

def smart_extract_from_text(text):
    new_entries = []
    lines = text.split('\n')
    for line in lines:
        match = re.search(r'([A-ZÁ-ž\s\.]+)\s+([A-ZÁ-ž\s\.]+)\s+(\d:\d)', line, re.IGNORECASE)
        if match:
            pA, pB, score = normalize_name(match.group(1)), normalize_name(match.group(2)), match.group(3)
            if pA and pB and ":" in score:
                if not any(d['A'] == pA and d['B'] == pB and d['score'] == score for d in st.session_state.data[-500:]):
                    try:
                        s1, s2 = map(int, score.split(':'))
                        new_entries.append({"A": pA, "B": pB, "score": score, "win": 1 if s1 > s2 else 0, "timestamp": datetime.datetime.now().isoformat(), "source": "bulk"})
                    except: continue
    return new_entries

# --- 3. GLICKO-2 VÝPOČET ---
def calculate_glicko_stats():
    players = {}
    sorted_data = sorted(st.session_state.data, key=lambda x: x.get('timestamp', '0'))
    for entry in sorted_data:
        pA, pB, winA = entry.get("A"), entry.get("B"), entry.get("win", 0)
        if not pA or not pB: continue
        for p in [pA, pB]:
            if p not in players: players[p] = {"r": BASE_RATING, "rd": BASE_RD, "matches": 0}
        rA, rdA, rB, rdB = players[pA]["r"], players[pA]["rd"], players[pB]["r"], players[pB]["rd"]
        expected_A = 1 / (1 + 10 ** ((rB - rA) / 400))
        shiftA = (rdA / 10) * (winA - expected_A)
        shiftB = (rdB / 10) * ((1 - winA) - (1 - expected_A))
        players[pA]["r"], players[pB]["r"] = rA + shiftA, rB + shiftB
        players[pA]["rd"], players[pB]["rd"] = max(30, rdA - 4), max(30, rdB - 4)
        players[pA]["matches"] += 1; players[pB]["matches"] += 1
    return players

# --- 4. UI STREAMLIT ---
st.set_page_config(page_title="TT STAR MASTER 11.5", layout="wide")
st.title("🏓 TT STAR ANALYTIK")

tabs = st.tabs(["📥 Vložit Set", "🌐 Archivní Vklad", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

p_stats = calculate_glicko_stats()

# T1: VLOŽIT SET
with tabs[0]:
    st.subheader("Ruční vklad jednoho setu")
    raw_in = st.text_area("Vložte text zápasu z Tipsportu:", height=100)
    res = parse_live_text(raw_in) if raw_in else None
    c1, c2, c3 = st.columns(3)
    with c1: m_date = st.date_input("Datum:", datetime.date.today())
    with c2: m_set = st.number_input("Set číslo:", 1, 5, value=res['set_num'] if res else 1)
    with c3: m_serve = st.selectbox("Podával první:", ["A", "B"], index=0 if (res and res['starter']=="A") else 1)
    if st.button("🚀 ULOŽIT SET"):
        if res:
            dt = datetime.datetime.combine(m_date, datetime.datetime.now().time())
            st.session_state.data.append({"A": res["A"], "B": res["B"], "score": res["score"], "win": res["win"], "starter": m_serve, "set_num": m_set, "timestamp": dt.isoformat(), "source": "manual"})
            save_data(st.session_state.data)
            st.success("Set uložen!"); st.rerun()

# T2: ARCHIVNÍ VKLAD
with tabs[1]:
    st.subheader("Hromadný vklad z webu (Results)")
    bulk_text = st.text_area("Sem vlož zkopírovaný text z TT Star:", height=200)
    if st.button("📥 ZPRACOVAT A PŘIDAT VŠE"):
        extracted = smart_extract_from_text(bulk_text)
        st.session_state.data.extend(extracted)
        save_data(st.session_state.data)
        st.success(f"Přidáno {len(extracted)} zápasů!"); st.rerun()

# T3: PREDIKCE
with tabs[2]:
    st.subheader("Predikce zápasu")
    all_p = sorted(list(p_stats.keys()))
    if len(all_p) >= 2:
        c1, c2 = st.columns(2)
        with c1: p_a = st.selectbox("Hráč A:", all_p); odds_a = st.number_input("Kurz na A:", value=1.85)
        with c2: p_b = st.selectbox("Hráč B:", all_p)
        if p_a != p_b:
            prob = 1 / (1 + 10 ** ((p_stats[p_b]['r'] - p_stats[p_a]['r']) / 400))
            st.metric(f"Šance {p_a}", f"{int(prob*100)}%")
            val = (prob * odds_a) - 1
            if val > 0: st.success(f"VALUE: +{val*100:.1f}%")
            else: st.error("BEZ VALUE")
    else: st.warning("Databáze je prázdná.")

# T4: ŽEBŘÍČEK
with tabs[3]:
    st.subheader("Žebříček hráčů")
    if p_stats:
        s_p = sorted(p_stats.items(), key=lambda x: x[1]['r'], reverse=True)
        df = pd.DataFrame([{"Jméno": k, "Rating": int(v['r']), "Zápasy": v['matches']} for k, v in s_p])
        st.dataframe(df, use_container_width=True)

# T5: HISTORIE & ZÁLOHA
with tabs[4]:
    st.subheader("📜 Historie a Úpravy")
    if st.session_state.data:
        rev_data = list(enumerate(st.session_state.data))
        rev_data.reverse()
        for idx, entry in rev_data[:15]:
            with st.expander(f"{entry['A']} vs {entry['B']} ({entry['score']})"):
                c1, c2, c3 = st.columns(3)
                enA = c1.text_input("Hráč A", entry['A'], key=f"histA_{idx}")
                enB = c2.text_input("Hráč B", entry['B'], key=f"histB_{idx}")
                enS = c3.text_input("Skóre", entry['score'], key=f"histS_{idx}")
                cc1, cc2 = st.columns(2)
                if cc1.button("Uložit změny", key=f"saveb_{idx}"):
                    st.session_state.data[idx].update({"A": normalize_name(enA), "B": normalize_name(enB), "score": enS})
                    save_data(st.session_state.data); st.rerun()
                if cc2.button("Smazat", key=f"delb_{idx}"):
                    st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()

    st.divider()
    st.download_button("📥 STÁHNOUT CELOU DATABÁZI", json.dumps(st.session_state.data, indent=4), "tt_full.json")
    up_file = st.file_uploader("Nahrát zálohu")
    if up_file:
        st.session_state.data = json.load(up_file)
        save_data(st.session_state.data); st.rerun()
