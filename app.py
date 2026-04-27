import streamlit as st
import unicodedata
import json
import os
import re
import datetime
import math

# Pokus o import scipy - pokud chybí, použijeme náhradní výpočet
try:
    from scipy.stats import poisson
except ImportError:
    st.error("Knihovna 'scipy' není nainstalována. Přidejte ji do requirements.txt")

# --- DOPLNĚNÁ FUNKCE PRO PŘESNÉ SKÓRE ---
def get_exact_score_probs(probA):
    """Vypočítá pravděpodobnost přesného skóre v setu (11:x)"""
    # Odhad průměrného počtu bodů (lambda) pro každého hráče
    # Pokud má hráč šanci 70 %, očekáváme, že nahraje 11 bodů a soupeř cca 7-8
    lambdaA = 11.0
    lambdaB = 11.0 * ((1 - probA) / (probA + 1e-9))
    if probA < 0.5:
        lambdaB = 11.0
        lambdaA = 11.0 * (probA / (1 - probA + 1e-9))

    scores = []
    # Projdeme možné výsledky od 11:0 do 11:9 a deuce (12:10 atd.)
    for b in range(0, 10): # Výhry A (11:0 až 11:9)
        p = (math.exp(-lambdaA) * lambdaA**11 / math.factorial(11)) * \
            (math.exp(-lambdaB) * lambdaB**b / math.factorial(b))
        scores.append(((11, b), p))
    
    for a in range(0, 10): # Výhry B (0:11 až 9:11)
        p = (math.exp(-lambdaA) * lambdaA**a / math.factorial(a)) * \
            (math.exp(-lambdaB) * lambdaB**11 / math.factorial(11))
        scores.append(((a, 11), p))

    # Přidáme pravděpodobnost pro těsné koncovky (12:10+)
    p_deuce = 1.0 - sum(s[1] for s in scores)
    if probA > 0.5:
        scores.append(((12, 10), p_deuce * 0.7))
        scores.append(((10, 12), p_deuce * 0.3))
    else:
        scores.append(((12, 10), p_deuce * 0.3))
        scores.append(((10, 12), p_deuce * 0.7))

    # Normalizace a seřazení od nejlepších
    total = sum(s[1] for s in scores)
    final_scores = sorted([(s[0], s[1]/total) for s in scores], key=lambda x: x[1], reverse=True)
    return final_scores[:5] # Vracíme top 5 výsledků
