# -*- coding: utf-8 -*-
import os
import io
from datetime import datetime, date, timedelta
import pytz
import pandas as pd
import numpy as np
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

from db import (
    init_db,
    get_engine_session,
    fetch_leads_df,
    insert_lead,
    update_leads_bulk,
    update_single_lead,
    import_initial_from_excel,
    import_from_csv_mapped,
    ensure_category_values,
)
from utils import (
    slovak_tz_now_date,
    normalize_df_columns,
    clean_dataframe_for_db,
    badges_counts,
    parse_date_safe,
    categories_from_db,
    unique_sorted,
)

st.set_page_config(page_title="REMARK CRM - Leads", page_icon="📋", layout="wide")

TZ = "Europe/Bratislava"

# Initialize DB and seed from Excel once
engine, SessionLocal = get_engine_session()
init_db(engine)

# Seed from Excel if table is empty
excel_default_path = "/data/CRM_leads_REMARK_FIXED.xlsx"
try:
    import_initial_from_excel(SessionLocal, excel_default_path)
except Exception as e:
    st.error(f"Import z Excelu zlyhal: {e}")

# Top header
st.title("📋 REMARK CRM – Leads")

# Info badges (next steps)
df_all = fetch_leads_df(SessionLocal)
today = slovak_tz_now_date()

overdue, today_cnt, next7 = badges_counts(df_all, today)
badge_html = f"""
<div style='display:flex; gap:12px; flex-wrap:wrap; margin-top: -6px; margin-bottom: 8px;'>
  <div style='background:#ffe6e6; color:#a30000; padding:6px 10px; border-radius:999px; font-weight:600;'>🔴 Po termíne: {overdue}</div>
  <div style='background:#e6f7ff; color:#004d80; padding:6px 10px; border-radius:999px; font-weight:700; border:2px solid #66c2ff;'>📌 Dnes: {today_cnt}</div>
  <div style='background:#fff8e6; color:#8a5a00; padding:6px 10px; border-radius:999px; font-weight:600;'>🟡 Najbližších 7 dní: {next7}</div>
  <div style='margin-left:6px; opacity:0.8;'>Dnešný dátum: {today.strftime('%Y-%m-%d')}</div>
</div>
"""
st.markdown(badge_html, unsafe_allow_html=True)

# --- Controls row ---
c1, c2, c3, c4, c5 = st.columns([1,1,1,1,2])
with c1:
    st.caption("Full‑text vyhľadávanie")
    quick_search = st.text_input("Hľadať", placeholder="meno, email, mesto, poznámky ...", label_visibility="collapsed")
with c2:
    if st.button("➕ Nový lead", use_container_width=True):
        st.session_state["show_new_lead_modal"] = True
with c3:
    uploaded_csv = st.file_uploader("Import CSV", type=["csv"], accept_multiple_files=False, label_visibility="collapsed")
    if uploaded_csv is not None:
        try:
            imported, skipped = import_from_csv_mapped(SessionLocal, uploaded_csv)
            st.success(f"Importované: {imported}, Preskočené: {skipped}")
            df_all = fetch_leads_df(SessionLocal)
        except Exception as e:
            st.error(f"Import zlyhal: {e}")
with c4:
    # quick refresh
    if st.button("🔁 Obnoviť", use_container_width=True):
        df_all = fetch_leads_df(SessionLocal)
with c5:
    st.caption("Pozn.: Môžete tiež vložiť súbor 'leads.csv' do /mnt/data a obnoviť stránku.")

# Auto-import from default CSV path if available and not imported yet in this session
default_csv_path = "/data/leads.csv"
if os.path.exists(default_csv_path) and not st.session_state.get("auto_csv_import_done"):
    import_from_csv_mapped(SessionLocal, default_csv_path)
    st.session_state["auto_csv_import_done"] = True
    df_all = fetch_leads_df(SessionLocal)

# --- Filter panel ---
with st.expander("🔎 Filtery", expanded=False):
    # category values from DB
    cats = categories_from_db(df_all)

    colf1, colf2, colf3, colf4, colf5 = st.columns(5)
    with colf1:
        f_stav_leadu = st.multiselect("Stav leadu", options=cats["stav_leadu"], default=[])
    with colf2:
        f_priorita = st.multiselect("Priorita", options=cats["priorita"], default=[])
    with colf3:
        f_typ = st.multiselect("Typ dopytu", options=cats["typ_dopytu"], default=[])
    with colf4:
        f_mesto = st.multiselect("Mesto", options=cats["mesto"], default=[])
    # Odstránený filter rozsah (colf5)

# Apply filters and full-text
df = df_all.copy()
if f_stav_leadu:
    df = df[df["stav_leadu"].isin(f_stav_leadu)]
if f_priorita:
    df = df[df["priorita"].isin(f_priorita)]
if f_typ:
    df = df[df["typ_dopytu"].isin(f_typ)]
if f_mesto:
    df = df[df["mesto"].isin(f_mesto)]
# Odstránený filter podľa dátumu
#
if quick_search:
    q = quick_search.lower().strip()
    if q:
        mask = pd.Series(False, index=df.index)
        for col in ["meno_zakaznika","telefon","email","mesto","typ_dopytu","stav_projektu","reakcia_zakaznika","dalsi_krok","poznamky"]:
            if col in df.columns:
                mask = mask | df[col].fillna("").str.lower().str.contains(q)
        df = df[mask]

# Editable fields inline
editable_cols = ["stav_leadu","priorita","stav_projektu","dalsi_krok","datum_dalsieho_kroku","poznamky","nasa_ponuka_orientacna"]

# Build AgGrid
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_default_column(
    sortable=True,
    filter=True,
    resizable=True,
)

# Select editors for certain columns based on unique values from DB
stav_leadu_opts = unique_sorted(df_all["stav_leadu"].dropna().tolist() + ["Open","Cold","Converted","Lost"])
priorita_opts = unique_sorted(df_all["priorita"].dropna().tolist() + ["Vysoká","Stredná","Nízka"])
stav_proj_opts = unique_sorted(df_all["stav_projektu"].dropna().tolist())
typ_dopytu_opts = unique_sorted(df_all["typ_dopytu"].dropna().tolist())

# Configure columns
for col in df.columns:
    if col == "id":
        gb.configure_column(col, header_name="ID", hide=True)
    elif col in ["nasa_ponuka_orientacna","orientacna_cena","cena_konkurencie"]:
        gb.configure_column(col, type=["numericColumn","numberColumnFilter","customNumericFormat"], valueFormatter="value==null? '': value.toLocaleString()")
    elif col in ["datum_povodneho_kontaktu","datum_dalsieho_kroku","datum_realizacie"]:
        gb.configure_column(col, filter="agDateColumnFilter")
    elif col == "stav_leadu":
        gb.configure_column(col, editable=True, cellEditor="agSelectCellEditor", cellEditorParams={"values": stav_leadu_opts})
    elif col == "priorita":
        gb.configure_column(col, editable=True, cellEditor="agSelectCellEditor", cellEditorParams={"values": priorita_opts})
    elif col == "stav_projektu":
        gb.configure_column(col, editable=True, cellEditor="agSelectCellEditor", cellEditorParams={"values": stav_proj_opts})
    elif col == "typ_dopytu":
        gb.configure_column(col, cellEditor="agSelectCellEditor", cellEditorParams={"values": typ_dopytu_opts})
    elif col in editable_cols:
        gb.configure_column(col, editable=True)
    else:
        gb.configure_column(col)

gb.configure_selection('single', use_checkbox=True)
gb.configure_side_bar()
gb.configure_grid_options(
    rowSelection="single",
    rowMultiSelectWithClick=False,
    suppressRowClickSelection=False,
    animateRows=True,
    enableRangeSelection=True,
    rememberGroupStateWhenNewData=True,
    pagination=True,
    paginationPageSize=25,
    suppressAggFuncInHeader=True,
    multiSortKey="ctrl",
    quickFilterText=quick_search if quick_search else "",
)

# Row styling: by stav_leadu and priorita
row_style_js = JsCode("""
function(params) {
    const v = params.data;
    if (!v) return {};
    // Lost -> strike-through + grey
    if (v.stav_leadu === 'Lost') {
        return { 'textDecoration': 'line-through', 'color': '#666', 'backgroundColor': 'rgba(200,200,200,0.15)' };
    }
    // Cold -> grey background wins
    if (v.stav_leadu === 'Cold') {
        return { 'backgroundColor': 'rgba(160,160,160,0.10)' };
    }
    // otherwise by priority
    if (v.priorita === 'Vysoká') return { 'backgroundColor': 'rgba(255,0,0,0.08)' };
    if (v.priorita === 'Stredná') return { 'backgroundColor': 'rgba(255,165,0,0.10)' };
    if (v.priorita === 'Nízka') return { 'backgroundColor': 'rgba(0,120,255,0.08)' };
    return {};
}
""")
# Cell style for next step date proximity
date_cell_style_js = JsCode("""
function(params) {
  const raw = params.value;
  if (!raw) return {};
  const today = new Date(); today.setHours(0,0,0,0);
  const dt = new Date(raw);
  const diffDays = Math.floor((dt - today) / 86400000);
  if (dt < today) return {'backgroundColor':'#ffe6e6', 'fontWeight':'700'}; // overdue
  if (diffDays === 0) return {'backgroundColor':'#e6f7ff', 'fontWeight':'700', 'border':'2px solid #66c2ff'}; // today
  if (diffDays <= 7) return {'backgroundColor':'#fff8e6', 'fontWeight':'600'}; // next 7
  return {};
}
""")

gb.configure_grid_options(getRowStyle=row_style_js)
gb.configure_column("datum_dalsieho_kroku", cellStyle=date_cell_style_js)

grid_options = gb.build()

# Keep cache of last df for change detection
if "last_grid_df" not in st.session_state:
    st.session_state["last_grid_df"] = df.copy()

grid_resp = AgGrid(
    df,
    gridOptions=grid_options,
    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
    update_mode=GridUpdateMode.VALUE_CHANGED | GridUpdateMode.SELECTION_CHANGED,
    theme="balham",
    height=560,
    fit_columns_on_grid_load=True,
    allow_unsafe_jscode=True
)

current_df = pd.DataFrame(grid_resp["data"])
selected_rows = grid_resp.get("selected_rows", [])

# Detect inline edits by comparing current_df to last_grid_df for editable columns
try:
    prev = st.session_state["last_grid_df"].set_index("id")
    cur = current_df.set_index("id")
    changed_ids = []
    updates = []
    for rid in cur.index:
        if rid in prev.index:
            for col in editable_cols:
                old = prev.at[rid, col] if col in prev.columns else None
                new = cur.at[rid, col] if col in cur.columns else None
                if pd.isna(old) and pd.isna(new):
                    continue
                if (pd.isna(old) and pd.notna(new)) or (pd.notna(old) and pd.isna(new)) or (old != new):
                    changed_ids.append(int(rid))
                    updates.append({"id": int(rid), col: new})
    if updates:
        # Consolidate updates by id
        consolidated = {}
        for upd in updates:
            rid = upd["id"]
            consolidated.setdefault(rid, {"id": rid})
            consolidated[rid].update(upd)
        update_payload = list(consolidated.values())
        if update_payload:
            updated_n = update_leads_bulk(SessionLocal, update_payload)
            if updated_n > 0:
                st.toast(f"Uložené inline zmeny: {updated_n}", icon="✅")
                # refresh df_all
                df_all = fetch_leads_df(SessionLocal)
except Exception as e:
    st.warning(f"Problém pri ukladaní inline zmien: {e}")

st.session_state["last_grid_df"] = current_df.copy()

# --- Detail panel ---
st.markdown("---")
left, right = st.columns([2,1], gap="large")

with left:
    st.subheader("Prehľad leadov")
    st.caption("Tip: podržte CTRL pri triedení pre multi-sort. V tabuľke môžete upraviť vybrané stĺpce.")
    # Nothing else; grid shown above

with right:
    st.subheader("Detail / Rýchle akcie")
    if selected_rows:
        row = selected_rows[0]
        rid = int(row["id"])
        with st.form(f"detail_{rid}", clear_on_submit=False):
            st.text_input("Meno zákazníka", key=f"meno_{rid}", value=row.get("meno_zakaznika",""))
            st.text_input("Telefón", key=f"tel_{rid}", value=row.get("telefon",""))
            st.text_input("Email", key=f"email_{rid}", value=row.get("email",""))
            st.text_input("Mesto", key=f"mesto_{rid}", value=row.get("mesto",""))
            st.selectbox("Typ dopytu", options=typ_dopytu_opts or [row.get("typ_dopytu","")], index= (typ_dopytu_opts.index(row.get("typ_dopytu")) if row.get("typ_dopytu") in typ_dopytu_opts else 0) if typ_dopytu_opts else 0, key=f"typ_{rid}")
            st.date_input("Dátum pôvodného kontaktu", value=parse_date_safe(row.get("datum_povodneho_kontaktu")), key=f"dpc_{rid}")
            st.selectbox("Stav projektu", options=stav_proj_opts or [row.get("stav_projektu","")], index=(stav_proj_opts.index(row.get("stav_projektu")) if row.get("stav_projektu") in stav_proj_opts else 0) if stav_proj_opts else 0, key=f"stavproj_{rid}")
            st.text_input("Konkurencia", key=f"konk_{rid}", value=row.get("konkurencia",""))
            st.number_input("Cena konkurencie", value=float(row.get("cena_konkurencie") or 0.0), step=100.0, key=f"ck_{rid}")
            st.number_input("Naša ponuka (orient.)", value=float(row.get("nasa_ponuka_orientacna") or 0.0), step=100.0, key=f"npo_{rid}")
            st.text_area("Reakcia zákazníka", key=f"reak_{rid}", value=row.get("reakcia_zakaznika",""))
            st.text_input("Ďalší krok", key=f"dk_{rid}", value=row.get("dalsi_krok",""))
            st.date_input("Dátum ďalšieho kroku", key=f"ddk_{rid}", value=parse_date_safe(row.get("datum_dalsieho_kroku")))
            st.selectbox("Priorita", options=priorita_opts, index=(priorita_opts.index(row.get("priorita")) if row.get("priorita") in priorita_opts else 1), key=f"prio_{rid}")
            st.selectbox("Stav leadu", options=stav_leadu_opts, index=(stav_leadu_opts.index(row.get("stav_leadu")) if row.get("stav_leadu") in stav_leadu_opts else 0), key=f"stavlead_{rid}")
            st.number_input("Orientačná cena", value=float(row.get("orientacna_cena") or 0.0), step=100.0, key=f"oc_{rid}")
            st.date_input("Dátum realizácie", key=f"dr_{rid}", value=parse_date_safe(row.get("datum_realizacie")))
            st.text_area("Poznámky", key=f"poz_{rid}", value=row.get("poznamky",""))

            saved = st.form_submit_button("💾 Uložiť")
            if saved:
                payload = {
                    "id": rid,
                    "meno_zakaznika": st.session_state[f"meno_{rid}"],
                    "telefon": st.session_state[f"tel_{rid}"],
                    "email": st.session_state[f"email_{rid}"],
                    "mesto": st.session_state[f"mesto_{rid}"],
                    "typ_dopytu": st.session_state.get(f"typ_{rid}"),
                    "datum_povodneho_kontaktu": st.session_state.get(f"dpc_{rid}"),
                    "stav_projektu": st.session_state.get(f"stavproj_{rid}"),
                    "konkurencia": st.session_state.get(f"konk_{rid}"),
                    "cena_konkurencie": st.session_state.get(f"ck_{rid}"),
                    "nasa_ponuka_orientacna": st.session_state.get(f"npo_{rid}"),
                    "reakcia_zakaznika": st.session_state.get(f"reak_{rid}"),
                    "dalsi_krok": st.session_state.get(f"dk_{rid}"),
                    "datum_dalsieho_kroku": st.session_state.get(f"ddk_{rid}"),
                    "priorita": st.session_state.get(f"prio_{rid}"),
                    "stav_leadu": st.session_state.get(f"stavlead_{rid}"),
                    "orientacna_cena": st.session_state.get(f"oc_{rid}"),
                    "datum_realizacie": st.session_state.get(f"dr_{rid}"),
                    "poznamky": st.session_state.get(f"poz_{rid}"),
                }
                update_single_lead(SessionLocal, payload)
                st.success("Uložené")
                st.experimental_rerun()

        # Quick actions
        st.markdown("#### ⚡ Rýchle akcie")
        qa1, qa2, qa3 = st.columns(3)
        with qa1:
            new_status = st.selectbox("Zmeniť stav", stav_leadu_opts, index=(stav_leadu_opts.index(row.get("stav_leadu")) if row.get("stav_leadu") in stav_leadu_opts else 0), key=f"qa_stav_{rid}")
            if st.button("Uložiť stav", key=f"btn_stav_{rid}", use_container_width=True):
                update_single_lead(SessionLocal, {"id": rid, "stav_leadu": new_status})
                st.experimental_rerun()
        with qa2:
            dk = st.text_input("Ďalší krok", value=row.get("dalsi_krok",""), key=f"qa_dk_{rid}")
            dkd = st.date_input("Dátum kroku", value=parse_date_safe(row.get("datum_dalsieho_kroku")), key=f"qa_dkd_{rid}")
            if st.button("Nastaviť krok", key=f"btn_krok_{rid}", use_container_width=True):
                update_single_lead(SessionLocal, {"id": rid, "dalsi_krok": dk, "datum_dalsieho_kroku": dkd})
                st.experimental_rerun()
        with qa3:
            if st.button("✅ Konvertovať", key=f"btn_conv_{rid}", type="primary", use_container_width=True):
                update_single_lead(SessionLocal, {"id": rid, "stav_leadu": "Converted", "datum_realizacie": date.today()})
                st.experimental_rerun()
    else:
        st.info("Vyberte riadok v tabuľke pre zobrazenie detailu a akcií.")

# --- New lead modal ---
if st.session_state.get("show_new_lead_modal"):
    with st.modal("Nový lead"):
        st.write("Vyplňte údaje. Položky *Meno*, aspoň jeden kontakt (*Telefón* alebo *Email*) a *Dátum pôvodného kontaktu* sú povinné.")
        with st.form("new_lead_form", clear_on_submit=True):
            meno = st.text_input("Meno zákazníka*")
            tel = st.text_input("Telefón")
            email = st.text_input("Email")
            mesto = st.text_input("Mesto")
            typ = st.text_input("Typ dopytu")
            dpc = st.date_input("Dátum pôvodného kontaktu*", value=date.today())
            stavproj = st.text_input("Stav projektu")
            konkur = st.text_input("Konkurencia")
            cena_k = st.number_input("Cena konkurencie", min_value=0.0, step=100.0)
            nasa = st.number_input("Naša ponuka (orient.)", min_value=0.0, step=100.0)
            reak = st.text_area("Reakcia zákazníka")
            dalsi = st.text_input("Ďalší krok")
            ddk = st.date_input("Dátum ďalšieho kroku", value=None)
            prio = st.selectbox("Priorita", ["Vysoká","Stredná","Nízka"], index=1)
            stavlead = st.selectbox("Stav leadu", ["Open","Cold","Converted","Lost"], index=0)
            oc = st.number_input("Orientačná cena", min_value=0.0, step=100.0)
            dr = st.date_input("Dátum realizácie", value=None)
            poz = st.text_area("Poznámky")
            submit = st.form_submit_button("Uložiť")
            if submit:
                errors = []
                if not meno.strip():
                    errors.append("Meno zákazníka je povinné.")
                if not tel.strip() and not email.strip():
                    errors.append("Uveďte telefón alebo email.")
                if not dpc:
                    errors.append("Dátum pôvodného kontaktu je povinný.")
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    payload = dict(
                        meno_zakaznika=meno.strip(),
                        telefon=tel.strip(),
                        email=email.strip(),
                        mesto=mesto.strip(),
                        typ_dopytu=typ.strip(),
                        datum_povodneho_kontaktu=dpc,
                        stav_projektu=stavproj.strip(),
                        konkurencia=konkur.strip(),
                        cena_konkurencie=cena_k,
                        nasa_ponuka_orientacna=nasa,
                        reakcia_zakaznika=reak.strip(),
                        dalsi_krok=dalsi.strip(),
                        datum_dalsieho_kroku=ddk,
                        priorita=prio,
                        stav_leadu=stavlead,
                        orientacna_cena=oc,
                        datum_realizacie=dr,
                        poznamky=poz.strip()
                    )
                    insert_lead(SessionLocal, payload)
                    st.success("Lead pridaný.")
                    st.session_state["show_new_lead_modal"] = False
                    st.experimental_rerun()
        if st.button("Zavrieť"):
            st.session_state["show_new_lead_modal"] = False
            st.experimental_rerun()

# --- Add new lead form ---
with st.form("Pridať nový lead"):
    meno = st.text_input("Meno")
    email = st.text_input("Email")
    datum_kroku = st.date_input("Dátum ďalšieho kroku")
    submitted = st.form_submit_button("Pridať")
    if submitted:
        insert_lead(SessionLocal, meno=meno, email=email, datum_dalsieho_kroku=datum_kroku)
        st.success("Lead pridaný!")

st.caption("⏱️ Časová zóna: Europe/Bratislava")
st.write("Počet leadov v DB:", fetch_leads_df(SessionLocal).shape[0])
