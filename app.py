# -*- coding: utf-8 -*-
import os
from datetime import date
import pandas as pd
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
    import_from_excel_mapped,
    remove_duplicate_leads,
)
from utils import (
    slovak_tz_now_date,
    badges_counts,
    parse_date_safe,
    categories_from_db,
)
from prefs import (
    load_grid_prefs,
    save_grid_prefs,
    load_category_prefs,
    save_category_prefs,
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

# Ensure no duplicate leads exist
remove_duplicate_leads(SessionLocal)

# Fetch data and stats
df_all = fetch_leads_df(SessionLocal)
today = slovak_tz_now_date()
overdue, today_cnt, next7 = badges_counts(df_all, today)

# Load category preferences
cats = categories_from_db(df_all)
user_cats = load_category_prefs()
for k, v in user_cats.items():
    if isinstance(v, list) and v:
        cats[k] = v

# Sidebar with stats and settings
with st.sidebar:
    st.header("Štatistiky")
    st.metric("Leadov", len(df_all))
    st.metric("Po termíne", overdue)
    st.metric("Dnes", today_cnt)
    st.metric("Najbližších 7 dní", next7)
    st.markdown("---")
    st.header("Nastavenia")
    with st.form("settings_form", clear_on_submit=False):
        st.write("Možnosti pre stĺpce (oddelené čiarkou)")
        stav_leadu_text = st.text_input("Stav leadu", ",".join(cats["stav_leadu"]))
        priorita_text = st.text_input("Priorita", ",".join(cats["priorita"]))
        stav_proj_text = st.text_input("Stav projektu", ",".join(cats.get("stav_projektu", [])))
        typ_dopytu_text = st.text_input("Typ dopytu", ",".join(cats["typ_dopytu"]))
        mesto_text = st.text_input("Mesto", ",".join(cats["mesto"]))
        saved_settings = st.form_submit_button("Uložiť")
        if saved_settings:
            new_settings = {
                "stav_leadu": [s.strip() for s in stav_leadu_text.split(",") if s.strip()],
                "priorita": [s.strip() for s in priorita_text.split(",") if s.strip()],
                "stav_projektu": [s.strip() for s in stav_proj_text.split(",") if s.strip()],
                "typ_dopytu": [s.strip() for s in typ_dopytu_text.split(",") if s.strip()],
                "mesto": [s.strip() for s in mesto_text.split(",") if s.strip()],
            }
            save_category_prefs(new_settings)
            st.success("Uložené")
            st.experimental_rerun()

# Header
st.title("📋 REMARK CRM – Leads")
st.caption(f"{today.strftime('%Y-%m-%d')} • Leadov: {len(df_all)}")

c_search, c_new = st.columns([3,1])
with c_search:
    quick_search = st.text_input("Hľadať", placeholder="meno, email, mesto, poznámky ...", label_visibility="collapsed")
with c_new:
    if st.button("➕ Nový lead", use_container_width=True):
        st.session_state["show_new_lead_modal"] = True

# Auto-import from default Excel path if available and not imported yet in this session
default_excel_path = "/data/leads.xlsx"
if os.path.exists(default_excel_path) and not st.session_state.get("auto_excel_import_done"):
    import_from_excel_mapped(SessionLocal, default_excel_path)
    remove_duplicate_leads(SessionLocal)
    st.session_state["auto_excel_import_done"] = True
    df_all = fetch_leads_df(SessionLocal)

# Auto-import from default CSV path if available
default_csv_path = "/data/leads.csv"
if os.path.exists(default_csv_path) and not st.session_state.get("auto_csv_import_done"):
    import_from_csv_mapped(SessionLocal, default_csv_path)
    remove_duplicate_leads(SessionLocal)
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
        for col in [
            "meno_zakaznika",
            "telefon",
            "email",
            "mesto",
            "typ_dopytu",
            "stav_projektu",
            "reakcia_zakaznika",
            "dalsi_krok",
            "poznamky",
        ]:
            if col in df.columns:
                mask = mask | df[col].fillna("").str.lower().str.contains(q)
        df = df[mask]

# Editable fields inline
editable_cols = [c for c in df.columns if c != "id"]

# Load grid preferences (order/width)
grid_prefs = load_grid_prefs()
col_state = grid_prefs.get("column_state")
width_map = {}
if col_state:
    ordered = [c["colId"] for c in sorted(col_state, key=lambda x: x.get("order", 0)) if c.get("colId") in df.columns]
    remaining = [c for c in df.columns if c not in ordered]
    if ordered:
        df = df[ordered + remaining]
    width_map = {c["colId"]: c.get("width") for c in col_state if c.get("width")}

# Build AgGrid
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_default_column(
    sortable=True,
    filter=True,
    resizable=True,
    editable=True,
)

# Select editors for certain columns based on preferences
stav_leadu_opts = cats["stav_leadu"]
priorita_opts = cats["priorita"]
stav_proj_opts = cats.get("stav_projektu", [])
typ_dopytu_opts = cats["typ_dopytu"]
mesto_opts = cats["mesto"]

# Configure columns
for col in df.columns:
    col_width = width_map.get(col)
    if col == "id":
        gb.configure_column(col, header_name="ID", hide=True)
    elif col in ["nasa_ponuka_orientacna", "orientacna_cena", "cena_konkurencie"]:
        gb.configure_column(
            col,
            type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
            valueFormatter="value==null? '' : value.toLocaleString()",
            width=col_width,
        )
    elif col in ["datum_povodneho_kontaktu", "datum_dalsieho_kroku", "datum_realizacie"]:
        gb.configure_column(col, filter="agDateColumnFilter", width=col_width)
    elif col == "stav_leadu":
        gb.configure_column(
            col,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": stav_leadu_opts},
            width=col_width,
        )
    elif col == "priorita":
        gb.configure_column(
            col,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": priorita_opts},
            width=col_width,
        )
    elif col == "stav_projektu":
        gb.configure_column(
            col,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": stav_proj_opts},
            width=col_width,
        )
    elif col == "typ_dopytu":
        gb.configure_column(
            col,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": typ_dopytu_opts},
            width=col_width,
        )
    elif col == "mesto":
        gb.configure_column(
            col,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": mesto_opts},
            width=col_width,
        )
    else:
        if col_width:
            gb.configure_column(col, width=col_width)

gb.configure_selection('single', use_checkbox=False)
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
    allow_unsafe_jscode=True,
    columns_state=col_state,
    update_on=[
        "cellValueChanged",
        "selectionChanged",
        "columnResized",
        "columnMoved",
    ],
)

current_df = pd.DataFrame(grid_resp["data"])
selected_rows = grid_resp.get("selected_rows", [])

# Save column state preferences
try:
    if grid_resp.columns_state:
        save_grid_prefs({"column_state": grid_resp.columns_state})
except Exception:
    pass

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
            st.selectbox(
                "Mesto",
                options=mesto_opts or [row.get("mesto", "")],
                index=(mesto_opts.index(row.get("mesto")) if row.get("mesto") in mesto_opts else 0) if mesto_opts else 0,
                key=f"mesto_{rid}",
            )
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

# --- New lead dialog ---
if st.session_state.get("show_new_lead_modal"):
    @st.dialog("Nový lead")
    def new_lead_dialog():
        st.write(
            "Vyplňte údaje. Položky *Meno*, aspoň jeden kontakt (*Telefón* alebo *Email*) a *Dátum pôvodného kontaktu* sú povinné."
        )
        with st.form("new_lead_form", clear_on_submit=True):
            meno = st.text_input("Meno zákazníka*")
            tel = st.text_input("Telefón")
            email = st.text_input("Email")
            mesto = st.selectbox("Mesto", options=mesto_opts or [""], index=0)
            typ = st.selectbox("Typ dopytu", options=typ_dopytu_opts or [""], index=0)
            dpc = st.date_input("Dátum pôvodného kontaktu*", value=date.today())
            stavproj = st.selectbox("Stav projektu", options=stav_proj_opts or [""], index=0)
            konkur = st.text_input("Konkurencia")
            cena_k = st.number_input("Cena konkurencie", min_value=0.0, step=100.0)
            nasa = st.number_input("Naša ponuka (orient.)", min_value=0.0, step=100.0)
            reak = st.text_area("Reakcia zákazníka")
            dalsi = st.text_input("Ďalší krok")
            ddk = st.date_input("Dátum ďalšieho kroku", value=None)
            prio = st.selectbox("Priorita", priorita_opts, index=1 if len(priorita_opts) > 1 else 0)
            stavlead = st.selectbox("Stav leadu", stav_leadu_opts, index=0)
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
                        poznamky=poz.strip(),
                    )
                    rid = insert_lead(SessionLocal, payload)
                    if rid:
                        st.success("Lead pridaný.")
                        st.session_state["show_new_lead_modal"] = False
                        st.rerun()
                    else:
                        st.warning("Lead nebol pridaný (duplicita).")
        if st.button("Zavrieť"):
            st.session_state["show_new_lead_modal"] = False
            st.rerun()

    new_lead_dialog()

# --- Footer with import and refresh ---
st.markdown("---")
f1, f2, f3 = st.columns([1,1,2])
with f1:
    uploaded_file = st.file_uploader(
        "Import Excel/CSV",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=False,
    )
    if uploaded_file is not None:
        try:
            name = uploaded_file.name.lower()
            if name.endswith((".xls", ".xlsx")):
                imported, skipped = import_from_excel_mapped(SessionLocal, uploaded_file)
            else:
                imported, skipped = import_from_csv_mapped(SessionLocal, uploaded_file)
            remove_duplicate_leads(SessionLocal)
            st.success(f"Importované: {imported}, Preskočené: {skipped}")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Import zlyhal: {e}")
with f2:
    if st.button("🔁 Obnoviť", use_container_width=True):
        st.experimental_rerun()
with f3:
    st.caption("Pozn.: Môžete tiež vložiť súbor 'leads.xlsx' alebo 'leads.csv' do /mnt/data a obnoviť stránku.")

st.caption("⏱️ Časová zóna: Europe/Bratislava")
