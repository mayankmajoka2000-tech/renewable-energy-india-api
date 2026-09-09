"""
Extract grid-wide CO2 emission factors (Simple Operating Margin, Build
Margin, Combined Margin) from the 'Results' sheet of each CEA CO2 Baseline
Database version — the same files used in fetch_cea_co2_database.py.

For each version, we take its own latest reported financial year (the last
non-empty year column in the Results sheet), since that's the year the
version was actually published to represent.
"""
import io
import re
import zipfile

import openpyxl
import requests

from app.database import SessionLocal, init_db
from app.models import EmissionFactorYearly
from app.ingestion.fetch_cea_co2_database import SOURCES, HEADERS, _to_float

YEAR_RE = re.compile(r"(20\d{2}-\d{2})")


def _norm(v):
    return re.sub(r"\s+", " ", str(v or "")).strip().lower()


def _row_label(row):
    for cell in row:
        if isinstance(cell, str) and cell.strip():
            return _norm(cell)
    return ""


def parse_results_sheet(wb, version_label, url):
    names = [s for s in wb.sheetnames if s.strip().lower() == "results"]
    if not names:
        return None
    ws = wb[names[0]]

    year_cols = {}
    om = bm = cm = None

    for row in ws.iter_rows(min_row=1, max_row=60, values_only=True):
        label = _row_label(row)
        if not year_cols:
            candidate = {}
            for i, cell in enumerate(row):
                m = YEAR_RE.fullmatch(str(cell or "").strip())
                if m:
                    candidate[i] = m.group(1)
            if len(candidate) >= 3:  # real fiscal-year header row lists several consecutive years
                year_cols.update(candidate)
            continue
        if om is None and re.match(r"^(simple )?operating margin", label):
            om = row
        elif bm is None and label.startswith("build margin"):
            bm = row
        elif cm is None and label.startswith("combined margin"):
            cm = row

    if not year_cols:
        return None

    last_col = max(year_cols.keys())
    fy_label = year_cols[last_col]

    def val(row):
        return _to_float(row[last_col]) if row is not None else None

    return {
        "database_version": version_label,
        "financial_year": fy_label,
        "operating_margin_emission_factor": val(om),
        "build_margin_emission_factor": val(bm),
        "combined_margin_emission_factor": val(cm),
        "source_url": url,
    }


def run():
    init_db()
    db = SessionLocal()
    existing = {v for (v,) in db.query(EmissionFactorYearly.database_version)}
    count = 0

    for version_label, url, is_zip in SOURCES:
        if version_label in existing:
            continue
        try:
            resp = requests.get(url, headers=HEADERS, timeout=120)
            resp.raise_for_status()
            content = resp.content
            if is_zip:
                zf = zipfile.ZipFile(io.BytesIO(content))
                inner = [n for n in zf.namelist() if n.lower().endswith((".xls", ".xlsx", ".xlsm"))]
                if not inner:
                    continue
                content = zf.read(inner[0])
                if inner[0].lower().endswith(".xls"):
                    print(f"[skip] {version_label}: legacy .xls Results-sheet parsing not supported here")
                    continue
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            result = parse_results_sheet(wb, version_label, url)
            if result:
                db.add(EmissionFactorYearly(**result))
                db.commit()
                count += 1
                print(f"  -> {version_label}: FY {result['financial_year']} combined margin = {result['combined_margin_emission_factor']}")
            else:
                print(f"[skip] {version_label}: no Results sheet found")
        except Exception as e:
            print(f"[error] {version_label}: {e}")

    db.close()
    print(f"Emission factor ingestion complete: {count} rows")


if __name__ == "__main__":
    run()
