
# -*- coding: utf-8 -*-
import pandas as pd
from datetime import date, datetime, timedelta
import pytz
import streamlit as st
import plotly.express as px

from db import get_engine_session, fetch_leads_df
from utils import slovak_tz_now_date, badges_counts

st.set_page_config(page_title="REMARK CRM - Summary", page_icon="📈", layout="wide")

st.title("📈 Summary & Štatistiky")

engine, SessionLocal = get_engine_session()
df = fetch_leads_df(SessionLocal)
today = slovak_tz_now_date()

if df.empty:
    st.info("Zatiaľ nemáme žiadne dáta.")
    st.stop()

# --- Počty podľa stavu leadu + konverzná miera ---
col1, col2 = st.columns([2,1])
with col1:
    counts_state = df["stav_leadu"].fillna("Neznáme").value_counts().reset_index()
    counts_state.columns = ["stav_leadu", "počet"]
    fig1 = px.bar(counts_state, x="stav_leadu", y="počet", title="Počty leadov podľa stavu", text="počet")
    st.plotly_chart(fig1, use_container_width=True)
with col2:
    total = len(df)
    converted = (df["stav_leadu"] == "Converted").sum()
    conv_rate = (converted / total * 100) if total else 0
    st.metric("Konverzná miera", f"{conv_rate:.1f}%",
              help="Podiel Converted zo všetkých leadov")

# --- Počty podľa priority ---
counts_prio = df["priorita"].fillna("Neznáme").value_counts().reset_index()
counts_prio.columns = ["priorita", "počet"]
fig2 = px.pie(counts_prio, names="priorita", values="počet", title="Počty podľa priority", hole=0.35)
st.plotly_chart(fig2, use_container_width=True)

# --- Počty podľa typ_dopytu a mesto ---
col3, col4 = st.columns(2)
with col3:
    counts_typ = df["typ_dopytu"].fillna("Neznáme").value_counts().reset_index()
    counts_typ.columns = ["typ_dopytu", "počet"]
    fig3 = px.bar(counts_typ, x="typ_dopytu", y="počet", title="Počty podľa typu dopytu", text="počet")
    st.plotly_chart(fig3, use_container_width=True)
with col4:
    counts_city = df["mesto"].fillna("Neznáme").value_counts().reset_index()
    counts_city.columns = ["mesto", "počet"]
    fig4 = px.bar(counts_city, x="mesto", y="počet", title="Počty podľa mesta", text="počet")
    st.plotly_chart(fig4, use_container_width=True)

# --- Priemerné dni od pôvodného kontaktu po realizáciu (len Converted) ---
df_conv = df[df["stav_leadu"] == "Converted"].copy()
if not df_conv.empty:
    d1 = pd.to_datetime(df_conv["datum_povodneho_kontaktu"], errors="coerce")
    d2 = pd.to_datetime(df_conv["datum_realizacie"], errors="coerce")
    days = (d2 - d1).dt.days.dropna()
    avg_days = days.mean() if not days.empty else 0
    st.metric("Priemerné dni od kontaktu po realizáciu", f"{avg_days:.1f} dňa")
else:
    st.info("Žiadne 'Converted' leady pre výpočet priemerných dní.")

st.markdown("---")

# --- Porovnanie ponúk ---
price_cols = ["nasa_ponuka_orientacna", "cena_konkurencie"]
df_prices = df[price_cols].copy().dropna(how="all")
if not df_prices.empty:
    df_long = df_prices.melt(value_vars=price_cols, var_name="typ", value_name="cena").dropna()
    df_long["typ"] = df_long["typ"].map({
        "nasa_ponuka_orientacna": "Naša ponuka",
        "cena_konkurencie": "Cena konkurencie"
    })
    col5, col6 = st.columns(2)
    with col5:
        fig_box = px.box(df_long, x="typ", y="cena", points="all", title="Porovnanie: Naša ponuka vs. konkurencia (boxplot)")
        st.plotly_chart(fig_box, use_container_width=True)
    with col6:
        fig_strip = px.strip(df_long, x="typ", y="cena", title="Rozptyl cien (strip)")
        st.plotly_chart(fig_strip, use_container_width=True)
else:
    st.info("Chýbajú údaje o cenách pre porovnanie.")

# --- Počet blížiacich sa krokov ---
overdue, today_cnt, next7 = badges_counts(df, today)
c7, c8, c9 = st.columns(3)
c7.metric("Po termíne", overdue)
c8.metric("Dnes", today_cnt)
c9.metric("Najbližších 7 dní", next7)

# --- Trend nových leadov ---
df["dpc"] = pd.to_datetime(df["datum_povodneho_kontaktu"], errors="coerce")
df_valid = df.dropna(subset=["dpc"]).copy()
if not df_valid.empty:
    period = st.radio("Zoskupiť podľa", ["Týždne","Mesiace"], horizontal=True, index=1)
    if period == "Týždne":
        df_valid["period"] = df_valid["dpc"].dt.to_period("W").dt.to_timestamp()
    else:
        df_valid["period"] = df_valid["dpc"].dt.to_period("M").dt.to_timestamp()
    trend = df_valid.groupby("period").size().reset_index(name="počet")
    fig_trend = px.line(trend, x="period", y="počet", markers=True, title="Trend nových leadov")
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("Chýbajú dátumy pôvodného kontaktu pre zobrazenie trendu.")
