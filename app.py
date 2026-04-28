import streamlit as st
import json
import os
import random

DATA_FILE = "tt_data.json"

# =========================
# LOAD / SAVE
# =========================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

if "data" not in st.session_state:
    st.session_state.data = load_data()

# =========================
# POINT MODEL
# =========================
def point_prob(A, B):
    winsA = 0
    total = 0

    for d in st.session_state.data:
        if d["A"] == A or d["B"] == A:
            total += 1
            if d["A"] == A and d["win"] == 1:
                winsA += 1
            if d["B"] == A and d["win"] == 0:
                winsA += 1

    if total == 0:
        return 0.5

    return winsA / total

# =========================
# SIMULACE SETU
# =========================
def simulate_set(pA):

    a = 0
    b = 0

    while True:
        if random.random() < pA:
            a += 1
        else:
            b += 1

        if (a >= 11 or b >= 11) and abs(a - b) >= 2:
            return a, b

# =========================
# MONTE CARLO
# =========================
def monte_carlo(pA, sims=500):

    results = {}

    for _ in range(sims):
        a,b = simulate_set(pA)
        score = f"{a}:{b}"
        results[score] = results.get(score, 0) + 1

    total = sum(results.values())

    return sorted([(k, v/total) for k,v in results.items()],
                  key=lambda x: x[1],
                  reverse=True)[:5]

# =========================
# UI
# =========================
st.title("🏓 TT STAR LIVE EDGE")

tab1, tab2, tab3 = st.tabs(["➕ Data", "🔥 LIVE EDGE", "💾 Data"])

# =========================
# DATA
# =========================
with tab1:

    A = st.text_input("Hráč A")
    B = st.text_input("Hráč B")

    score = st.text_input("Skóre (např 11:8)")

    if st.button("ULOŽIT"):

        try:
            a,b = map(int, score.split(":"))
            win = 1 if a>b else 0

            st.session_state.data.append({
                "A": A.upper(),
                "B": B.upper(),
                "win": win
            })

            save_data(st.session_state.data)
            st.success("ULOŽENO")

        except:
            st.error("Chyba")

# =========================
# LIVE EDGE
# =========================
with tab2:

    st.subheader("LIVE predikce")

    A = st.text_input("Player A")
    B = st.text_input("Player B")

    score_live = st.text_input("Aktuální skóre (např 6:5)")

    odds = st.number_input("Kurz na A", 1.0, 10.0, 1.8)

    if A and B:

        pA = point_prob(A.upper(), B.upper())

        st.write("📊 Pravděpodobnost bodu:", round(pA,3))

        # SIMULACE
        sims = monte_carlo(pA)

        st.write("🎯 Nejčastější výsledky:")
        for s,p in sims:
            st.write(s, round(p*100,1), "%")

        # EV
        ev = pA * odds - 1

        st.write("💰 EV:", round(ev,3))

# =========================
# DATA MANAGEMENT
# =========================
with tab3:

    st.write("Počet:", len(st.session_state.data))

    st.download_button(
        "📥 Stáhnout",
        json.dumps(st.session_state.data),
        file_name="tt.json"
    )

    file = st.file_uploader("📤 Upload", type=["json"])

    if file:
        st.session_state.data = json.load(file)
        save_data(st.session_state.data)
        st.success("Nahráno")
