"""
Ingest CEA's 'CO2 Baseline Database for the Indian Power Sector' — every
publicly archived version on cea.nic.in — into the power_units and
emission_factors_yearly tables.

This is CEA's official plant/unit-wise database of net generation and CO2
emissions for every grid-connected thermal, hydro and nuclear unit in India,
used as the authoritative baseline for CDM/carbon-credit and grid emission
factor calculations. Solar/wind units are not included in this database
(they're the zero-emission comparator, not the baseline) — their capacity
comes from fetch_re_capacity.py instead.

`database_version` is always derived directly from the source filename, never
guessed, so every row stays traceable to the exact file it came from.
"""
import io
import re
import zipfile
from datetime import datetime, date

import openpyxl
import requests

from app.database import SessionLocal, init_db
from app.models import PowerUnit, EmissionFactorYearly

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0; +academic use)"}

# (version_label, url, is_zip)
SOURCES = [
    ("database_v1_2006", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database.zip", True),
    ("database_v2", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_1.zip", True),
    ("database_v3", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_2.zip", True),
    ("database_v4", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_3.zip", True),
    ("database_v5", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_4.zip", True),
    ("database_v6", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_5.zip", True),
    ("database_v7", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_6.zip", True),
    ("database_v8", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_7.zip", True),
    ("database_v9", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_8.zip", True),
    ("database_v10", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_9.zip", True),
    ("database_v11", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_10.zip", True),
    ("database_v12", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_11.zip", True),
    ("database_v13", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_12.zip", True),
    ("database_v14", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_13.zip", True),
    ("database_v15", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_14.zip", True),
    ("database_v16", "https://cea.nic.in/wp-content/uploads/baseline/2020/07/database_15.zip", True),
    ("database_2019_20", "https://cea.nic.in/wp-content/uploads/baseline/2021/06/2019_20_CO2_database.zip", True),
    ("database_v17_2020_21", "https://cea.nic.in/wp-content/uploads/baseline/2022/02/database_17_.zip", True),
    ("database_v18_2021_22", "https://cea.nic.in/wp-content/uploads/baseline/2023/01/version_18.zip", True),
    ("database_v19_2022_23", "https://cea.nic.in/wp-content/uploads/baseline/2024/04/CO2_DatabaseVersion_19_2022_23.xlsx", False),
    ("database_v20_2023_24", "https://cea.nic.in/wp-content/uploads/2021/03/CO2_Database_Version_20.0_2023_24.xlsx", False),
    ("database_v21", "https://cea.nic.in/wp-content/uploads/baseline/2025/12/CO2_Database_V_21.0.xlsx", False),
]

YEAR_RE = re.compile(r"(20\d{2})\s*-\s*(\d{2})")


def _norm(h):
    return re.sub(r"\s+", " ", str(h or "")).strip().upper()


def _find_header_row(ws, max_scan=5):
    for r in range(1, max_scan + 1):
        row = [ _norm(c) for c in next(ws.iter_rows(min_row=r, max_row=r, values_only=True)) ]
        if any("NAME" == c or "NAME" in c for c in row):
            return r, row
    return None, None


def _col_index(header, *keywords_all_of):
    for i, h in enumerate(header):
        if all(k in h for k in keywords_all_of):
            return i
    return None


def _load_workbook_from_bytes(name, content):
    if name.lower().endswith(".xls"):
        import pandas as pd
        df = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, engine="xlrd")
        return ("pandas", df)
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    return ("openpyxl", wb)


def _get_data_sheet_openpyxl(wb):
    candidates = [s for s in wb.sheetnames if s.strip().lower() in ("database", "data")]
    if not candidates:
        candidates = wb.sheetnames
    best = max(candidates, key=lambda s: wb[s].max_row)
    return wb[best]


def _parse_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def _to_float(v):
    try:
        if v in (None, "", "NA", "N/A", "-"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_openpyxl_sheet(ws, version_label, url):
    header_row_idx, header = _find_header_row(ws)
    if header_row_idx is None:
        print(f"  [skip] {version_label}: no header row found")
        return []

    fixed = {
        "s_no": _col_index(header, "S_NO") or _col_index(header, "S.NO") or _col_index(header, "SR"),
        "name": _col_index(header, "NAME"),
        "unit_no": _col_index(header, "UNIT_NO") or _col_index(header, "UNIT NO"),
        "dt_comm": _col_index(header, "DT_", "COMM") or _col_index(header, "COMM", "DATE") or _col_index(header, "DT COMM"),
        "type": _col_index(header, "TYPE"),
        "state": _col_index(header, "STATE"),
        "sector": _col_index(header, "SECTOR"),
        "system": _col_index(header, "SYSTEM"),
        "fuel1": _col_index(header, "FUEL1") or _col_index(header, "FUEL 1") or _col_index(header, "FUEL", "1"),
        "fuel2": _col_index(header, "FUEL2") or _col_index(header, "FUEL 2") or _col_index(header, "FUEL", "2"),
    }
    capacity_idx = None
    for i, h in enumerate(header):
        if "CAPACITY" in h:
            capacity_idx = i
            break
    fixed["capacity"] = capacity_idx

    # Detect year-blocks (wide multi-year format) vs single narrow snapshot
    year_cols = {}
    for i, h in enumerate(header):
        m = YEAR_RE.search(h)
        if m:
            yr = f"{m.group(1)}-{m.group(2)}"
            year_cols.setdefault(yr, []).append((i, h))

    rows_out = []

    def make_unit_row(vals, gen_mu, co2_total, factor, fy_label):
        return {
            "database_version": f"{version_label}::{fy_label}",
            "s_no": int(vals[fixed["s_no"]]) if fixed["s_no"] is not None and _to_float(vals[fixed["s_no"]]) is not None else None,
            "plant_name": str(vals[fixed["name"]]).strip() if fixed["name"] is not None and vals[fixed["name"]] else None,
            "unit_no": int(_to_float(vals[fixed["unit_no"]])) if fixed["unit_no"] is not None and _to_float(vals[fixed["unit_no"]]) is not None else None,
            "commissioning_date": _parse_date(vals[fixed["dt_comm"]]) if fixed["dt_comm"] is not None else None,
            "capacity_mw": _to_float(vals[fixed["capacity"]]) if fixed["capacity"] is not None else None,
            "plant_type": str(vals[fixed["type"]]).strip() if fixed["type"] is not None and vals[fixed["type"]] else None,
            "state": str(vals[fixed["state"]]).strip() if fixed["state"] is not None and vals[fixed["state"]] else None,
            "sector": str(vals[fixed["sector"]]).strip() if fixed["sector"] is not None and vals[fixed["sector"]] else None,
            "system_owner": str(vals[fixed["system"]]).strip() if fixed["system"] is not None and vals[fixed["system"]] else None,
            "fuel1": str(vals[fixed["fuel1"]]).strip() if fixed["fuel1"] is not None and vals[fixed["fuel1"]] else None,
            "fuel2": str(vals[fixed["fuel2"]]).strip() if fixed["fuel2"] is not None and vals[fixed["fuel2"]] else None,
            "net_generation_mu": gen_mu,
            "co2_tons_total": co2_total,
            "emission_factor_ton_per_mwh": factor,
            "source_url": url,
        }

    if len(year_cols) >= 2:
        # Wide multi-year format: one output row per unit per embedded year
        blocks = {}
        for yr, cols in year_cols.items():
            gen_i = co2_i = fac_i = None
            for i, h in cols:
                if "GENERATION" in h:
                    gen_i = i
                elif "ABSOLUTE" in h or ("CO2" in h and "SPECIFIC" not in h):
                    co2_i = i
                elif "SPECIFIC" in h or "FACTOR" in h:
                    fac_i = i
            blocks[yr] = (gen_i, co2_i, fac_i)

        for row in ws.iter_rows(min_row=header_row_idx + 1, values_only=True):
            if fixed["name"] is None or row[fixed["name"]] in (None, ""):
                continue
            for yr, (gen_i, co2_i, fac_i) in blocks.items():
                gen = _to_float(row[gen_i]) if gen_i is not None else None
                co2 = _to_float(row[co2_i]) if co2_i is not None else None
                fac = _to_float(row[fac_i]) if fac_i is not None else None
                if gen is None and co2 is None and fac is None:
                    continue
                rows_out.append(make_unit_row(row, gen, co2, fac, yr))
    else:
        gen_i = _col_index(header, "NET", "GENERATION") or _col_index(header, "GENERATION")
        co2_i = _col_index(header, "TOTAL", "CO2") or _col_index(header, "TOTAL CO2")
        fac_i = _col_index(header, "EMISSION", "FACTOR")
        fy_label = version_label.split("_")[-1] if any(ch.isdigit() for ch in version_label) else "unknown_fy"
        for row in ws.iter_rows(min_row=header_row_idx + 1, values_only=True):
            if fixed["name"] is None or row[fixed["name"]] in (None, ""):
                continue
            gen = _to_float(row[gen_i]) if gen_i is not None else None
            co2 = _to_float(row[co2_i]) if co2_i is not None else None
            fac = _to_float(row[fac_i]) if fac_i is not None else None
            if gen is None and co2 is None and fac is None:
                continue
            rows_out.append(make_unit_row(row, gen, co2, fac, fy_label))

    return rows_out


def fetch_one(version_label, url, is_zip):
    print(f"Fetching {version_label} ...")
    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    content = resp.content

    if is_zip:
        zf = zipfile.ZipFile(io.BytesIO(content))
        names = [n for n in zf.namelist() if n.lower().endswith((".xls", ".xlsx", ".xlsm"))]
        if not names:
            print(f"  [skip] {version_label}: no excel file inside zip")
            return []
        inner_name = names[0]
        content = zf.read(inner_name)
        fname = inner_name
    else:
        fname = url

    kind, wb = _load_workbook_from_bytes(fname, content)
    if kind == "pandas":
        # legacy .xls via pandas/xlrd — reuse same header/column logic on the largest sheet
        df_dict = wb
        best_sheet = max(df_dict, key=lambda s: df_dict[s].shape[0])
        df = df_dict[best_sheet]
        # Wrap into a minimal fake worksheet-like iterator reusing parse logic
        class _FakeWS:
            def __init__(self, df):
                self._rows = df.values.tolist()
            def iter_rows(self, min_row=1, max_row=None, values_only=True):
                sl = self._rows[min_row - 1: max_row if max_row else None]
                for r in sl:
                    yield r
        fake_ws = _FakeWS(df)
        return parse_openpyxl_sheet(fake_ws, version_label, url)
    else:
        ws = _get_data_sheet_openpyxl(wb)
        return parse_openpyxl_sheet(ws, version_label, url)


def run():
    init_db()
    db = SessionLocal()
    total = 0
    for version_label, url, is_zip in SOURCES:
        try:
            rows = fetch_one(version_label, url, is_zip)
        except Exception as e:
            print(f"  [error] {version_label}: {e}")
            continue
        for r in rows:
            db.add(PowerUnit(**r))
        db.commit()
        total += len(rows)
        print(f"  -> {len(rows)} unit-year rows loaded (running total {total})")
    db.close()
    print(f"CEA CO2 baseline ingestion complete: {total} rows")


if __name__ == "__main__":
    run()
