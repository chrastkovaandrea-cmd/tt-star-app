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
# ADD MATCH TRAINING
# =========================

st.subheader("📥 Add training match")

block=st.text_area(
"Paste match:",
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

            first_point="A" if int(a)>0 else "B"
            last_point="A" if int(a)>int(b) else "B"

            parity="even" if (int(a)+int(b))%2==0 else "odd"

            data.append({
                "A":A,
                "B":B,
                "score":f"{a}:{b}",
                "points":int(a)+int(b),
                "diff":diff,
                "sets":sets,
                "first_point":first_point,
                "last_point":last_point,
                "parity":parity
            })

        save()

        st.success("✔ match saved")

    except:

        st.error("Format error")

# =========================
# PLAYER INPUT
# =========================

st.subheader("📊 Prediction")

playerA=st.text_input("Player A")
playerB=st.text_input("Player B")

oddsA=st.number_input("Odds A",value=1.8)
oddsB=st.number_input("Odds B",value=2.0)

# =========================
# SCORE MODEL
# =========================

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
# FIRST POINT MODEL
# =========================

first_points=[x["first_point"] for x in data
if x["A"]==playerA or x["B"]==playerA
or x["A"]==playerB or x["B"]==playerB]

if len(first_points)>10:

    pA=first_points.count("A")/len(first_points)

    st.subheader("🎯 First point probability")

    st.write(playerA,"→",round(pA*100,1),"%")
    st.write(playerB,"→",round((1-pA)*100,1),"%")

# =========================
# LAST POINT MODEL (11th)
# =========================

last_points=[x["last_point"] for x in data
if x["A"]==playerA or x["B"]==playerA
or x["A"]==playerB or x["B"]==playerB]

if len(last_points)>10:

    pA=last_points.count("A")/len(last_points)

    st.subheader("🏁 Last point probability")

    st.write(playerA,"→",round(pA*100,1),"%")
    st.write(playerB,"→",round((1-pA)*100,1),"%")

# =========================
# EVEN / ODD MODEL
# =========================

parity=[x["parity"] for x in data]

if len(parity)>10:

    even=parity.count("even")/len(parity)

    st.subheader("⚖️ Even / Odd total points")

    st.write("Even →",round(even*100,1),"%")
    st.write("Odd →",round((1-even)*100,1),"%")

# =========================
# OVER / UNDER MODEL
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
# DATA INFO
# =========================

st.write("Stored sets:",len(data))
