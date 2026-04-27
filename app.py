# --- 3. SMART PARSER v9.4 (Opravená filtrace rekapitulace) ---
def parse_live_text(text):
    # 1. Rozdělení na řádky a základní vyčištění od balastu
    raw_lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # 2. FILTRACE: Vynecháme rekapitulační řádky a logo
    # Hledáme řádky, které NEZAČÍNAJÍ slovy "Konec" a NEobsahují "milestone-logo"
    clean_lines = []
    for l in raw_lines:
        l_lower = l.lower()
        if "milestone-logo" in l_lower:
            continue
        if l_lower.startswith("konec"):
            continue
        if l in [".", ":"]:
            continue
        clean_lines.append(l)

    if len(clean_lines) < 2: 
        return None

    # Jména hráčů jsou obvykle na prvních dvou očištěných řádcích
    pA_name = normalize_name(clean_lines[0])
    pB_name = normalize_name(clean_lines[1])

    # 3. ZÍSKÁNÍ BODŮ: Musíme parsovat jen z očištěného textu, 
    # abychom nesebrali skóre z těch smazaných "Konec zápasu" řádků
    cleaned_text_for_scores = "\n".join(clean_lines)
    all_scores = re.findall(r'(\d+)\s*:\s*(\d+)', cleaned_text_for_scores)
    
    if not all_scores: 
        return None

    points = [(int(a), int(b)) for a, b in all_scores]

    # Otočení pořadí, pokud jsou data od nejnovějšího po nejstarší (Tipsport style)
    if (points[0][0] + points[0][1]) > (points[-1][0] + points[-1][1]):
        points.reverse()

    # Detekce podání (ze surového textu, to ničemu nevadí)
    detected_starter = "A" 
    serve_match = re.search(r'první podání\s+([A-Z][a-z]?\.[A-Za-zÁ-ž]+|[A-Za-zÁ-ž]+)', text, re.IGNORECASE)
    if serve_match:
        found_name = normalize_name(serve_match.group(1))
        if found_name and (found_name in pB_name or pB_name in found_name):
            detected_starter = "B"

    # Logika sekvence bodů
    sequence, last_a, last_b, unique_points = [], 0, 0, []
    for p in points:
        if not unique_points or p != unique_points[-1]:
            # Ochrana proti "skokům zpět" v čase
            if unique_points and (p[0] + p[1]) < (unique_points[-1][0] + unique_points[-1][1]): 
                continue
            unique_points.append(p)

    for a, b in unique_points:
        if a > last_a: sequence.append("A")
        elif b > last_b: sequence.append("B")
        last_a, last_b = a, b

    return {
        "A": pA_name, 
        "B": pB_name, 
        "score": f"{last_a}:{last_b}", 
        "win": 1 if last_a > last_b else 0, 
        "sequence": sequence, 
        "starter": detected_starter
    }
