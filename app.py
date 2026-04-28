import streamlit as st
import json, os, datetime, math, re, unicodedata

DATA_FILE = "tt_data.json"
BASE_ELO = 1500
K = 32

# =========================
# NORMALIZE
# =========================
def norm(x):
    x = unicodedata.normalize('NFKD', x).encode('ASCII','ignore').decode()
    return x.strip().upper()

# =========================
# LOAD / SAVE
# =========================
def load():
    if os.path.exists(DATA_FILE):
        return json.load(open(DATA_FILE))
    return []

def save(d):
    json.dump(d, open(DATA_FILE,"w"))

if "data" not in st.session_state:
    st.session_state.data = load()

# =========================
# ELO
# =========================
def calc_elo():
    elo={}
    for d in st.session_state.data:
        A,B=d["A"],d["B"]
        w=d["win"]

        if A not in elo: elo[A]=BASE_ELO
        if B not in elo: elo[B]=BASE_ELO

        EA=1/(1+10**((elo[B]-elo[A])/400))
        elo[A]+=K*(w-EA)
        elo[B]+=K*((1-w)-(1-EA))
    return elo

# =========================
# PARSER (Tipsport)
# =========================
def parse(text):

    lines=[l.strip() for l in text.split("\n") if l.strip()]

    if len(lines)<3:
        return None

    A=norm(lines[0])
    B=norm(lines[1])

    scores=re.findall(r'(\d+):(\d+)', text)

    if not scores:
        return None

    last=scores[-1]

    return {
        "A":A,
        "B":B,
        "score":f"{last[0]}:{last[1]}",
        "win":1 if int(last[0])>int(last[1]) else 0
    }

# =========================
# PREDIKCE
# =========================
def prob(A,B,elo):
    return 1/(1+10**((elo.get(B,1500)-elo.get(A,1500))/400))

# =========================
# UI
# =========================
st.title("🏓 TT STAR PRO")

t1,t2,t3,t4=st.tabs(["📥 Vložit","🔮 Predikce","🏆 Žebříček","⚙️ Historie"])

# =========================
# TAB 1
# =========================
with t1:

    txt=st.text_area("Vlož text z Tipsportu")

    if st.button("➕ Načíst"):
        r=parse(txt)

        if r:
            st.session_state.tmp=r
            st.success("OK")

    if "tmp" in st.session_state:

        r=st.session_state.tmp

        st.write(r)

        if
