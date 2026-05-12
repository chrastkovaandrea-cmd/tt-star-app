import streamlit as st
import json
import os
import re
import datetime
import math
import unicodedata
import pandas as pd
import io

# =====================================================
# KONFIGURACE
# =====================================================

DATA_FILE = "tt_star_ultra_v17.json"

st.set_page_config(
    page_title="TT STAR ANALYTIK PRO",
    page_icon="🏓",
    layout="wide"
)

# =====================================================
# FUNKCE
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


# =====================================================
# SESSION STATE
# =====================================================

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


# =====================================================
# RATING SYSTÉM
# =====================================================

@st.cache_data(show_spinner="Přepočítávám žebříček...")
def get_ratings(data_list):

    ratings = {}

    BASE_RATING = 1500

    if not data_list:
        return {}

    for match in data_list:

        try:

            pA = normalize_name(match.get("A"))
            pB = normalize_name(match.get("B"))
            score = str(match.get("score"))

            if ":" not in score:
                continue

            ptsA, ptsB = map(int, score.split(":"))

            if pA not in ratings:
                ratings[pA] = {
                    "r": BASE_RATING,
                    "count": 0
                }

            if pB not in ratings:
                ratings[pB] = {
                    "r": BASE_RATING,
                    "count": 0
                }

            diff = abs(ptsA - ptsB)

            gain = 10 + diff

            if ptsA > ptsB:

                ratings[pA]["r"] += gain
                ratings[pB]["r"] -= gain

            else:

                ratings[pB]["r"] += gain
                ratings[pA]["r"] -= gain

            ratings[pA]["count"] += 1
            ratings[pB]["count"] += 1

        except:
            continue

    return ratings


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
# VKLÁDÁNÍ
# =====================================================

with t1:

    st.subheader("Ruční vkládání zápasu")

    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)

    raw_in = st.text_area(
        "Vlož text zápasu:",
        height=100,
        key="txt_area"
    )

    c1, c2 = st.columns(2)

    with c1:

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

    with c2:

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

                    ts = datetime.datetime.now().strftime("%d.%m. %H:%M")

                    temp_matches = []

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

                        clean_score = (
                            s.strip()
                            .replace("-", ":")
                        )

                        temp_matches.append({
                            "A": p1_n,
                            "B": p2_n,
                            "score": clean_score,
                            "starter": starter,
                            "timestamp": ts,
                            "odds": f"{o1}/{o2}"
                        })

                    st.session_state.data.extend(temp_matches)

                    save_data(st.session_state.data)

                    st.session_state.txt_area = ""

                    st.session_state.success_msg = (
                        f"✅ Zápas {p1_n} vs {p2_n} uložen"
                    )

                    st.rerun()

                except Exception as e:

                    st.error(f"Chyba: {e}")


# =====================================================
# PREDIKCE
# =====================================================

with t2:

    ratings = get_ratings(st.session_state.data)

    if ratings:

        players = sorted(ratings.keys())

        c1, c2 = st.columns(2)

        selA = c1.selectbox(
            "Hráč A",
            players
        )

        selB = c2.selectbox(
            "Hráč B",
            players,
            index=min(1, len(players)-1)
        )

        if selA != selB:

            rA = ratings[selA]["r"]
            rB = ratings[selB]["r"]

            total = rA + rB

            probA = rA / total
            probB = rB / total

            winner = selA if probA > probB else selB

            percent = max(probA, probB) * 100

            st.markdown(
                f"## 🏆 Predikovaný vítěz: **{winner}**"
            )

            st.markdown(
                f"### Pravděpodobnost výhry: {percent:.1f}%"
            )

            st.write("---")

            st.metric(
                f"Síla {selA}",
                int(rA)
            )

            st.metric(
                f"Síla {selB}",
                int(rB)
            )

            st.info(
                f"Férové kurzy → "
                f"{selA}: {1/probA:.2f} | "
                f"{selB}: {1/probB:.2f}"
            )

    else:

        st.info("Zatím nejsou vložená data.")


# =====================================================
# ŽEBŘÍČEK
# =====================================================

with t3:

    ratings = get_ratings(st.session_state.data)

    if ratings:

        table = []

        for player, values in ratings.items():

            table.append({
                "Hráč": player,
                "Rating": int(values["r"]),
                "Zápasů": values["count"]
            })

        df = pd.DataFrame(table)

        df = df.sort_values(
            "Rating",
            ascending=False
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("Zatím nejsou vložená data.")


# =====================================================
# SPRÁVA
# =====================================================

with t4:

    st.subheader("⚙️ Správa, Import a Export")

    # =================================================
    # POSLEDNÍCH 5 ZÁPASŮ
    # =================================================

    st.markdown("## 🕒 Posledních 5 vložených zápasů")

    if st.session_state.data:

        last_matches = st.session_state.data[-5:]

        last_matches.reverse()

        df_last = pd.DataFrame(last_matches)

        st.dataframe(
            df_last,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("Žádné zápasy.")

    st.write("---")

    c_i, c_e = st.columns(2)

    # =================================================
    # IMPORT
    # =================================================

    with c_i:

        st.markdown("### 📥 Import")

        up = st.file_uploader(
            "Nahrát CSV",
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

                st.success("Import dokončen")

                st.rerun()

            except Exception as e:

                st.error(f"Chyba importu: {e}")

    # =================================================
    # EXPORT
    # =================================================

    with c_e:

        st.markdown("### 📤 Export")

        if st.session_state.data:

            df_ex = pd.DataFrame(
                st.session_state.data
            )

            csv_buffer = io.StringIO()

            df_ex.to_csv(
                csv_buffer,
                index=False,
                encoding='utf-8-sig'
            )

            st.download_button(
                "💾 STÁHNOUT CSV",
                data=csv_buffer.getvalue(),
                file_name=f"tt_star_backup_{datetime.datetime.now().strftime('%d_%m')}.csv",
                use_container_width=True
            )

    st.write("---")

    # =================================================
    # SMAZÁNÍ
    # =================================================

    if st.button(
        "🧨 SMAZAT VŠECHNA DATA",
        use_container_width=True
    ):

        st.session_state.data = []

        save_data([])

        st.rerun()
