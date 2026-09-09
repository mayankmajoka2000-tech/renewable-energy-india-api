"""
Ingest CEA's RE-India state-wise renewable capacity time series (REIndia.csv)
into re_capacity_monthly. This is a real CEA-published dataset covering
state x renewable-source x month installed capacity (MW), Apr-2018 to Jan-2020.

It is intentionally NOT synthetically extended past its real coverage window —
this table's date range is a genuine historical snapshot, not a live feed.
"""
import csv
import io
from datetime import date

import requests

from app.database import SessionLocal, init_db
from app.models import RECapacityMonthly

URL = "https://cea.nic.in/wp-content/uploads/2020/04/REIndia.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0; +academic use)"}

SOURCE_COLUMNS = {
    "Wind ": "WIND",
    "Solar": "SOLAR",
    "Biomass": "BIOMASS",
    "Bagasse": "BAGASSE",
    "Small Hydel": "SMALL_HYDEL",
    "Others": "OTHERS",
}

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _parse_month(label):
    label = label.strip()
    mon, yy = label.split("-")
    year = 2000 + int(yy)
    return date(year, MONTH_MAP[mon], 1)


def run():
    init_db()
    resp = requests.get(URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig")))

    db = SessionLocal()
    existing = {
        (r.state, r.month, r.source_type)
        for r in db.query(RECapacityMonthly.state, RECapacityMonthly.month, RECapacityMonthly.source_type)
    }
    count = 0
    for row in reader:
        state = row["State"].strip()
        region = row["Region"].strip()
        month = _parse_month(row["Month "])
        for col, source_type in SOURCE_COLUMNS.items():
            raw = row.get(col)
            if raw is None or raw.strip() == "":
                continue
            try:
                mw = float(raw)
            except ValueError:
                continue
            key = (state, month, source_type)
            if key in existing:
                continue
            db.add(RECapacityMonthly(
                state=state, region=region, month=month,
                source_type=source_type, capacity_mw=mw,
                source_url=URL,
            ))
            existing.add(key)
            count += 1
    db.commit()
    db.close()
    print(f"RE capacity ingestion complete: {count} rows")


if __name__ == "__main__":
    run()
