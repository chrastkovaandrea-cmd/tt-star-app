import streamlit as st
import json, os, re, datetime, math, unicodedata
import pandas as pd
import io
import random
from collections import Counter

# =====================================================
# KONFIG
# =====================================================

DATA_FILE = "tt_star_ultra_v18.json"

st.set_page_config(
    page_title="TT STAR ANALYTIK PRO",
    page_icon="🏓",
    layout="wide"
)

# =====================================================
# SESSION
# =====================================================

if "txt_area" not in st.session_state:
    st.session_state.txt_area = ""

if "success_msg" not in st.session_state:
    st.session_state.success_msg = ""

if "txt_reset" not in st.session_state:
    st.session_state.txt_reset = False

# =====================================================
# NORMALIZE
# =====================================================

def normalize_name(name):

    if not name or pd.isna(name):
        return ""

    name = str(name).strip().upper()

    name = unicodedata.normalize(
        'NFKD',
        name
    ).encode(
        'ASCII',
        'ignore'
    ).decode('ASCII')

    name = re.sub(r'^[A-Z]\.\s*', '', name)

    return re.sub(
        r'[^A-Z\s]',
        '',
        name
    ).strip()

# =====================================================
# SAVE
# =====================================================

def save_data(data):

    with open(DATA_FILE, "w") as f:

        json.dump(
            data,
            f,
            indent=4
        )

    st.cache_data.clear()

# =====================================================
# LOAD
# =====================================================

if 'data' not in st.session_state:

    if os.path.exists(DATA_FILE):

        try:

            with open(DATA_FILE, "r") as f:

                st.session_state.data = json.load(f)

        except:

            st.session_state.data = []

    else:

        st.session_state.data = []

# =====================================================
# GLICKO ENGINE
# =====================================================

@st.cache_data(show_spinner="Přepočítávám žebříček...")
def get_ratings(data_list):

    ratings = {}

    BASE_R = 1500
    BASE_RD = 350

    if not data_list:
        return {}

    sorted_data = sorted(
        data_list,
        key=lambda x: str(x.get('timestamp', ''))
    )

    q = math.log(10) / 400

    for d in sorted_data:

        pA = d.get('A')
        pB = d.get('B')
        score = d.get('score')

        if not pA or not pB:
            continue

        pA = normalize_name(pA)
        pB = normalize_name(pB)

        for p in [pA, pB]:

            if p not in ratings:

                ratings[p] = {
                    "r": 1500,
                    "rd": 350,
                    "count": 0
                }

        try:

            ptsA, ptsB = map(
                int,
                str(score).split(':')
            )

            actualA = 1 if ptsA > ptsB else 0

            rA = ratings[pA]["r"]
            rB = ratings[pB]["r"]

            rdA = ratings[pA]["rd"]
            rdB = ratings[pB]["rd"]

            gB = 1 / math.sqrt(
                1 + 3 * ((q * rdB / math.pi) ** 2)
            )

            expA = 1 / (1 + 10 ** (gB * (rA - rB) / -400))

            diff_weight = 1 + (min(abs(ptsA - ptsB), 8) / 12)

            d2 = 1 / (q**2 * gB**2 * expA * (1-expA))

            change = (
                q / ((1 / rdA**2) + (1 / d2))
            ) * gB * (actualA - expA)

            ratings[pA]["r"] += change * diff_weight
            ratings[pB]["r"] -= change * diff_weight

            ratings[pA]["rd"] = max(35, rdA * 0.97)
            ratings[pB]["rd"] = max(35, rdB * 0.97)

            ratings[pA]["count"] += 1
            ratings[pB]["count"] += 1

        except:
            continue

    return ratings

# =====================================================
# MONTE CARLO
# =====================================================

def simulate_set_live(pA, startA, startB):

    a = startA
    b = startB

    while True:

        if random.random() < pA:
            a += 1
        else:
            b += 1

        if (a >= 11 or b >= 11) and abs(a - b) >= 2:
            return a, b

def monte_carlo_live(pA, scoreA, scoreB, sims=3000):

    results = []

    for _ in range(sims):
        sa, sb = simulate_set_live(pA, scoreA, scoreB)
        results.append(f"{sa}:{sb}")

    c = Counter(results)
    total = sum(c.values())

    return {k: v/total for k, v in c.items()}

def calculate_live_probability(probs):

    pA = 0

    for s, p in probs.items():

        sa, sb = map(int, s.split(':'))

        if sa > sb:
            pA += p

    return pA

# =====================================================
# TABS
# =====================================================

t1, t2, t3, t4 = st.tabs([
    "📥 Vkládání",
    "🔮 Predikce",
    "🏆 Žebříček",
    "⚙️ Správa"
])

# =====================================================
# VKLÁDÁNÍ (FIXED DELETE)
# =====================================================

with t1:

    st.subheader("Ruční vložení zápasu")

    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)

    raw_in = st.text_area(
        "Vlož zápas:",
        height=120,
        key="txt_area_" + str(st.session_state.txt_reset)
    )

    c1, c2 = st.columns(2)

    with c1:

        if st.button("🗑️ SMAZAT TEXT"):

            st.session_state.txt_reset = not st.session_state.txt_reset
            st.session_state.success_msg = ""
            st.rerun()

    with c2:

        if st.button("🚀 ULOŽIT"):

            if raw_in:

                try:

                    parts = raw_in.split('|')
                    names = parts[0].split('-')

                    p1 = normalize_name(names[0])
                    p2 = normalize_name(names[1])

                    sets_raw = re.search(r'\((.*?)\)', parts[1]).group(1)

                    sets = [s.strip() for s in sets_raw.split(',')]

                    for s in sets:

                        st.session_state.data.append({
                            "A": p1,
                            "B": p2,
                            "score": s.replace('-', ':'),
                            "timestamp": datetime.datetime.now().isoformat()
                        })

                    save_data(st.session_state.data)

                    st.session_state.success_msg = f"✅ {p1} vs {p2} uložen"
                    st.session_state.txt_reset = not st.session_state.txt_reset

                    st.rerun()

                except Exception as e:
                    st.error(e)

# =====================================================
# PREDIKCE
# =====================================================

with t2:

    ratings = get_ratings(st.session_state.data)

    if ratings:

        players = sorted(list(ratings.keys()))

        c1, c2 = st.columns(2)

        selA = c1.selectbox("Hráč A", players)
        selB = c2.selectbox("Hráč B", players, index=min(1, len(players)-1))

        if selA != selB:

            rA = ratings[selA]["r"]
            rB = ratings[selB]["r"]

            pA = 1 / (1 + 10**((rB - rA)/400))

            st.subheader("🔥 LIVE ENGINE")

            lc1, lc2 = st.columns(2)

            liveA = lc1.number_input(f"{selA} body", 0, 50, 0)
            liveB = lc2.number_input(f"{selB} body", 0, 50, 0)

            probs = monte_carlo_live(pA, liveA, liveB, sims=4000)

            winA = calculate_live_probability(probs)
            winB = 1 - winA

            st.markdown("## 🏆 LIVE WIN PROBABILITY")

            c1, c2 = st.columns(2)

            c1.metric(selA, f"{winA*100:.1f}%")
            c2.metric(selB, f"{winB*100:.1f}%")

# =====================================================
# ŽEBŘÍČEK
# =====================================================

with t3:

    ratings = get_ratings(st.session_state.data)

    if ratings:

        df = pd.DataFrame([
            {
                "Hráč": k,
                "Rating": int(v["r"]),
                "RD": int(v["rd"]),
                "Zápasy": v["count"]
            }
            for k, v in ratings.items()
        ])

        st.dataframe(
            df.sort_values("Rating", ascending=False),
            use_container_width=True,
            hide_index=True
        )

# =====================================================
# SPRÁVA (FIXED UPLOAD + EXPORT)
# =====================================================

with t4:

    st.subheader("⚙️ Správa dat")

    st.write(f"Počet setů: {len(st.session_state.data)}")

    # ================= IMPORT (VRÁCENO ZPĚT) =================
    up = st.file_uploader("📥 Import CSV", type=None)

    if up:

        try:

            bytes_data = up.read()

            try:
                text_data = bytes_data.decode('utf-8-sig')
            except:
                text_data = bytes_data.decode('cp1250')

            df = pd.read_csv(
                io.StringIO(text_data),
                sep=None,
                engine='python'
            )

            st.session_state.data = df.where(pd.notnull(df), None).to_dict('records')

            save_data(st.session_state.data)

            st.success("✅ Import hotov")

        except Exception as e:
            st.error(e)

    # ================= EXPORT =================
    if st.session_state.data:

        df_ex = pd.DataFrame(st.session_state.data)

        csv_b = io.StringIO()

        df_ex.to_csv(csv_b, index=False, encoding='utf-8-sig')

        st.download_button(
            "💾 STÁHNOUT CSV",
            data=csv_b.getvalue(),
            file_name=f"tt_backup_{datetime.datetime.now().strftime('%d_%m_%Y')}.csv",
            use_container_width=True
        )

    st.write("---")

    if st.button("🧨 SMAZAT VŠE"):

        st.session_state.data = []
        save_data([])
        st.rerun()
