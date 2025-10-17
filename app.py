import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
import io 

# =========================================================================
# --- STAŁE FINANSOWE I REFERENCYJNE (ZAKTUALIZOWANE O NOWE LIMITY) ---
# =========================================================================
ULGA_MAX_KWOTA = 53000.0 
REF_PRODUKCJA_WIATR_KWH_KW_ROK = 1000.0 

# Limity dotacji jednostkowe (np. z programu "Moja Elektrownia Wiatrowa")
MAX_DOTACJA_WIATR_NA_KW = 5000.0  
MAX_DOTACJA_ESS_NA_KWH = 6000.0   

# Nowe, dodane limity maksymalne KWOTOWE (z netbilling2.py)
MAX_DOTACJA_WIATR_KWOTOWY = 30000.0
MAX_DOTACJA_ESS_KWOTOWY = 17000.0

# Ustawienia ESS (techniczne)
ESS_RT_EFFICIENCY = 0.90 
INTERWAL_H = 0.25 

# --- FUNKCJA GENERUJĄCA PRODUKCJĘ WIATROWĄ (NIEZMIENIONA) ---
PROFIL_MIESIECZNY_WIATR = np.array([0.15, 0.14, 0.12, 0.10, 0.09, 0.08, 0.07, 0.08, 0.10, 0.12, 0.14, 0.13])
PROFIL_GODZINOWY_WIATR = np.array([
    0.05, 0.06, 0.07, 0.08, 0.07, 0.06, 
    0.05, 0.04, 0.04, 0.03, 0.03, 0.04, 
    0.04, 0.05, 0.04, 0.04, 0.05, 0.06, 
    0.06, 0.07, 0.07, 0.06, 0.06, 0.05  
])
PROFIL_GODZINOWY_WIATR /= PROFIL_GODZINOWY_WIATR.sum()
PROFIL_MIESIECZNY_WIATR /= PROFIL_MIESIECZNY_WIATR.sum()

def generuj_produkcje_wiatrowa(df, roczna_produkcja_docelowa_kwh):
    # Logika z netbilling2.py
    MIESIAC_ARR = df['Miesiąc'].values 
    GODZINA_ARR = df['Godzina'].values
    wskazniki = np.empty(len(df))
    for i in range(len(df)):
        miesiac_idx = MIESIAC_ARR[i] - 1
        godzina_idx = GODZINA_ARR[i]
        if 0 <= miesiac_idx < 12 and 0 <= godzina_idx < 24:
            wskazniki[i] = PROFIL_MIESIECZNY_WIATR[miesiac_idx] * PROFIL_GODZINOWY_WIATR[godzina_idx]
        else:
            wskazniki[i] = 0 
    df['Wskaznik_Profilu'] = wskazniki
    suma_wskaznikow = df['Wskaznik_Profilu'].sum()
    if suma_wskaznikow == 0:
        return np.zeros(len(df))
    df['Produkcja_Wiatr_Kwh'] = (df['Wskaznik_Profilu'] / suma_wskaznikow) * roczna_produkcja_docelowa_kwh
    return df['Produkcja_Wiatr_Kwh'].copy()

# --- ZOPTYMALIZOWANA FUNKCJA GENERUJĄCA WYKRES (ADAPTACJA DO STREAMLIT) ---
def generuj_wykres_bilansu_rocznego(raport_miesieczny_dane, moc_pv_kwp, moc_turbina_kw, ess_pojemnosc_kwh):
    if not raport_miesieczny_dane:
        st.warning("⚠️ Brak danych miesięcznych do wizualizacji.")
        return

    df_raport = pd.DataFrame(raport_miesieczny_dane)
    
    miesiące_nazwy = {1: 'Sty', 2: 'Lut', 3: 'Mar', 4: 'Kwi', 5: 'Maj', 6: 'Cze', 
                     7: 'Lip', 8: 'Sie', 9: 'Wrz', 10: 'Paź', 11: 'Lis', 12: 'Gru'}
    
    df_raport['Miesiąc_Num'] = df_raport['Miesiąc'].apply(lambda x: x.month)
    df_raport['Miesiąc_Sort'] = df_raport['Miesiąc_Num'].apply(lambda x: x if x >= 10 else x + 12)
    df_raport['Miesiąc_Nazwa'] = df_raport['Miesiąc_Num'].map(miesiące_nazwy)
    df_raport = df_raport.sort_values(by='Miesiąc_Sort')
    
    X = df_raport['Miesiąc_Nazwa']
    Y_AC_PV = df_raport['AC_PV_KWh']
    Y_AC_Wiatr = df_raport['AC_Wiatr_KWh']
    Y_AC_ESS = df_raport['AC_ESS_KWh']
    Y_SPRZEDAZ = df_raport['Sprzedaz_Siec_KWh']
    Y_ZAKUP = df_raport['Zakup_Siec_KWh']
    
    COLOR_PV = '#FFEB3B'      # Żółty
    COLOR_WIATR = '#03A9F4'   # Niebieski
    COLOR_ESS = '#4CAF50'     # Zielony
    COLOR_ZAKUP = '#F44336'   # Czerwony
    COLOR_EKSPORT = '#FF9800' # Pomarańczowy

    fig, ax = plt.subplots(figsize=(12, 6))
    
    current_bottom = pd.Series(np.zeros(len(df_raport))) 

    # SŁUPKI NAD OSIĄ 0
    ax.bar(X, Y_AC_PV, color=COLOR_PV, label='Autokonsumpcja z PV', zorder=2, bottom=current_bottom)
    current_bottom += Y_AC_PV 
    
    ax.bar(X, Y_AC_Wiatr, bottom=current_bottom, color=COLOR_WIATR, label='Autokonsumpcja z Wiatru', zorder=2)
    current_bottom += Y_AC_Wiatr 
    
    ax.bar(X, Y_AC_ESS, bottom=current_bottom, color=COLOR_ESS, label='Autokonsumpcja z Magazynu', zorder=2)
    current_bottom += Y_AC_ESS 
    
    ax.bar(X, Y_SPRZEDAZ, bottom=current_bottom, color=COLOR_EKSPORT, label='Eksport/Sprzedaż do Sieci', zorder=2)

    # SŁUPKI PONIŻEJ OSI 0
    ax.bar(X, -Y_ZAKUP, color=COLOR_ZAKUP, label='Pobór/Zakup z Sieci', zorder=2)

    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_title(f'Roczny Bilans Energetyczny: {moc_pv_kwp} kWp PV + {moc_turbina_kw} kW Wiatr + {ess_pojemnosc_kwh} kWh ESS')
    ax.set_xlabel('Miesiąc')
    ax.set_ylabel('Energia [kWh]')
    
    # Formatowanie legendy (zgodnie z poprawką w netbilling2.py)
    ax.legend(loc='lower right', 
               bbox_to_anchor=(1.0, 1.05), 
               ncol=3, 
               frameon=False, 
               fontsize='small') 

    ax.grid(axis='y', linestyle=':', zorder=1)
    plt.tight_layout(rect=[0, 0, 1, 0.9])
    
    st.pyplot(fig)


# --- GŁÓWNA FUNKCJA KALKULATORA (CAŁA LOGIKA SYMULACJI Z NETBILLING2.PY) ---
def run_simulation(moc_pv_kwp, koszt_pv_total, moc_turbina_kw, koszt_turbiny_wiatrowej, 
                   ess_pojemnosc_kwh, ess_moc_ladowania_kw, ess_moc_rozladowania_kw, 
                   cena_magazynu_total, korzysta_z_dotacji, korzysta_z_ulgi_termomodernizacyjnej, 
                   stawka_podatkowa_procent, procent_pracy_turbiny, df_dane):
    
    # Skalowanie produkcji wiatrowej
    wspolczynnik_skali_wiatr = procent_pracy_turbiny / 100.0
    roczna_produkcja_docelowa_kwh = moc_turbina_kw * REF_PRODUKCJA_WIATR_KWH_KW_ROK * wspolczynnik_skali_wiatr

    # Ustawienie limitów ESS dla symulacji
    ESS_LADOWANIE_LIMIT_KWH = ess_moc_ladowania_kw * INTERWAL_H 
    ESS_ROZLADOWANIE_LIMIT_KWH = ess_moc_rozladowania_kw * INTERWAL_H
    
    # Koszt bazowy ESS
    ESS_KOSZT_BAZOWY = cena_magazynu_total

    # KOSZT CAŁKOWITY INWESTYCJI PRZED DOTACJĄ I ULGĄ
    koszt_calkowity_bazowy = koszt_pv_total + koszt_turbiny_wiatrowej + ESS_KOSZT_BAZOWY

    # --- OBLICZANIE DOTACJI Z NOWYMI LIMITAMI (KROK 1) ---
    dotacja_magazyn = 0.0
    dotacja_turbina = 0.0

    if korzysta_z_dotacji:
        # 1. Limity procentowe (50% kosztów)
        limit_procentowy_magazyn = ESS_KOSZT_BAZOWY * 0.5
        limit_procentowy_turbina = koszt_turbiny_wiatrowej * 0.5
        
        # 2. Limity na kW/kWh
        limit_kwotowy_na_jednostke_magazyn = ess_pojemnosc_kwh * MAX_DOTACJA_ESS_NA_KWH
        limit_kwotowy_na_jednostke_turbina = moc_turbina_kw * MAX_DOTACJA_WIATR_NA_KW
        
        # 3. Limity maksymalne KWOTOWE (Nowe!)
        limit_max_kwotowy_turbina = MAX_DOTACJA_WIATR_KWOTOWY
        limit_max_kwotowy_magazyn = MAX_DOTACJA_ESS_KWOTOWY
        
        # Dotacja to minimum z tych 3 limitów dla każdego elementu
        dotacja_magazyn = min(limit_procentowy_magazyn, 
                              limit_kwotowy_na_jednostke_magazyn, 
                              limit_max_kwotowy_magazyn)
        
        dotacja_turbina = min(limit_procentowy_turbina, 
                              limit_kwotowy_na_jednostke_turbina,
                              limit_max_kwotowy_turbina)

    dotacja_calkowita = dotacja_magazyn + dotacja_turbina

    koszt_ess_po_dotacji = ESS_KOSZT_BAZOWY - dotacja_magazyn
    koszt_turbiny_po_dotacji = koszt_turbiny_wiatrowej - dotacja_turbina

    koszt_inwestycji_po_dotacji = koszt_pv_total + koszt_ess_po_dotacji + koszt_turbiny_po_dotacji

    # --- OBLICZANIE ULGI TERMODERNIZACYJNE (KROK 2) ---
    if korzysta_z_ulgi_termomodernizacyjnej:
        koszt_kwalifikowany_calkowity = koszt_inwestycji_po_dotacji
        kwota_do_odliczenia = min(koszt_kwalifikowany_calkowity, ULGA_MAX_KWOTA)
        ulga_wartosc_pln = kwota_do_odliczenia * (stawka_podatkowa_procent / 100.0)
        koszt_inwestycji_netto = koszt_inwestycji_po_dotacji - ulga_wartosc_pln
    else:
        koszt_kwalifikowany_calkowity = 0.0
        kwota_do_odliczenia = 0.0
        ulga_wartosc_pln = 0.0
        koszt_inwestycji_netto = koszt_inwestycji_po_dotacji 
        
    
    # --- PRZYGOTOWANIE DANYCH ---
    df_cleaned = df_dane.copy() 

    if 'Data' not in df_cleaned.columns and len(df_cleaned.columns) > 0:
        df_cleaned.rename(columns={df_cleaned.columns[0]: 'Data'}, inplace=True) 

    try:
        # Kod do obsługi konwersji dat (niezmieniony)
        if df_cleaned['Data'].dtype in [np.float64, np.int64]:
            df_cleaned['Data'] = pd.to_datetime('1899-12-30') + pd.to_timedelta(df_cleaned['Data'], unit='D')
        
        df_cleaned['Data'] = pd.to_datetime(df_cleaned['Data'], errors='coerce', dayfirst=True)
        
        start_date = df_cleaned['Data'].min()
        if pd.isna(start_date):
             raise ValueError("Brak danych daty w pliku po konwersji.")

        end_date = start_date + pd.DateOffset(years=1) - pd.Timedelta(minutes=15)
        
        df_cleaned = df_cleaned[(df_cleaned['Data'] >= start_date) & (df_cleaned['Data'] <= end_date)].copy()
        
        if len(df_cleaned) == 0:
            raise ValueError("Dane nie obejmują pełnego roku lub filtracja się nie powiodła.")
        
        df_cleaned['Miesiąc'] = df_cleaned['Data'].dt.month.fillna(0).astype(int)
        df_cleaned['Godzina'] = df_cleaned['Data'].dt.hour.fillna(0).astype(int)
        
        df_cleaned['Miesiąc_Rok'] = df_cleaned['Data'].dt.to_period('M')
        df_cleaned['Dzień'] = df_cleaned['Data'].dt.date
        
    except Exception as e:
        st.error(f"❌ BŁĄD: Problem z konwersją kolumny 'Data' lub wyciąganiem czasu. {e}")
        return None

    def convert_to_numeric(column):
        if column.dtype == 'object':
            cleaned = column.astype(str).str.replace('zł', '', regex=False).str.replace(' ', '', regex=False).str.replace(',', '.', regex=False)
            return pd.to_numeric(cleaned, errors='coerce') 
        return column

    col_cena_eksportu = 'Cena eksportu'
    col_produkcja_pv_1kwp = 'produkcja 1KWp'
    col_konsumpcja = 'Profil konsumpcji (Kwh'
    col_cena_energii = 'cena energii czynnej (Kwh)'
    col_koszt_dystrybucji = 'koszt dystrybucji (Kwh)'

    REQUIRED_COLS = [col_cena_eksportu, col_produkcja_pv_1kwp, col_konsumpcja, col_cena_energii, col_koszt_dystrybucji]

    missing_cols = [c for c in REQUIRED_COLS if c not in df_cleaned.columns]
    if missing_cols:
        st.error(f"❌ BŁĄD KOLUMN: Nie znaleziono kluczowych nagłówków: {missing_cols}. Sprawdź, czy są poprawnie nazwane w pliku CSV.")
        return None

    for col in REQUIRED_COLS:
        df_cleaned[col] = convert_to_numeric(df_cleaned[col])

    df_cleaned[col_konsumpcja] = df_cleaned[col_konsumpcja].fillna(0)
    df_cleaned[col_produkcja_pv_1kwp] = df_cleaned[col_produkcja_pv_1kwp].fillna(0)

    for col in [col_cena_eksportu, col_cena_energii, col_koszt_dystrybucji]:
        mean_val = df_cleaned[col].mean()
        df_cleaned[col] = df_cleaned[col].fillna(mean_val if pd.notna(mean_val) else 0)

    df = df_cleaned.dropna(subset=REQUIRED_COLS, how='all').copy() 

    SUMA_KONSUMPCJI_KWH = df[col_konsumpcja].sum() 
    # Dodanie obliczenia kosztu bez PV dla oszczędności
    koszt_bez_pv = (df[col_konsumpcja] * (df[col_cena_energii] + df[col_koszt_dystrybucji])).sum()
    
    if moc_turbina_kw > 0:
        df['Produkcja_Wiatr_Kwh'] = generuj_produkcje_wiatrowa(df, roczna_produkcja_docelowa_kwh)
    else:
        df['Produkcja_Wiatr_Kwh'] = 0.0

    # --- PĘTLA SYMULACYJNA (NIEZMIENIONA) ---
    moce_kwp = [moc_pv_kwp] 
    raport_miesieczny_dane = []
    
    # Stan naładowania magazynu
    ess_soc_kwh = ess_pojemnosc_kwh / 2 
    
    # Zmienne roczne
    oszczednosci_kompensacja_suma = 0 
    koszt_dystrybucji_suma = 0 
    koszt_energii_do_zaplaty = 0 
    portfel_pln = 0 
    suma_autokonsumpcji_pv_kwh = 0
    suma_autokonsumpcji_wiatr_kwh = 0
    suma_autokonsumpcji_z_ess_kwh = 0 
    suma_produkcji_pv_kwh = 0
    suma_produkcji_wiatr_kwh = 0
    suma_wyslana_do_sieci_kwh = 0
    
    aktualny_miesiac = None
    koszt_dystrybucji_suma_miesiac = 0
    koszt_energii_do_zaplaty_miesiac = 0
    portfel_pln_poczatek_miesiac = 0
    
    suma_produkcji_miesiac = 0
    suma_konsumpcji_miesiac = 0
    suma_autokonsumpcji_miesiac = 0
    suma_sprzedazy_miesiac = 0
    suma_zakupu_miesiac = 0
    suma_ac_pv_miesiac = 0
    suma_ac_wiatr_miesiac = 0
    suma_ac_ess_miesiac = 0

    # Główna pętla symulacyjna
    for index, row in df.iterrows():
        
        # Logika do agregacji miesięcznej
        if 'Miesiąc_Rok' in df.columns:
            miesiac_rok = row.get('Miesiąc_Rok')
            
            if pd.isna(miesiac_rok):
                pass
            
            elif aktualny_miesiac is None or miesiac_rok != aktualny_miesiac:
                if aktualny_miesiac is not None and moc_pv_kwp == moc_pv_kwp: 
                    rachunek_miesiac = (koszt_dystrybucji_suma_miesiac + koszt_energii_do_zaplaty_miesiac)
                    
                    raport_miesieczny_dane.append({
                        'Miesiąc': aktualny_miesiac,
                        'Portfel_PLN_Poczatek': portfel_pln_poczatek_miesiac,
                        'Portfel_PLN_Koniec': portfel_pln,
                        'Rachunek_Do_Zaplaty_PLN': rachunek_miesiac,
                        'Produkcja_KWh': suma_produkcji_miesiac,
                        'Autokonsumpcja_KWh': suma_autokonsumpcji_miesiac,
                        'Zakup_Siec_KWh': suma_zakupu_miesiac,
                        'Sprzedaz_Siec_KWh': suma_sprzedazy_miesiac,
                        'AC_PV_KWh': suma_ac_pv_miesiac,
                        'AC_Wiatr_KWh': suma_ac_wiatr_miesiac,
                        'AC_ESS_KWh': suma_ac_ess_miesiac,
                        'KWP': moc_pv_kwp
                    })

                # Wyzerowanie liczników dla nowego miesiąca
                aktualny_miesiac = miesiac_rok
                portfel_pln_poczatek_miesiac = portfel_pln
                koszt_dystrybucji_suma_miesiac = 0
                koszt_energii_do_zaplaty_miesiac = 0
                suma_produkcji_miesiac = 0
                suma_konsumpcji_miesiac = 0
                suma_autokonsumpcji_miesiac = 0
                suma_sprzedazy_miesiac = 0
                suma_zakupu_miesiac = 0
                suma_ac_pv_miesiac = 0
                suma_ac_wiatr_miesiac = 0
                suma_ac_ess_miesiac = 0


        # OBLICZENIA BILANSU ENERGETYCZNEGO (Niezmienione)
        produkcja_pv = moc_pv_kwp * row[col_produkcja_pv_1kwp]
        produkcja_wiatr = row['Produkcja_Wiatr_Kwh']
        
        suma_produkcji_pv_kwh += produkcja_pv
        suma_produkcji_wiatr_kwh += produkcja_wiatr
        
        suma_produkcji_miesiac += produkcja_pv + produkcja_wiatr
        konsumpcja = row[col_konsumpcja]
        suma_konsumpcji_miesiac += konsumpcja 
        
        pozostala_konsumpcja = konsumpcja
        
        # KROK 1: Autokonsumpcja bezposrednia (PV + Wiatr)
        autokonsumpcja_z_pv = min(produkcja_pv, pozostala_konsumpcja)
        suma_autokonsumpcji_pv_kwh += autokonsumpcja_z_pv
        suma_ac_pv_miesiac += autokonsumpcja_z_pv 
        pozostala_konsumpcja -= autokonsumpcja_z_pv
        nadwyzka_pv = produkcja_pv - autokonsumpcja_z_pv
        
        autokonsumpcja_z_wiatru = min(produkcja_wiatr, pozostala_konsumpcja)
        suma_autokonsumpcji_wiatr_kwh += autokonsumpcja_z_wiatru
        suma_ac_wiatr_miesiac += autokonsumpcja_z_wiatru 
        pozostala_konsumpcja -= autokonsumpcja_z_wiatru
        nadwyzka_wiatr = produkcja_wiatr - autokonsumpcja_z_wiatru
        
        nadwyzka_calkowita_do_zagospodarowania = nadwyzka_pv + nadwyzka_wiatr
        niedobor_po_ac = pozostala_konsumpcja
        
        energia_z_ess = 0 
        
        # LOGIKA ESS (TYLKO AUTOKONSUMPCJA)
        
        # A. Nadwyżka (Ładowanie ESS)
        energia_do_magazynu = 0
        if nadwyzka_calkowita_do_zagospodarowania > 0:
            brakuje_do_pelna = ess_pojemnosc_kwh - ess_soc_kwh
            max_mozemy_zaladowac_netto = min(brakuje_do_pelna, ESS_LADOWANIE_LIMIT_KWH)
            energia_do_pobrania = max_mozemy_zaladowac_netto / ESS_RT_EFFICIENCY
            energia_do_magazynu = min(nadwyzka_calkowita_do_zagospodarowania, energia_do_pobrania)
            
            if energia_do_magazynu > 0:
                ess_soc_kwh += energia_do_magazynu * ESS_RT_EFFICIENCY
                nadwyzka_calkowita_do_zagospodarowania -= energia_do_magazynu
                
        # B. Niedobór (Rozładowanie ESS dla zużycia własnego)
        if niedobor_po_ac > 0:
            max_mozemy_rozladowac = min(ess_soc_kwh, ESS_ROZLADOWANIE_LIMIT_KWH)
            ilosc_potrzebna = niedobor_po_ac
            energia_z_ess = min(ilosc_potrzebna, max_mozemy_rozladowac)
            
            if energia_z_ess > 0:
                ess_soc_kwh -= energia_z_ess
                niedobor_po_ac -= energia_z_ess
                suma_autokonsumpcji_z_ess_kwh += energia_z_ess
                suma_ac_ess_miesiac += energia_z_ess 

        # Zwiększanie licznika miesięcznego Autokonsumpcji
        suma_autokonsumpcji_miesiac += autokonsumpcja_z_pv + autokonsumpcja_z_wiatru + energia_z_ess
        
        # D. Wysłanie pozostałej Nadwyżki do Sieci (Net-billing)
        if nadwyzka_calkowita_do_zagospodarowania > 0:
            energia_wyslana_do_sieci = nadwyzka_calkowita_do_zagospodarowania
            
            cena_sprzedazy = row[col_cena_eksportu]
            if cena_sprzedazy < 0:
                cena_sprzedazy = 0.0 

            portfel_pln += energia_wyslana_do_sieci * cena_sprzedazy
            suma_wyslana_do_sieci_kwh += energia_wyslana_do_sieci
            suma_sprzedazy_miesiac += energia_wyslana_do_sieci 
            
        # E. Pobranie z Sieci (pozostały Niedobór)
        if niedobor_po_ac > 0:
            
            koszt_dystrybucji_dodatek = niedobor_po_ac * row[col_koszt_dystrybucji]
            koszt_dystrybucji_suma += koszt_dystrybucji_dodatek
            if aktualny_miesiac is not None:
                koszt_dystrybucji_suma_miesiac += koszt_dystrybucji_dodatek
            
            koszt_energii_czynnej = niedobor_po_ac * row[col_cena_energii] 
            
            kompensacja_z_portfela = min(portfel_pln, koszt_energii_czynnej)
            portfel_pln -= kompensacja_z_portfela
            oszczednosci_kompensacja_suma += kompensacja_z_portfela
            
            pozostaly_koszt_do_zaplaty = koszt_energii_czynnej - kompensacja_z_portfela
            koszt_energii_do_zaplaty += pozostaly_koszt_do_zaplaty
            if aktualny_miesiac is not None:
                koszt_energii_do_zaplaty_miesiac += pozostaly_koszt_do_zaplaty
            
            portfel_pln = max(0, portfel_pln)
            
            suma_zakupu_miesiac += niedobor_po_ac 

    # Zapis ostatniego miesiąca po pętli rocznej
    if 'Miesiąc_Rok' in df.columns and moc_pv_kwp == moc_pv_kwp and aktualny_miesiac is not None:
        rachunek_miesiac = (koszt_dystrybucji_suma_miesiac + koszt_energii_do_zaplaty_miesiac)
        raport_miesieczny_dane.append({
            'Miesiąc': aktualny_miesiac,
            'Portfel_PLN_Poczatek': portfel_pln_poczatek_miesiac,
            'Portfel_PLN_Koniec': portfel_pln,
            'Rachunek_Do_Zaplaty_PLN': rachunek_miesiac,
            'Produkcja_KWh': suma_produkcji_miesiac,
            'Autokonsumpcja_KWh': suma_autokonsumpcji_miesiac,
            'Zakup_Siec_KWh': suma_zakupu_miesiac,
            'Sprzedaz_Siec_KWh': suma_sprzedazy_miesiac,
            'AC_PV_KWh': suma_ac_pv_miesiac,
            'AC_Wiatr_KWh': suma_ac_wiatr_miesiac,
            'AC_ESS_KWh': suma_ac_ess_miesiac,
            'KWP': moc_pv_kwp
        })


    # KROK 4: Obliczenia końcowe (roczne)
    
    rachunek_po_pv = koszt_dystrybucji_suma + koszt_energii_do_zaplaty
    
    # Obliczenie oszczędności z uniknięcia zakupu (koszt bez PV - rachunek po PV)
    oszczednosci_z_unikniecia_zakupu = koszt_bez_pv - rachunek_po_pv
    
    portfel_pln_przed_wyplata = portfel_pln
    wyplata_z_portfela = portfel_pln * 0.30 
    
    oszczednosci_calkowite_roczne = oszczednosci_z_unikniecia_zakupu + wyplata_z_portfela
    
    okres_zwrotu = koszt_inwestycji_netto / oszczednosci_calkowite_roczne if oszczednosci_calkowite_roczne > 0 else float('inf')
    
    suma_calkowita_produkcji_kwh = suma_produkcji_pv_kwh + suma_produkcji_wiatr_kwh
    suma_calkowita_autokonsumpcji_kwh = suma_autokonsumpcji_pv_kwh + suma_autokonsumpcji_wiatr_kwh + suma_autokonsumpcji_z_ess_kwh
    
    procent_samo_zuzycia = (suma_calkowita_autokonsumpcji_kwh / suma_calkowita_produkcji_kwh) * 100 if suma_calkowita_produkcji_kwh > 0 else 0.0
    procent_samo_wystarczalnosci = (suma_calkowita_autokonsumpcji_kwh / SUMA_KONSUMPCJI_KWH) * 100 if SUMA_KONSUMPCJI_KWH > 0 else 0.0

    # Zwrócenie wyników rocznych i miesięcznych (klucze dostosowane do netbilling2.py)
    return {
        'wyniki_roczne': {
            'Oszczędności całkowite': oszczednosci_calkowite_roczne,
            'Rachunek do zapłaty': rachunek_po_pv,
            'Koszt inwestycji Całkowity': koszt_inwestycji_netto, # Zmieniony klucz
            'Okres zwrotu (lat)': okres_zwrotu,
            'Procent samo-wystarczalności': procent_samo_wystarczalnosci, 
            'Procent samo-zużycia': procent_samo_zuzycia,
            'Produkcja PV [kWh]': suma_produkcji_pv_kwh,
            'Produkcja Wiatr [kWh]': suma_produkcji_wiatr_kwh,
            'Wartość Dotacji': dotacja_calkowita,
            'Wartość Odliczenia (Ulga)': ulga_wartosc_pln,
        },
        'raport_miesieczny_dane': raport_miesieczny_dane
    }


# =========================================================================
# GŁÓWNA STRUKTURA STREAMLIT (INTERFEJS)
# =========================================================================

st.set_page_config(page_title="Kalkulator Net-billing PV+Wiatr+ESS", layout="wide")
st.title("☀️ Kalkulator Net-billing: PV + Wiatr + Magazyn Energii")

# Sekcja wczytywania ukrytych danych
try:
    file_path = 'dane_zuzycia.csv'
    # Streamlit Cloud wczytuje plik bezpośrednio z repozytorium
    df_dane = pd.read_csv(file_path, delimiter=';', encoding='utf-8-sig', low_memory=False)
    st.info(f"Pomyślnie wczytano dane zużycia z pliku **{file_path}**.")
except FileNotFoundError:
    st.error(f"❌ BŁĄD: Ukryty plik danych '{file_path}' nie został znaleziony. Upewnij się, że jest w repozytorium.")
    df_dane = None
except Exception as e:
    st.error(f"❌ BŁĄD wczytywania ukrytego pliku: {e}")
    df_dane = None


if df_dane is not None:
    st.sidebar.header("Ustawienia Inwestycji")

    # --- Sekcja PV ---
    st.sidebar.subheader("1. Fotowoltaika (PV)")
    moc_pv_kwp = st.sidebar.number_input("Moc instalacji PV [kWp]:", 
                                         min_value=0.0, value=5.0, step=0.5, format="%.1f")
    koszt_pv_total = st.sidebar.number_input(f"Koszt instalacji PV [zł]:", 
                                             min_value=0.0, value=25000.0, step=100.0, format="%.2f")

    # --- Sekcja WIATR ---
    st.sidebar.subheader("2. Turbina Wiatrowa")
    moc_turbina_kw = st.sidebar.number_input("Moc nominalna turbiny [kW]:", 
                                             min_value=0.0, value=2.0, step=0.5, format="%.1f")
    koszt_turbiny_wiatrowej = st.sidebar.number_input(f"Koszt instalacji wiatrowej [zł]:", 
                                                      min_value=0.0, value=30000.0, step=100.0, format="%.2f")
    procent_pracy_turbiny = st.sidebar.slider("Procent pracy turbiny [%]:", 
                                             min_value=10, max_value=200, value=100, step=10, help=f"Skalowanie rocznej produkcji wiatru (100% to {moc_turbina_kw * REF_PRODUKCJA_WIATR_KWH_KW_ROK:.0f} kWh dla {moc_turbina_kw}kW)")

    # --- Sekcja ESS ---
    st.sidebar.subheader("3. Magazyn Energii (ESS)")
    ess_pojemnosc_kwh = st.sidebar.number_input("Pojemność magazynu [kWh]:", 
                                                min_value=0.0, value=10.0, step=1.0, format="%.1f")
    cena_magazynu_total = st.sidebar.number_input(f"Koszt magazynu [zł]:", 
                                                  min_value=0.0, value=40000.0, step=100.0, format="%.2f")
    
    col1, col2 = st.sidebar.columns(2)
    ess_moc_ladowania_kw = col1.number_input("Moc ładowania [kW]:", 
                                             min_value=0.1, value=5.0, step=0.5, format="%.1f")
    ess_moc_rozladowania_kw = col2.number_input("Moc rozładowania [kW]:", 
                                                min_value=0.1, value=5.0, step=0.5, format="%.1f")

    # --- Sekcja Ulgi i Dotacje ---
    st.sidebar.subheader("4. Finansowanie")
    korzysta_z_dotacji = st.sidebar.checkbox(f"Korzystam z dotacji 'MEW' (max {MAX_DOTACJA_WIATR_KWOTOWY:,.0f} zł na Wiatr, {MAX_DOTACJA_ESS_KWOTOWY:,.0f} zł na ESS)", value=True)
    korzysta_z_ulgi_termomodernizacyjnej = st.sidebar.checkbox(f"Korzystam z Ulgi Termomodernizacyjnej (max {ULGA_MAX_KWOTA:,.0f} zł)", value=True)
    
    stawka_podatkowa_procent = 0.0
    if korzysta_z_ulgi_termomodernizacyjnej:
        stawka_podatkowa_procent = st.sidebar.slider("Stawka podatkowa PIT [%]:", 
                                                     min_value=0.0, max_value=32.0, value=18.0, step=0.5, format="%.1f")

    st.markdown("---")
    if st.button("🚀 Uruchom Symulację Net-billing"):
        
        if moc_pv_kwp + moc_turbina_kw == 0:
            st.warning("Wprowadź moc co najmniej jednej instalacji (PV lub Wiatr).")
        else:
            with st.spinner('Trwa obliczanie rocznej symulacji i wyników finansowych...'):
                
                # Uruchomienie Głównej Logiki
                results = run_simulation(
                    moc_pv_kwp, koszt_pv_total, moc_turbina_kw, koszt_turbiny_wiatrowej, 
                    ess_pojemnosc_kwh, ess_moc_ladowania_kw, ess_moc_rozladowania_kw, 
                    cena_magazynu_total, korzysta_z_dotacji, korzysta_z_ulgi_termomodernizacyjnej, 
                    stawka_podatkowa_procent, procent_pracy_turbiny, df_dane
                )
                
                # WYŚWIETLANIE WYNIKÓW STREAMLIT
                if results is not None:
                    roczne = results['wyniki_roczne']
                    miesieczne_dane = results['raport_miesieczny_dane']
                    
                    st.header("Wyniki Końcowe i Finansowe")
                    
                    colA, colB, colC = st.columns(3)
                    
                    # Kolumna 1: ZWROT I OSZCZĘDNOŚCI
                    colA.metric("Oszczędności Całkowite Rocznie", 
                                f"{roczne['Oszczędności całkowite']:,.0f} PLN", 
                                "Zysk z AC + 30% z eksportu")
                    
                    zwrot_text = f"{roczne['Okres zwrotu (lat)']:.1f} lat" if roczne['Okres zwrotu (lat)'] != float('inf') else "NIGDY"
                    colA.metric("⏱️ Okres Zwrotu Inwestycji (Ostateczny)", 
                                zwrot_text)

                    # Kolumna 2: EFEKTYWNOŚĆ ENERGETYCZNA
                    colB.metric("Procent Samo-Wystarczalności", 
                                f"{roczne['Procent samo-wystarczalności']:,.1f} %", 
                                "Ile zużycia pokrywa instalacja")
                    colB.metric("Procent Samo-Zużycia", 
                                f"{roczne['Procent samo-zużycia']:,.1f} %", 
                                "Ile produkcji jest zużywane na miejscu")
                                
                    # Kolumna 3: KOSZTY
                    colC.metric("Koszt Inwestycji Całkowity (Ostateczny)", 
                                f"{roczne['Koszt inwestycji Całkowity']:,.0f} PLN") # Zaktualizowany klucz
                    if roczne['Wartość Dotacji'] > 0:
                         colC.metric("Wartość Dotacji", 
                                     f"-{roczne['Wartość Dotacji']:,.0f} PLN", 
                                     help="Dotacja na ESS i Wiatr (z nowymi limitami)")
                    if roczne['Wartość Odliczenia (Ulga)'] > 0:
                         colC.metric("Zwrot PIT (Ulga Termom.)", 
                                     f"-{roczne['Wartość Odliczenia (Ulga)']:,.0f} PLN", 
                                     help=f"Ulga termomodernizacyjna wg stawki {stawka_podatkowa_procent:.1f}%")

                    
                    st.subheader("Roczny Bilans Energetyczny (Wykres)")
                    st.caption(f"Produkcja PV: {roczne['Produkcja PV [kWh]']:,.0f} kWh | Produkcja Wiatr: {roczne['Produkcja Wiatr [kWh]']:,.0f} kWh")
                    
                    # Wywołanie funkcji generującej wykres Matplotlib
                    generuj_wykres_bilansu_rocznego(miesieczne_dane, moc_pv_kwp, moc_turbina_kw, ess_pojemnosc_kwh)