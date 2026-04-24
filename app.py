import streamlit as st

st.title("🏓 TT STAR LIVE APP")

if "A" not in st.session_state:
    st.session_state.A = 0
if "B" not in st.session_state:
    st.session_state.B = 0

st.write("Score:", st.session_state.A, ":", st.session_state.B)

col1, col2 = st.columns(2)

with col1:
    if st.button("+ Point A"):
        st.session_state.A += 1

with col2:
    if st.button("+ Point B"):
        st.session_state.B += 1

oddsA = st.number_input("Odds A", value=1.8)
oddsB = st.number_input("Odds B", value=2.0)

def prob(a,b):
    return 1/(1+10**((b-a)/1.5))

pA = prob(oddsA, oddsB)

diff = st.session_state.A - st.session_state.B
live = max(
    
