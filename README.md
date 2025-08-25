
# REMARK CRM (Streamlit + SQLite)

CRM systém pre firmu REMARK Interier. Postavené na **Streamlit** + **SQLite** s importom z Excelu a CSV.

## Funkcie
- Úvodná tabuľka s prehľadom leadov (multi‑sort, filtre, full‑text).
- Okamžitá inline editácia vybraných polí.
- Farebné označenie podľa **stav_leadu** a **priorita** + zvýraznenie termínov ďalších krokov.
- Detail pravého panelu s rýchlymi akciami (zmeniť stav, nastaviť krok, konvertovať).
- Pridanie nového leadu (validácie).
- Upozornenia na blížiace sa „najbližšie kroky“ (po termíne / dnes / do 7 dní).
- Samostatná stránka **Summary** so štatistikami a grafmi.

## Inštalácia
```bash
cd remark_crm_app
python -m venv .crmvenv
source .crmvenv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Spustenie
```bash
streamlit run app.py
```

## Dáta a import
- Pri prvom spustení sa databáza naplní zo súboru **/mnt/data/CRM_leads_REMARK_FIXED.xlsx** (sheet **Leads**), ak existuje.
- Následne môžete:
  - pridávať leady manuálne cez tlačidlo **„Nový lead“**,
  - importovať Excel so stĺpcami: *Meno zákazníka, Telefón, Email, Mesto, Typ dopytu, Dátum pôvodného kontaktu, Stav projektu, Kto je konkurencia, Cena konkurencie, Naša ponuka (orientačná), Reakcia zákazníka, Dohodnutý ďalší krok, Dátum ďalšieho kroku, Priorita, Stav leadu, Orientačná cena (€), Dátum realizácie, Poznámky*,
  - alebo importovať CSV (mapovanie: `Meno`→Meno zákazníka, `Email`→Email, `Phone`→Telefón, `Vytovorene`→Dátum pôvodného kontaktu).
- Databáza sa ukladá do súboru **remark_crm.db** v koreňovom priečinku projektu.

## Poznámky
- Časová zóna: **Europe/Bratislava** (pre výpočty termínov).
- Na tabuľku sa používa **streamlit-aggrid** (podpora multi‑sort/filtra, inline editácie a štýlovania).
