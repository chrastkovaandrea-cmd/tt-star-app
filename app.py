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

playerA=st.text_input("Player A")
playerB=st.text_input("Player B")

oddsA=st.number_input("Odds A",value=1.8)
oddsB=st.number_input("Odds B",value=2.0)

# LIVE SCORE
if "A" not in st.session_state:
    st.session_state.A=0

if "B" not in st.session_state:
    st.session_state.B=0

col1,col2=st.columns(2)

with col1:
    if st.button("+ point A"):
        st.session_state.A+=1

with col2:
    if st.button("+ point B"):
        st.session_state.B+=1

st.write("Score:",st.session_state.A,":",st.session_state.B)

# SCORE MODEL
def score_model(A,B):

    scores=[x["score"] for x in data
    if x["A"]==A or x["B"]==A
    or x["A"]==B or x["B"]==B]

    return Counter(scores)

model=score_model(playerA,playerB)

if len(model)>0:

    total=sum(model.values())

    st.subheader("📊 Score prediction")

    for s,c in model.most_common(6):

        prob=c/total

        st.write(s,"→",round(prob*100,1),"%")

# OVER UNDER MODEL
points=[x["points"] for x in data]

if len(points)>10:

    line=st.number_input("line (např 18.5)",value=18.5)

    over=sum(1 for x in points if x>line)/len(points)

    st.write("OVER:",round(over*100,1),"%")
    st.write("UNDER:",round((1-over)*100,1),"%")

# EV CALCULATOR
def implied_prob(odds):
    return 1/odds

pA=implied_prob(oddsA)

ev=(pA*oddsA)-1

st.subheader("💰 EV")

st.write("EV:",round(ev,3))

# SAVE TRAINING DATA
st.subheader("Save training match")

score=st.text_input("Example: 11:9")

if st.button("Save result"):

    a,b=score.split(":")

    data.append({
        "A":playerA,
        "B":playerB,
        "score":score,
        "points":int(a)+int(b)
    })

    save()

    st.success("saved")
