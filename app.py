import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import pandas as pd

# --- 1. NASTAVENÍ ---
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

# --- 2. PARSERY ---
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
                if not any(d['A'] == pA and d['B'] == pB and d['score'] == score for d in st.session_state.data[-300:]):
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

# --- 4. UI ---
st.set_page_config(page_title="TT STAR ULTRA v11.3", layout="wide")
st.title("🏓 TT STAR - MASTER ANALYTIK")

tabs = st.tabs(["📥 Vložit Set", "🌐 Archivní Vklad", "🔮 Predikce", "🏆 Žebříček", "⚙️ Historie & Záloha"])

p_stats = calculate_glicko_stats()

with tabs[0]: 
    st.subheader("Detailní vklad setu (Tipsport)")
    raw_in = st.text_area("Vložte text:", height=100)
    res = parse_live_text(raw_in) if raw_in else None
    col1, col2, col3 = st.columns(3)
    with col1: m_date = st.date_input("Datum:", datetime.date.today())
    with col2: m_set = st.number_input("Set č.:", 1, 5, value=res['set_num'] if res else 1)
    with col3: m_serve = st.selectbox("Podával jako první:", ["A", "B"], index=0 if (res and res['starter']=="A") else 1)
    if st.button("🚀 ULOŽIT SET"):
        if res:
            dt = datetime.datetime.combine(m_date, datetime.datetime.now().time())
            st.session_state.data.append({"A": res["A"], "B": res["B"], "score": res["score"], "win": res["win"], "starter": m_serve, "set_num": m_set, "timestamp": dt.isoformat(), "source": "manual"})
            save_data(st.session_state.data)
            st.success("Uloženo!")
            st.rerun()

with tabs[1]:
    st.subheader("Hromadný vklad z webu")
    bulk_text = st.text_area("Vlož zkopírovaný text z TT Star Results:", height=200)
    if st.button("📥 ZPRACOVAT A PŘIDAT"):
        extracted = smart_extract_from_text(bulk_text)
        st.session_state.data.extend(extracted)
        save_data(st.session_state.data)
        st.success(f"Přidáno {len(extracted)} zápasů!")
        st.rerun()

with tabs[4]: 
    st.subheader("📜 Historie a správa dat")
    # Historie s úpravami a mazáním
    if st.session_state.data:
        reversed_data = list(enumerate(st.session_state.data))
        reversed_data.reverse()
        for idx, entry in reversed_data[:15]:
            with st.expander(f"{entry['A']} vs {entry['B']} ({entry['score']}) - {entry.get('source','?')}"):
                c1, c2, c3 = st.columns(3)
                editA = c1.text_input("Hráč A", entry['A'], key=f"eA_{idx}")
                editB = c2.text_input("Hráč B", entry['B'], key=f"eB_{idx}")
                editS = c3.text_input("Skóre", entry['score'], key=f"eS_{idx}")
                cc1, cc2 = st.columns(2)
                if cc1.button("💾 Uložit", key=f"s_{idx}"):
                    st.session_state.data[idx].update({"A": normalize_name(editA), "B": normalize_name(editB), "score": editS})
                    save_data(st.session_state.data); st.rerun()
                if cc2.button("🗑️ Smazat", key=f"d_{idx}"):
                    st.session_state.data.pop(idx); save_data(st.session_state.data); st.rerun()

    st.divider()
    st.subheader("💾 Export a Import (Záloha celé databáze)")
    st.info(f"Aktuálně je v databázi celkem {len(st.session_state.data)} záznamů.")
    
    # Tlačítko pro stažení VŠECH dat (ručních i z archivu)
    full_json = json.dumps(st.session_state.data, indent=4)
    st.download_button(
        label="📥 STÁHNOUT KOMPLETNÍ DATABÁZI (JSON)",
        data=full_json,
        file_name=f"tt_star_full_backup_{datetime.date.today()}.json",
        mime="application/json"
    )

    if st.button("💾 PEVNĚ ULOŽIT NA SERVER"):
        save_data(st.session_state.data)
        st.success("Všechna data byla uložena do souboru na serveru.")

    st.divider()
    up = st.file_uploader("Nahrát databázi ze souboru (Obnova):", type="json")
    if up:
        st.session_state.data = json.load(up)
        save_data(st.session_state.data)
        st.success("Databáze byla úspěšně obnovena!")
        st.rerun()
