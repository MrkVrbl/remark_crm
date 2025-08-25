
# -*- coding: utf-8 -*-
import os
from datetime import date, datetime
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Text, or_
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.session import Session
import io

from utils import normalize_columns_generic, clean_dataframe_for_db, parse_date_safe

DB_PATH = os.environ.get("REMARK_CRM_DB", "remark_crm.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

Base = declarative_base()

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meno_zakaznika = Column(String)
    telefon = Column(String)
    email = Column(String)
    mesto = Column(String)
    typ_dopytu = Column(String)
    datum_povodneho_kontaktu = Column(Date)
    stav_projektu = Column(String)
    konkurencia = Column(String)
    cena_konkurencie = Column(Float)
    nasa_ponuka_orientacna = Column(Float)
    reakcia_zakaznika = Column(Text)
    dalsi_krok = Column(Text)
    datum_dalsieho_kroku = Column(Date)
    priorita = Column(String)  # Vysoká, Stredná, Nízka
    stav_leadu = Column(String)  # Open, Cold, Converted, Lost
    orientacna_cena = Column(Float)
    datum_realizacie = Column(Date)
    poznamky = Column(Text)


def is_duplicate_lead(session: Session, payload: Dict[str, Any]) -> bool:
    """Return True if a lead with at least two matching fields exists."""
    name = payload.get("meno_zakaznika")
    phone = payload.get("telefon")
    email = payload.get("email")
    dpc = parse_date_safe(payload.get("datum_povodneho_kontaktu"))

    filters = []
    if name:
        filters.append(Lead.meno_zakaznika == name)
    if phone:
        filters.append(Lead.telefon == phone)
    if email:
        filters.append(Lead.email == email)
    if dpc:
        filters.append(Lead.datum_povodneho_kontaktu == dpc)
    if not filters:
        return False

    candidates = session.query(Lead).filter(or_(*filters)).all()
    for c in candidates:
        matches = 0
        if name and c.meno_zakaznika == name:
            matches += 1
        if phone and c.telefon == phone:
            matches += 1
        if email and c.email == email:
            matches += 1
        if dpc and c.datum_povodneho_kontaktu == dpc:
            matches += 1
        if matches >= 2:
            return True
    return False


def remove_duplicate_leads(SessionLocal) -> int:
    """Delete duplicate leads based on matching at least two key fields."""
    session: Session = SessionLocal()
    removed = 0
    try:
        leads = session.query(Lead).all()
        to_delete = set()
        for i, a in enumerate(leads):
            if a.id in to_delete:
                continue
            for b in leads[i + 1 :]:
                if b.id in to_delete:
                    continue
                matches = 0
                if a.meno_zakaznika and b.meno_zakaznika and a.meno_zakaznika == b.meno_zakaznika:
                    matches += 1
                if a.telefon and b.telefon and a.telefon == b.telefon:
                    matches += 1
                if a.email and b.email and a.email == b.email:
                    matches += 1
                if (
                    a.datum_povodneho_kontaktu
                    and b.datum_povodneho_kontaktu
                    and a.datum_povodneho_kontaktu == b.datum_povodneho_kontaktu
                ):
                    matches += 1
                if matches >= 2:
                    to_delete.add(b.id)
        if to_delete:
            session.query(Lead).filter(Lead.id.in_(to_delete)).delete(synchronize_session=False)
            session.commit()
            removed = len(to_delete)
        return removed
    finally:
        session.close()

def get_engine_session():
    engine = create_engine(DATABASE_URL, echo=False, future=True)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal

def init_db(engine):
    Base.metadata.create_all(bind=engine)

def fetch_leads_df(SessionLocal) -> pd.DataFrame:
    session: Session = SessionLocal()
    try:
        rows = session.query(Lead).all()
        if not rows:
            return pd.DataFrame([
                # ensure columns visible even when empty
                {c.name: None for c in Lead.__table__.columns}
            ]).iloc[0:0]
        data = []
        for r in rows:
            d = {
                "id": r.id,
                "meno_zakaznika": r.meno_zakaznika,
                "telefon": r.telefon,
                "email": r.email,
                "mesto": r.mesto,
                "typ_dopytu": r.typ_dopytu,
                "datum_povodneho_kontaktu": r.datum_povodneho_kontaktu,
                "stav_projektu": r.stav_projektu,
                "konkurencia": r.konkurencia,
                "cena_konkurencie": r.cena_konkurencie,
                "nasa_ponuka_orientacna": r.nasa_ponuka_orientacna,
                "reakcia_zakaznika": r.reakcia_zakaznika,
                "dalsi_krok": r.dalsi_krok,
                "datum_dalsieho_kroku": r.datum_dalsieho_kroku,
                "priorita": r.priorita,
                "stav_leadu": r.stav_leadu,
                "orientacna_cena": r.orientacna_cena,
                "datum_realizacie": r.datum_realizacie,
                "poznamky": r.poznamky,
            }
            data.append(d)
        df = pd.DataFrame(data)
        return df
    finally:
        session.close()

def insert_lead(SessionLocal, payload: Dict[str, Any]) -> int:
    session: Session = SessionLocal()
    try:
        if is_duplicate_lead(session, payload):
            return 0
        obj = Lead(
            meno_zakaznika=payload.get("meno_zakaznika"),
            telefon=payload.get("telefon"),
            email=payload.get("email"),
            mesto=payload.get("mesto"),
            typ_dopytu=payload.get("typ_dopytu"),
            datum_povodneho_kontaktu=parse_date_safe(payload.get("datum_povodneho_kontaktu")),
            stav_projektu=payload.get("stav_projektu"),
            konkurencia=payload.get("konkurencia"),
            cena_konkurencie=payload.get("cena_konkurencie"),
            nasa_ponuka_orientacna=payload.get("nasa_ponuka_orientacna"),
            reakcia_zakaznika=payload.get("reakcia_zakaznika"),
            dalsi_krok=payload.get("dalsi_krok"),
            datum_dalsieho_kroku=parse_date_safe(payload.get("datum_dalsieho_kroku")),
            priorita=payload.get("priorita"),
            stav_leadu=payload.get("stav_leadu"),
            orientacna_cena=payload.get("orientacna_cena"),
            datum_realizacie=parse_date_safe(payload.get("datum_realizacie")),
            poznamky=payload.get("poznamky"),
        )
        session.add(obj)
        session.commit()
        return obj.id
    finally:
        session.close()

def update_single_lead(SessionLocal, payload: Dict[str, Any]) -> int:
    session: Session = SessionLocal()
    try:
        rid = payload.get("id")
        obj = session.query(Lead).filter(Lead.id == rid).first()
        if not obj:
            return 0
        for key, value in payload.items():
            if key == "id": 
                continue
            if key.startswith("datum") and value is not None:
                value = parse_date_safe(value)
            setattr(obj, key, value)
        session.commit()
        return 1
    finally:
        session.close()

def update_leads_bulk(SessionLocal, updates: List[Dict[str, Any]]) -> int:
    session: Session = SessionLocal()
    updated = 0
    try:
        for upd in updates:
            rid = upd.get("id")
            if not rid:
                continue
            obj = session.query(Lead).filter(Lead.id == rid).first()
            if not obj:
                continue
            for k, v in upd.items():
                if k == "id": 
                    continue
                if k.startswith("datum") and v is not None:
                    v = parse_date_safe(v)
                setattr(obj, k, v)
            updated += 1
        session.commit()
        return updated
    finally:
        session.close()

# --- Importers ---

EXCEL_SHEET = "Leads"

# Mapping helper for Excel/CSV differences
COLUMN_ALIASES = {
    "meno": "meno_zakaznika",
    "meno zákazníka": "meno_zakaznika",
    "meno_zákazníka": "meno_zakaznika",
    "telefon": "telefon",
    "telefón": "telefon",
    "email": "email",
    "mesto": "mesto",
    "typ dopytu": "typ_dopytu",
    "typ_dopytu": "typ_dopytu",
    "dátum pôvodného kontaktu": "datum_povodneho_kontaktu",
    "datum_povodneho_kontaktu": "datum_povodneho_kontaktu",
    "stav projektu": "stav_projektu",
    "stav_projektu": "stav_projektu",
    "konkurencia": "konkurencia",
    "kto je konkurencia": "konkurencia",
    "cena konkurencie": "cena_konkurencie",
    "cena_konkurencie": "cena_konkurencie",
    "naša ponuka orientačná": "nasa_ponuka_orientacna",
    "nasa ponuka (orientacna)": "nasa_ponuka_orientacna",
    "nasa_ponuka_orientacna": "nasa_ponuka_orientacna",
    "reakcia zákazníka": "reakcia_zakaznika",
    "reakcia_zakaznika": "reakcia_zakaznika",
    "ďalší krok": "dalsi_krok",
    "dohodnuty dalsi krok": "dalsi_krok",
    "dalsi_krok": "dalsi_krok",
    "dátum ďalšieho kroku": "datum_dalsieho_kroku",
    "datum_dalsieho_kroku": "datum_dalsieho_kroku",
    "priorita": "priorita",
    "stav leadu": "stav_leadu",
    "stav_leadu": "stav_leadu",
    "orientačná cena": "orientacna_cena",
    "orientacna cena (eur)": "orientacna_cena",
    "orientacna_cena": "orientacna_cena",
    "dátum realizácie": "datum_realizacie",
    "datum_realizacie": "datum_realizacie",
    "poznámky": "poznamky",
    "poznamky": "poznamky",
    # CSV specific
    "meno zákazníka*": "meno_zakaznika",
    "meno_zakaznika": "meno_zakaznika",
    "phone": "telefon",
    "telefón*": "telefon",
    "vytvorene": "datum_povodneho_kontaktu",
    "vytvorené": "datum_povodneho_kontaktu",
    "meno zákazníka (name)": "meno_zakaznika",
    "meno (name)": "meno_zakaznika",
    "meno zákazníka (meno)": "meno_zakaznika",
}

DB_COLUMNS = [
    "meno_zakaznika","telefon","email","mesto","typ_dopytu",
    "datum_povodneho_kontaktu","stav_projektu","konkurencia",
    "cena_konkurencie","nasa_ponuka_orientacna","reakcia_zakaznika",
    "dalsi_krok","datum_dalsieho_kroku","priorita","stav_leadu",
    "orientacna_cena","datum_realizacie","poznamky"
]

def import_initial_from_excel(SessionLocal, excel_path: str) -> Tuple[int,int]:
    """Import initial data from Excel sheet 'Leads' if DB is empty. Returns (imported, skipped)."""
    session: Session = SessionLocal()
    try:
        any_row = session.query(Lead).first()
        if any_row:
            return (0,0)  # already populated
    finally:
        session.close()

    if not excel_path or not os.path.exists(excel_path):
        return (0,0)

    try:
        import pandas as pd
        df = pd.read_excel(excel_path, sheet_name=EXCEL_SHEET, engine="openpyxl")
    except Exception as e:
        return (0,0)

    df = normalize_columns_generic(df, COLUMN_ALIASES)
    df = clean_dataframe_for_db(df, DB_COLUMNS)

    # Fill defaults for required categories if missing
    if "priorita" in df.columns:
        df["priorita"] = df["priorita"].fillna("Stredná")
    if "stav_leadu" in df.columns:
        df["stav_leadu"] = df["stav_leadu"].fillna("Open")

    imported = 0
    session = SessionLocal()
    try:
        for _, r in df.iterrows():
            payload = {col: r.get(col, None) for col in DB_COLUMNS}
            # Replace pandas NaN/NaT with Python ``None`` so SQLAlchemy doesn't
            # attempt to insert them directly.
            for k, v in payload.items():
                if pd.isna(v):
                    payload[k] = None
            # parse dates
            for dk in ["datum_povodneho_kontaktu","datum_dalsieho_kroku","datum_realizacie"]:
                payload[dk] = parse_date_safe(payload.get(dk))
            if is_duplicate_lead(session, payload):
                continue
            obj = Lead(**payload)
            session.add(obj)
            imported += 1
        session.commit()
    finally:
        session.close()
    return (imported, 0)

def import_from_excel_mapped(SessionLocal, file_or_buffer) -> Tuple[int,int]:
    """Import leads from an Excel file with columns like 'Meno zákazníka',
    'Telefón', etc. Returns (imported, skipped)."""
    import pandas as pd
    if isinstance(file_or_buffer, (str, bytes, os.PathLike)):
        df = pd.read_excel(file_or_buffer, engine="openpyxl")
    else:
        df = pd.read_excel(file_or_buffer, engine="openpyxl")

    df = normalize_columns_generic(df, COLUMN_ALIASES)
    df = clean_dataframe_for_db(df, DB_COLUMNS)

    if "priorita" in df.columns:
        df["priorita"] = df["priorita"].fillna("Stredná")
    if "stav_leadu" in df.columns:
        df["stav_leadu"] = df["stav_leadu"].fillna("Open")

    imported, skipped = 0, 0
    session = SessionLocal()
    try:
        for _, r in df.iterrows():
            if pd.isna(r.get("meno_zakaznika")):
                skipped += 1
                continue
            payload = {col: r.get(col, None) for col in DB_COLUMNS}
            for k, v in payload.items():
                if pd.isna(v):
                    payload[k] = None
            for dk in ["datum_povodneho_kontaktu","datum_dalsieho_kroku","datum_realizacie"]:
                payload[dk] = parse_date_safe(payload.get(dk))
            if is_duplicate_lead(session, payload):
                skipped += 1
                continue
            obj = Lead(**payload)
            session.add(obj)
            imported += 1
        session.commit()
    finally:
        session.close()
    return (imported, skipped)

def import_from_csv_mapped(SessionLocal, file_or_buffer) -> Tuple[int,int]:
    """Import from CSV with mapping:
        CSV: 'Meno' -> meno_zakaznika, 'Email' -> email, 'Phone' -> telefon, 'Vytovorene' -> datum_povodneho_kontaktu
    """
    import pandas as pd
    if isinstance(file_or_buffer, (str, bytes, os.PathLike)):
        df = pd.read_csv(file_or_buffer)
    else:
        # Uploaded file-like
        try:
            df = pd.read_csv(file_or_buffer)
        except Exception:
            # reset and try semicolon separator
            file_or_buffer.seek(0)
            df = pd.read_csv(file_or_buffer, sep=";")

    aliases = {
        "meno":"meno_zakaznika","Meno":"meno_zakaznika","Meno zákazníka":"meno_zakaznika",
        "Email":"email","email":"email",
        "Phone":"telefon","Telefón":"telefon","Telefon":"telefon","phone":"telefon",
        "Vytovorene":"datum_povodneho_kontaktu","Vytvorené":"datum_povodneho_kontaktu","Vytvorene":"datum_povodneho_kontaktu",
    }
    df = normalize_columns_generic(df, aliases)

    # Keep only mapped columns
    keep = ["meno_zakaznika","email","telefon","datum_povodneho_kontaktu"]
    df = df[[c for c in keep if c in df.columns]].copy()

    # Defaults
    df["priorita"] = "Stredná"
    df["stav_leadu"] = "Open"

    # Parse date
    if "datum_povodneho_kontaktu" in df.columns:
        df["datum_povodneho_kontaktu"] = pd.to_datetime(df["datum_povodneho_kontaktu"], errors="coerce").dt.date

    imported, skipped = 0, 0
    session: Session = SessionLocal()
    try:
        for _, r in df.iterrows():
            if pd.isna(r.get("meno_zakaznika")):
                skipped += 1
                continue
            meno = r.get("meno_zakaznika")
            email = r.get("email")
            telefon = r.get("telefon")
            dpc = r.get("datum_povodneho_kontaktu")
            payload = dict(
                meno_zakaznika=None if pd.isna(meno) else meno,
                email=None if pd.isna(email) else email,
                telefon=None if pd.isna(telefon) else telefon,
                datum_povodneho_kontaktu=None if pd.isna(dpc) else dpc,
                priorita="Stredná",
                stav_leadu="Open",
            )
            if is_duplicate_lead(session, payload):
                skipped += 1
                continue
            obj = Lead(**payload)
            session.add(obj)
            imported += 1
        session.commit()
    finally:
        session.close()

    return (imported, skipped)

def ensure_category_values(SessionLocal):
    """Optional: ensure there is at least one value for select boxes."""
    pass
