import streamlit as st
import pandas as pd
import os

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="TT Star Data App", layout="wide")

# --- FUNKCE PRO ZPRACOVÁNÍ DAT (Logika vkládání) ---
def vloz_zapas_callback():
    """Tato funkce bezpečně zpracuje text a vymaže pole bez chyby."""
    text = st.session_state.txt_area
    if not text:
        return

    try:
        # Rozdělení textu: Hráči | Sety | Datum | Kurzy
        casti = [c.strip() for c in text.split('|')]
        if len(casti) < 4:
            st.error("Chybný formát! Musí tam být 3 svislítka ( | ).")
            return

        hraci = [h.strip() for h in casti[0].split('-')]
        hrac_a, hrac_b = hraci[0], hraci[1]
        sety_raw = casti[1].replace('(', '').replace(')', '').split(',')
        datum_cas = casti[2]
        kurzy = casti[3].split('/')
        k_a, k_b = kurzy[0].strip(), kurzy[1].strip()

        novy_zaznamy = []
        for i, s in enumerate(sety_raw):
            skore = s.strip()
            body = skore.split(':')
            vitez = 'A' if int(body[0]) > int(body[1]) else 'B'
            
            novy_zaznamy.append({
                'A': hrac_a, 'B': hrac_b, 'score': skore, 'starter': '?',
                'timestamp': datum_cas, 'odds': f"{k_a}/{k_b}",
                'set_num': i + 1, 'odds_player_A': k_a, 'odds_player_B': k_b, 'set_winner': vitez
            })

        df_novy = pd.DataFrame(novy_zaznamy)
        soubor = 'tt_star.csv'
        
        if os.path.exists(soubor):
            df_stary = pd.read_csv(soubor)
            df_final = pd.concat([df_stary, df_novy], ignore_index=True)
        else:
            df_final = df_novy
            
        df_final.to_csv(soubor, index=False)
        st.sidebar.success(f"Uloženo: {hrac_a} vs {hrac_b}")
        
        # DŮLEŽITÉ: Vymazání textového pole po úspěšném vložení
        st.session_state.txt_area = ""

    except Exception as e:
        st.error(f"Chyba při parsování: {e}")

# --- BOČNÍ MENU ---
st.sidebar.title("TT Star Menu")
volba = st.sidebar.radio("Navigace:", ["📥 Vkládání", "🔮 Predikce", "🏆 Žebříček", "⚙️ Správa"])

# --- JEDNOTLIVÉ SEKCE ---

if volba == "📥 Vkládání":
    st.title("📥 Ruční vkládání zápasů")
    st.info("Formát: Jméno A - Jméno B | (11:5, 11:7) | 07.05. 08:31 | 1.50 / 2.50")
    
    # Text area s klíčem propojeným na session_state
    st.text_area("Vložte text zápasu:", key="txt_area", height=200)
    
    # Tlačítko používá on_click callback
    st.button("Uložit zápas do databáze", on_click=vloz_zapas_callback)

elif volba == "🔮 Predikce":
    st.title("🔮 Predikce výsledků")
    st.write("Zde vložte svůj kód pro výpočet Glicko ratingu a pravděpodobností.")
    # Sem zkopíruj svou logiku pro predikce
    
elif volba == "🏆 Žebříček":
    st.title("🏆 Žebříček hráčů")
    if os.path.exists('tt_star.csv'):
        df = pd.read_csv('tt_star.csv')
        st.write("Aktuální pořadí podle vašich dat:")
        st.dataframe(df['A'].value_counts()) # Jen příklad
    else:
        st.warning("Zatím nemáte žádná data.")

elif volba == "⚙️ Správa":
    st.title("⚙️ Správa a zálohy")
    if os.path.exists('tt_star.csv'):
        df = pd.read_csv('tt_star.csv')
        st.dataframe(df.tail(20))
        
        # Tlačítko pro stažení zálohy
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Stáhnout tt_star.csv (Záloha)", data=csv, file_name="tt_star_backup.csv", mime="text/csv")
        
        if st.button("Smazat poslední záznam"):
            df.drop(df.tail(1).index, inplace=True)
            df.to_csv('tt_star.csv', index=False)
            st.rerun()
    else:
        st.error("Soubor s daty nebyl nalezen.")
