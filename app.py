import streamlit as st
import json
import os
import re
import datetime
import math
import unicodedata
import pandas as pd
import io

# =========================================================
# KONFIGURACE
# =========================================================

DATA_FILE = "tt_star_ultra_v17.json"

st.set_page_config(
    page_title="TT STAR ANALYTIK PRO",
    page_icon="🏓",
    layout="wide"
)

# =========================================================
# FUNKCE
# =========================================================

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

    return re.sub(r'[^A-Z\s]', '', name).strip()


def save_data(data):

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )

    st.cache_data.clear()


# =========================================================
# SESSION STATE
# =========================================================

if "data" not in st.session_state:

    if os.path.exists(DATA_FILE):

        try:

            with open(DATA_FILE, "r", encoding="utf-8") as f:
                st.session_state.data = json.load(f)

        except:
            st.session_state.data = []

    else:
        st.session_state.data = []


if "txt_area" not in st.session_state:
    st.session_state.txt_area = ""

if "success_msg" not in st.session_state:
    st.session_state.success_msg = ""


# =========================================================
# GLICKO RATING
# =========================================================

@st.cache_data(show_spinner="Přepočítávám žebříček...")
def get_ratings(data_list):

    ratings = {}

    BASE_R = 1500
    BASE_RD = 350
    BASE_VOL = 0.06

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

        if not pA or not pB or ":" not in str(score):
            continue

        pA = normalize_name(pA)
        pB = normalize_name(pB)

        for p in [pA, pB]:

            if p not in ratings:

                ratings[p] = {
                    "r": BASE_R,
                    "rd": BASE_RD,
                    "vol": BASE_VOL,
                    "count": 0
                }

        try:

            ptsA, ptsB = map(
                int,
                str(score).split(':')
            )

            actual_winA = 1 if ptsA > ptsB else 0

            win_weight = 1.0 + (
                min(abs(ptsA - ptsB), 9) / 20.0
            )

            rA = ratings[pA]["r"]
            rdA = ratings[pA]["rd"]

            rB = ratings[pB]["r"]
            rdB = ratings[pB]["rd"]

            gB = 1 / math.sqrt(
                1 + 3 * (q * rdB / math.pi) ** 2
            )

            expA = 1 / (
                1 + 10 ** (
                    gB * (rA - rB) / -400
                )
            )

            dA_inv = (
                q ** 2 *
                gB ** 2 *
                expA *
                (1 - expA)
            )

            ratings[pA]["r"] += (
                (
                    q / (
                        1 / rdA ** 2 + dA_inv
                    )
                )
                * gB
                * (actual_winA - expA)
                * win_weight
            )

            ratings[pA]["rd"] = max(
                30,
                math.sqrt(
                    1 / (
                        1 / rdA ** 2 + dA_inv
                    )
                )
            )

            ratings[pA]["count"] += 1

            gA = 1 / math.sqrt(
                1 + 3 * (q * rdA / math.pi) ** 2
            )

            dB_inv = (
                q ** 2 *
                gA ** 2 *
                expA *
                (1 - expA)
            )

            ratings[pB]["r"] += (
                (
                    q / (
                        1 / rdB ** 2 + dB_inv
                    )
                )
                * gA
                * (
                    (1 - actual_winA)
                    - (1 - expA)
                )
                * win_weight
            )

            ratings[pB]["rd"] = max(
                30,
                math.sqrt(
                    1 / (
                        1 / rdB ** 2 + dB_inv
                    )
                )
            )

            ratings[pB]["count"] += 1

        except:
            continue

    return ratings


# =========================================================
# TABS
# =========================================================

t1, t2, t3, t4 = st.tabs([
    "📥 Vkládání",
    "🔮 Predikce",
    "🏆 Žebříček",
    "⚙️ Správa"
])

# =========================================================
# VKLÁDÁNÍ
# =========================================================

with t1:

    st.subheader("Ruční vkládání zápasu")

    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)

    raw_in = st.text_area(
        "Vlož text zápasu:",
        height=100,
        key="txt_area"
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button("🗑️ VYMAZAT TEXT"):

            st.session_state.txt_area = ""
            st.rerun()

    m_first = st.selectbox(
        "Kdo podával v 1. SETU?",
        [
            "Hráč 1 (Horní)",
            "Hráč 2 (Dolní)"
        ]
    )

    with col2:

        if st.button("🚀 ULOŽIT ZÁPAS"):

            if raw_in:

                try:

                    parts = raw_in.split('|')

                    names = parts[0].split('-')

                    p1_n = normalize_name(names[0])
                    p2_n = normalize_name(names[1])

                    sets_raw = re.search(
                        r'\((.*?)\)',
                        parts[1]
                    ).group(1)

                    sets = [
                        s.strip()
                        for s in sets_raw.split(',')
                    ]

                    odds_raw = re.findall(
                        r'\d+\.\d+',
                        parts[-1]
                    )

                    if len(odds_raw) >= 2:
                        o1 = odds_raw[0]
                        o2 = odds_raw[1]
                    else:
                        o1 = "0"
                        o2 = "0"

                    ts = (
                        parts[2].strip()
                        if len(parts) > 2
                        else datetime.datetime.now().strftime("%d.%m. %H:%M")
                    )

                    temp_new_sets = []

                    for i, s in enumerate(sets):

                        if (i + 1) % 2 != 0:

                            starter = (
                                "A"
                                if "Hráč 1" in m_first
                                else "B"
                            )

                        else:

                            starter = (
                                "B"
                                if "Hráč 1" in m_first
                                else "A"
                            )

                        clean_score = s.strip().replace('-', ':')

                        temp_new_sets.append({
                            "A": p1_n,
                            "B": p2_n,
                            "score": clean_score,
                            "starter": starter,
                            "timestamp": ts,
                            "odds": f"{o1}/{o2}"
                        })

                    st.session_state.data.extend(temp_new_sets)

                    save_data(st.session_state.data)

                    st.session_state.txt_area = ""

                    st.session_state.success_msg = (
                        f"✅ Zápas {p1_n} - {p2_n} byl úspěšně uložen!"
                    )

                    st.rerun()

                except Exception as e:

                    st.error(f"Chyba: {e}")


# =========================================================
# PREDIKCE
# =========================================================

with t2:

    ratings = get_ratings(st.session_state.data)

    if ratings:

        player_list = sorted(list(ratings.keys()))

        c1, c2 = st.columns(2)

        selA = c1.selectbox(
            "Hráč A",
            player_list,
            key="sA"
        )

        selB = c2.selectbox(
            "Hráč B",
            player_list,
            index=min(1, len(player_list) - 1),
            key="sB"
        )

        co1, co2, co3 = st.columns(3)

        co1.number_input(
            f"Kurz {selA}",
            1.01,
            20.0,
            1.85
        )

        co2.number_input(
            f"Kurz {selB}",
            1.01,
            20.0,
            1.85
        )

        live_s = co3.radio(
            "Kdo začíná podávat (Live):",
            [selA, selB]
        )

        if selA != selB:

            rA = ratings[selA]
            rB = ratings[selB]

            q = math.log(10) / 400

            rd_c = math.sqrt(
                rA["rd"] ** 2 +
                rB["rd"] ** 2
            )

            g = 1 / math.sqrt(
                1 + 3 * (q * rd_c / math.pi) ** 2
            )

            p_base = 1 / (
                1 + 10 ** (
                    g * (rA["r"] - rB["r"]) / -400
                )
            )

            p_set = min(
                max(
                    p_base + (
                        0.05 if live_s == selA else -0.05
                    ),
                    0.05
                ),
                0.95
            )

            sc = {
                "3:0": p_set ** 3,
                "3:1": 3 * (p_set ** 3) * (1 - p_set),
                "3:2": 6 * (p_set ** 3) * ((1 - p_set) ** 2),
                "0:3": (1 - p_set) ** 3,
                "1:3": 3 * ((1 - p_set) ** 3) * p_set,
                "2:3": 6 * ((1 - p_set) ** 3) * (p_set ** 2)
            }

            probA = (
                sc["3:0"] +
                sc["3:1"] +
                sc["3:2"]
            )

            probB = 1 - probA

            best_res = max(sc, key=sc.get)

            st.markdown(
                f"## 🏆 Vítěz: "
                f"**{selA if probA > probB else selB}** "
                f"({max(probA, probB) * 100:.1f}%)"
            )

            st.subheader(
                f"📊 Nejpravděpodobnější výsledek: {best_res}"
            )

            st.info(
                f"Férové kurzy -> "
                f"{selA}: {1 / probA:.2f} | "
                f"{selB}: {1 / probB:.2f}"
            )


# =========================================================
# ŽEBŘÍČEK
# =========================================================

with t3:

    ratings = get_ratings(st.session_state.data)

    if ratings:

        df_view = pd.DataFrame([
            {
                "Hráč": k,
                "Rating": int(v["r"]),
                "Zápasů": v["count"]
            }
            for k, v in ratings.items()
        ])

        st.dataframe(
            df_view.sort_values(
                "Rating",
                ascending=False
            ),
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# SPRÁVA
# =========================================================

with t4:

    st.subheader("⚙️ Správa, Import a Export")

    st.markdown("## 🕒 Posledních 5 vložených zápasů")

    if st.session_state.data:

        last_matches = st.session_state.data[-5:]

        last_matches = list(reversed(last_matches))

        df_last = pd.DataFrame(last_matches)

        st.dataframe(
            df_last,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("Zatím nejsou vložené žádné zápasy.")

    st.write("---")

    c_i, c_e = st.columns(2)

    with c_i:

        st.markdown("### 📥 Import")

        up = st.file_uploader(
            "Nahrát soubor (CSV)",
            type=None
        )

        if up and st.button("✅ POTVRDIT IMPORT"):

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

                df.columns = [
                    str(c).strip()
                    for c in df.columns
                ]

                if 'A' not in df.columns:

                    df = df.rename(columns={
                        df.columns[0]: 'A',
                        df.columns[1]: 'B',
                        df.columns[2]: 'score'
                    })

                df['A'] = df['A'].apply(normalize_name)
                df['B'] = df['B'].apply(normalize_name)

                st.session_state.data = (
                    df.where(pd.notnull(df), None)
                    .to_dict('records')
                )

                save_data(st.session_state.data)

                st.success("Data byla úspěšně nahrána!")

                st.rerun()

            except Exception as e:

                st.error(f"Chyba při importu: {e}")

    with c_e:

        st.markdown("### 📤 Export")

        if st.session_state.data:

            df_ex = pd.DataFrame(st.session_state.data)

            csv_b = io.StringIO()

            df_ex.to_csv(
                csv_b,
                index=False,
                encoding='utf-8-sig'
            )

            st.download_button(
                "💾 STÁHNOUT ZÁLOHU (CSV)",
                data=csv_b.getvalue(),
                file_name=f"tt_star_backup_{datetime.datetime.now().strftime('%d_%m')}.csv",
                use_container_width=True
            )

    st.write("---")

    if st.button(
        "🧨 SMAZAT VŠECHNA DATA",
        use_container_width=True
    ):

        st.session_state.data = []

        save_data([])

        st.rerun()
