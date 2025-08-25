# -*- coding: utf-8 -*-
import os
import pandas as pd
import streamlit as st

from db import get_engine_session, fetch_leads_df, DB_PATH, clear_database
from prefs import (
    load_category_prefs,
    save_category_prefs,
    load_grid_prefs,
    save_grid_prefs,
)

st.set_page_config(page_title="REMARK CRM - Nastavenia", page_icon="⚙️", layout="wide")

st.title("⚙️ Nastavenia")

engine, SessionLocal = get_engine_session()
df = fetch_leads_df(SessionLocal)
all_columns = [c for c in df.columns if c != "id"]

# Distinct values from DB for placeholders
cats_db = {}
for col in all_columns:
    cats_db[col] = sorted([str(x) for x in df[col].dropna().unique().tolist() if str(x).strip()])

saved_cats = load_category_prefs()

st.subheader("Preddefinované hodnoty")
with st.form("cats_form"):
    selected_cols = st.multiselect(
        "Stĺpce s výberom",
        options=all_columns,
        default=list(saved_cats.keys()),
    )
    cat_inputs = {}
    for col in selected_cols:
        existing = saved_cats.get(col, cats_db.get(col, []))
        cat_inputs[col] = st.text_input(col, value=",".join(existing))

    cats_submitted = st.form_submit_button("Uložiť")
    if cats_submitted:
        new_cats = {}
        for col in selected_cols:
            val = cat_inputs[col]
            new_cats[col] = [s.strip() for s in val.split(",") if s.strip()]
        save_category_prefs(new_cats)
        st.success("Preddefinované hodnoty uložené")

st.subheader("Poradie a šírka stĺpcov")
grid_prefs = load_grid_prefs()
col_state = grid_prefs.get("column_state", [])
state_map = {c["colId"]: c for c in col_state}
ordered_cols = sorted(
    all_columns,
    key=lambda c: state_map.get(c, {}).get("order", all_columns.index(c)),
)
rows = []
for col in ordered_cols:
    st_info = state_map.get(col, {})
    rows.append({
        "column": col,
        "width": st_info.get("width"),
    })
df_state = pd.DataFrame(rows)
df_state.index.name = "poradie"

with st.form("grid_form"):
    edited = st.data_editor(
        df_state,
        use_container_width=True,
        column_config={
            "_index": st.column_config.NumberColumn("Poradie", disabled=True),
            "column": st.column_config.TextColumn("Stĺpec", disabled=True),
            "width": st.column_config.NumberColumn("Šírka", required=False),
        },
        key="grid_editor",
    )

    grid_submitted = st.form_submit_button("Uložiť")
    if grid_submitted:
        new_col_state = []
        for order, row in enumerate(edited.itertuples(index=False)):
            state = {"colId": row.column, "order": order}
            if pd.notna(row.width) and str(row.width).strip() != "":
                state["width"] = int(row.width)
            new_col_state.append(state)
        save_grid_prefs({"column_state": new_col_state})
        st.success("Poradie a šírka stĺpcov uložené")
        st.switch_page("app.py")

st.subheader("Správa databázy")
col1, col2, col3 = st.columns(3)
with col1:
    uploaded_db = st.file_uploader("Import databázy", type=["db"])
    if uploaded_db is not None:
        with open(DB_PATH, "wb") as f:
            f.write(uploaded_db.getbuffer())
        st.success("Databáza importovaná")
        st.experimental_rerun()
with col2:
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button("Export databázy", data=f, file_name="remark_crm.db")
    else:
        st.warning("Databázový súbor neexistuje")
with col3:
    if st.button("Vymazať databázu"):
        deleted = clear_database(SessionLocal)
        st.success(f"Vymazaných záznamov: {deleted}")
        st.experimental_rerun()
