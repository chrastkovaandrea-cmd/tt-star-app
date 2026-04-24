import streamlit as st
import json
import os
from collections import Counter

DATA_FILE="data.json"

# LOAD DATA
if os.path.exists(DATA_FILE):
    with open(DATA_FILE,"r") as f:
        data=json.load(f)
else:
    data=[]

def save():
    with open(DATA_FILE,"w") as f:
        json.dump(data,f)

st.title("🏓 TT STAR PRO MODEL")

# =========================
# ADD FULL MATCH TRAINING
# =========================

st.subheader("📥 Add training match")

block=st.text_area(
"Paste match like:",
"""Novák vs Černý
1.66 vs 1.89
3:1
11:9,10:12,11:8,11:7"""
)

if st.button("Save match"):

    try:

        lines=block.strip().split("\n")

        players=lines[0]
        odds=lines[1]
        sets=lines[2]
        scores=lines[3]

        A,B=players.split("vs")
        oddsA,oddsB=odds.split("vs")

        A=A.strip()
        B=B.strip()

        diff=abs(float(oddsA)-float(oddsB))

        for s in scores.split(","):

            a,b=s.split(":")

            data.append({
                "A":A,
                "B":B,
                "score":f"{a}:{b}",
                "points":int(a)+int(b),
                "diff":diff,
                "sets":sets
            })

        save()

        st.success("✔ match saved")

    except:

        st.error("Format error")

# =========================
# PREDICTION
# =========================

st.subheader("📊 Prediction")

playerA=st.text_input("Player A")
playerB=st.text_input("Player B")

oddsA=st.number_input("Odds A",value=1.8)
oddsB=st.number_input("Odds B",value=2.0)

def score_model(A,B):

    scores=[x["score"] for x in data
    if x["A"]==A or x["B"]==A
    or x["A"]==B or x["B"]==B]

    return Counter(scores)

model=score_model(playerA,playerB)

if len(model)>0:

    total=sum(model.values())

    st.write("Most likely set scores:")

    for s,c in model.most_common(6):

        prob=c/total

        st.write(s,"→",round(prob*100,1),"%")

# =========================
# OVER UNDER
# =========================

points=[x["points"] for x in data]

if len(points)>10:

    line=st.number_input("Line example 18.5",value=18.5)

    over=sum(1 for x in points if x>line)/len(points)

    st.write("OVER:",round(over*100,1),"%")
    st.write("UNDER:",round((1-over)*100,1),"%")

# =========================
# EV CALCULATOR
# =========================

def implied_prob(odds):

    return 1/odds

pA=implied_prob(oddsA)

ev=(pA*oddsA)-1

st.subheader("💰 EV")

st.write("EV:",round(ev,3))

# =========================
# DATA SIZE INFO
# =========================

st.write("Stored sets:",len(data))
