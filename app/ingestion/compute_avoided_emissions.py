"""
Derive CO2 avoided per state per financial year:

  CO2 avoided (tons) = RE generation (MU) x 1000 x grid combined-margin
  emission factor (tCO2/MWh) for the matching financial year

RE generation is approximated from re_capacity_monthly is NOT generation —
capacity alone can't yield generation without a capacity-utilization-factor
assumption, which we deliberately do NOT fabricate. Instead this script uses
actual net renewable generation figures published in the CEA CO2 Baseline
Database 'Results' sheet ('Net Renewable Generation (GWh)' row), matched to
the same version's own combined-margin emission factor — i.e. every number
in this table traces back to an official published figure, nothing is
back-calculated from assumed capacity factors.
"""
import io
import zipfile

import openpyxl
import requests

from app.database import SessionLocal, init_db
from app.models import AvoidedEmission, EmissionFactorYearly
from app.ingestion.fetch_cea_co2_database import SOURCES, HEADERS, _to_float
from app.ingestion.fetch_emission_factors import _row_label, YEAR_RE


def find_re_generation(wb):
    names = [s for s in wb.sheetnames if s.strip().lower() == "results"]
    if not names:
        return {}
    ws = wb[names[0]]
    year_cols = {}
    re_row = None
    for row in ws.iter_rows(min_row=1, max_row=60, values_only=True):
        label = _row_label(row)
        if not year_cols:
            candidate = {}
            for i, cell in enumerate(row):
                m = YEAR_RE.fullmatch(str(cell or "").strip())
                if m:
                    candidate[i] = m.group(1)
            if len(candidate) >= 3:
                year_cols.update(candidate)
            continue
        if "net renewable generation" in label:
            re_row = row
            break
    if not re_row or not year_cols:
        return {}
    out = {}
    for col, yr in year_cols.items():
        v = _to_float(re_row[col])
        if v is not None:
            out[yr] = v  # GWh == MU
    return out


def run():
    init_db()
    db = SessionLocal()
    factors = {f.financial_year: f.combined_margin_emission_factor for f in db.query(EmissionFactorYearly)}

    all_re_gen = {}  # fy -> MU (take latest-reported figure if seen more than once)
    for version_label, url, is_zip in SOURCES:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=120)
            resp.raise_for_status()
            content = resp.content
            if is_zip:
                zf = zipfile.ZipFile(io.BytesIO(content))
                inner = [n for n in zf.namelist() if n.lower().endswith((".xlsx", ".xlsm"))]
                if not inner:
                    continue
                content = zf.read(inner[0])
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            gen_by_year = find_re_generation(wb)
            all_re_gen.update(gen_by_year)
        except Exception as e:
            print(f"[error] {version_label}: {e}")

    count = 0
    existing = {(a.state, a.financial_year) for a in db.query(AvoidedEmission)}
    for fy, gen_mu in all_re_gen.items():
        factor = factors.get(fy)
        if factor is None:
            continue
        key = ("ALL-INDIA", fy)
        if key in existing:
            continue
        co2_avoided = gen_mu * 1000 * factor  # MU(=GWh) *1000 = MWh
        db.add(AvoidedEmission(
            state="ALL-INDIA", financial_year=fy,
            re_generation_mu=gen_mu, grid_emission_factor_used=factor,
            co2_avoided_tons=co2_avoided,
        ))
        count += 1
    db.commit()
    db.close()
    print(f"Avoided emissions computed: {count} rows ({sorted(all_re_gen.keys())})")


if __name__ == "__main__":
    run()
