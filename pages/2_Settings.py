# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from db import get_engine_session, fetch_leads_df
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

with st.form("settings_form"):
    st.subheader("Preddefinované hodnoty")
    selected_cols = st.multiselect(
        "Stĺpce s výberom",
        options=all_columns,
        default=list(saved_cats.keys()),
    )
    cat_inputs = {}
    for col in selected_cols:
        existing = saved_cats.get(col, cats_db.get(col, []))
        cat_inputs[col] = st.text_input(col, value=",".join(existing))

    st.subheader("Poradie a šírka stĺpcov")
    grid_prefs = load_grid_prefs()
    col_state = grid_prefs.get("column_state", [])
    state_map = {c["colId"]: c for c in col_state}
    rows = []
    for idx, col in enumerate(all_columns):
        st_info = state_map.get(col, {})
        rows.append({
            "column": col,
            "order": st_info.get("order", idx),
            "width": st_info.get("width", ""),
        })
    df_state = pd.DataFrame(rows)
    edited = st.data_editor(
        df_state,
        hide_index=True,
        use_container_width=True,
        column_config={
            "column": st.column_config.TextColumn("Stĺpec", disabled=True),
            "order": st.column_config.NumberColumn("Poradie"),
            "width": st.column_config.NumberColumn("Šírka", required=False),
        },
    )

    submitted = st.form_submit_button("Uložiť")
    if submitted:
        new_cats = {}
        for col in selected_cols:
            val = cat_inputs[col]
            new_cats[col] = [s.strip() for s in val.split(",") if s.strip()]
        save_category_prefs(new_cats)

        new_col_state = []
        edited_sorted = edited.sort_values("order")
        for _, row in edited_sorted.iterrows():
            state = {"colId": row["column"], "order": int(row["order"])}
            if pd.notna(row["width"]) and str(row["width"]).strip() != "":
                state["width"] = int(row["width"])
            new_col_state.append(state)
        save_grid_prefs({"column_state": new_col_state})

        st.success("Uložené")
