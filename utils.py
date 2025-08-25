# -*- coding: utf-8 -*-
from datetime import datetime, date
import pandas as pd
import numpy as np
import pytz
import re
from unidecode import unidecode

TZ = "Europe/Bratislava"

def slovak_tz_now_date() -> date:
    return datetime.now(pytz.timezone(TZ)).date()

def normalize_text_basic(s: str) -> str:
    if s is None:
        return ""
    return unidecode(str(s)).strip().lower()

def normalize_columns_generic(df: pd.DataFrame, aliases: dict) -> pd.DataFrame:
    """Lowercase, remove accents, map via aliases to target names."""
    new_cols = []
    for c in df.columns:
        key = normalize_text_basic(c)
        key = key.replace("_", " ").strip()
        if key in aliases:
            new_cols.append(aliases[key])
        else:
            # convert spaces to underscores and strip accents
            new_cols.append(re.sub(r"\s+", "_", key))
    df = df.copy()
    df.columns = new_cols
    return df

def normalize_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [re.sub(r"\s+", "_", normalize_text_basic(c)) for c in df.columns]
    return df

def parse_date_safe(val):
    """Parse input into a ``date`` or return ``None``.

    Historically this helper assumed values like ``np.nan`` or ``pd.NaT``
    would be caught by ``pd.to_datetime``.  However, calling ``.date()`` on a
    ``NaT`` results in a ``ValueError`` (``cannot convert float NaN to
    integer``) which bubbled up during Excel/CSV imports.  To make the import
    process robust we explicitly treat any "not a time"/"not a number" values
    as ``None`` before attempting the conversion.
    """
    if val in [None, "", "NaT", "nat"] or pd.isna(val):
        return None
    if isinstance(val, date):
        return val
    try:
        dt = pd.to_datetime(val, errors="coerce")
        return None if pd.isna(dt) else dt.date()
    except Exception:
        return None

def clean_dataframe_for_db(df: pd.DataFrame, ordered_cols) -> pd.DataFrame:
    """Ensure only DB columns, cast numeric and date fields."""
    df = df.copy()
    # keep only known columns
    keep = [c for c in ordered_cols if c in df.columns]
    df = df[keep]
    # numbers
    for c in ["cena_konkurencie","nasa_ponuka_orientacna","orientacna_cena"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # dates
    for c in ["datum_povodneho_kontaktu","datum_dalsieho_kroku","datum_realizacie"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    return df

def badges_counts(df, today):
    d = pd.to_datetime(df["datum_dalsieho_kroku"], errors="coerce")
    # Uistíme sa, že today je pandas Timestamp
    today_ts = pd.to_datetime(today)
    overdue = (d.notna() & (d < today_ts)).sum()
    today_cnt = (d.notna() & (d == today_ts)).sum()
    next7 = (d.notna() & (d > today_ts) & (d <= today_ts + pd.Timedelta(days=7))).sum()
    return overdue, today_cnt, next7

def categories_from_db(df: pd.DataFrame):
    def uniq(col):
        return sorted([x for x in df.get(col, pd.Series(dtype=object)).dropna().unique().tolist() if str(x).strip() != "" ])
    return {
        "stav_leadu": uniq("stav_leadu") or ["Open","Cold","Converted","Lost"],
        "priorita": uniq("priorita") or ["Vysoká","Stredná","Nízka"],
        "typ_dopytu": uniq("typ_dopytu"),
        "mesto": uniq("mesto"),
    }

def unique_sorted(values):
    try:
        vals = [v for v in values if v is not None and str(v).strip() != ""]
        return sorted(list(dict.fromkeys(vals)))
    except Exception:
        return []
