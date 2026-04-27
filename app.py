import streamlit as st
import unicodedata
import json
import os
from collections import Counter
def normalize_name(name):

    name = name.strip()

    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')

    name = " ".join(name.split())

    return name
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
import requests
from PIL import Image
import re
import numpy as np

st.subheader("📸 Upload Tipsport screenshot")

img_file = st.file_uploader("Upload image", type=["png","jpg","jpeg"])

def ocr_space(image_file):

    api_key = "helloworld"

    response = requests.post(
        "https://api.ocr.space/parse/image",
        files={"file": image_file},
        data={
            "apikey": api_key,
            "language": "eng"
        },
    )

    result = response.json()

    try:
        return result["ParsedResults"][0]["ParsedText"]
    except:
        return ""

if img_file:

    text = ocr_space(img_file)

    st.text("Detected text:")
    st.text(text[:1000])
    import re

def parse_tipsport(text):

    matches = []

    lines = text.split("\n")

    for i in range(len(lines)):

        line = lines[i]

        # hledá "hráč A - hráč B"
        if " - " in line:

            try:
                players = line.split("-")
                A = normalize_name(players[0])
                B = normalize_name(players[1])

                next_line = lines[i+1]

                # např 3:1
                set_match = re.search(r"\d:\d", next_line)

                # např (11:9,11:7,...)
                score_match = re.search(r"\((.*?)\)", next_line)

                odds_line = lines[i+2]

                odds = re.findall(r"\d+\.\d+", odds_line)

                if set_match and score_match and len(odds)>=2:

                    sets = set_match.group()
                    scores = score_match.group(1)

                    oddsA = float(odds[0])
                    oddsB = float(odds[1])

                    matches.append({
                        "A":A,
                        "B":B,
                        "sets":sets,
                        "scores":scores,
                        "oddsA":oddsA,
                        "oddsB":oddsB
                    })

            except:
                pass

    return matches


# =========================
# PARSE + SAVE
# =========================

parsed = parse_tipsport(text)

if len(parsed) > 0:

    st.success(f"Detected {len(parsed)} matches")

    for m in parsed:
        st.write(m)

    if st.button("💾 Uložit do modelu"):

        for m in parsed:

            diff = abs(m["oddsA"] - m["oddsB"])

            for s in m["scores"].split(","):

                a,b = s.strip().split(":")

                data.append({
                    "A":m["A"],
                    "B":m["B"],
                    "score":f"{a}:{b}",
                    "points":int(a)+int(b),
                    "diff":diff,
                    "sets":m["sets"]
                })

        save()

        st.success("✔ data uložená")

    st.success(f"Detected {len(parsed)} matches")

    for m in parsed:

        st.write(m)

        diff = abs(m["oddsA"] - m["oddsB"])

        for s in m["scores"].split(","):

            a,b = s.strip().split(":")

            data.append({
                "A":m["A"],
                "B":m["B"],
                "score":f"{a}:{b}",
                "points":int(a)+int(b),
                "diff":diff,
                "sets":m["sets"]
            })

    save()

    st.success("✔ data saved to model")

else:

    st.error("No matches detected")
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
# =========================
# PREDICTION ENGINE
# =========================

st.header("📊 Prediction")

if len(data) < 30:
    st.warning("Málo dat (min 30 setů)")
else:

    A = st.text_input("Hráč A")
    B = st.text_input("Hráč B")

    oddsA = st.number_input("Kurz A", value=1.8)
    oddsB = st.number_input("Kurz B", value=2.0)

    if st.button("🔮 Spočítat"):

        A = normalize_name(A)
        B = normalize_name(B)

        # DATA
        playerA = [x["score"] for x in data if x["A"]==A or x["B"]==A]
        playerB = [x["score"] for x in data if x["A"]==B or x["B"]==B]

        matchup = [x["score"] for x in data if 
                   (x["A"]==A and x["B"]==B) or 
                   (x["A"]==B and x["B"]==A)]

        global_scores = [x["score"] for x in data]

        from collections import Counter

        final = Counter()

        # GLOBAL
        for k,v in Counter(global_scores).items():
            final[k] += v * 0.3

        # PLAYER A
        for k,v in Counter(playerA).items():
            final[k] += v * 0.2

        # PLAYER B
        for k,v in Counter(playerB).items():
            final[k] += v * 0.2

        # MATCHUP
        if len(matchup) > 0:
            for k,v in Counter(matchup).items():
                final[k] += v * 0.3

        total = sum(final.values())

        st.subheader("📊 Pravděpodobnosti skóre setu")

        probs = []

        for score,count in final.most_common(6):

            p = count / total

            probs.append((score,p))

            st.write(score, "→", round(p*100,1), "%")

        # =========================
        # EVEN / ODD
        # =========================

        even = sum(count for score,count in final.items()
                   if (int(score.split(":")[0]) + int(score.split(":")[1])) % 2 == 0)

        even = even / total

        st.subheader("⚖️ Sudý / lichý")

        st.write("Even:", round(even*100,1), "%")
        st.write("Odd:", round((1-even)*100,1), "%")

        # =========================
        # OVER / UNDER
        # =========================

        line = st.number_input("Line (např 18.5)", value=18.5)

        over = sum(count for score,count in final.items()
                   if (int(score.split(":")[0]) + int(score.split(":")[1])) > line)

        over = over / total

        st.subheader("📈 Over / Under")

        st.write("Over:", round(over*100,1), "%")
        st.write("Under:", round((1-over)*100,1), "%")

        # =========================
        # EV + EDGE
        # =========================

        pA = sum(count for score,count in final.items()
                 if int(score.split(":")[0]) > int(score.split(":")[1])) / total

        edgeA = pA - (1/oddsA)
        edgeB = (1-pA) - (1/oddsB)

        st.subheader("💰 VALUE")

        st.write("P(A):", round(pA,3))
        st.write("Edge A:", round(edgeA,3))
        st.write("Edge B:", round(edgeB,3))
