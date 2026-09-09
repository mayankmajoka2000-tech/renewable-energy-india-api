"""
Ingest daily solar irradiance / wind speed / temperature for 33 Indian
state & UT capitals, plus named major solar/wind installations, from NASA
POWER (power.larc.nasa.gov) — the free, no-API-key satellite reanalysis
(MERRA-2 / SYN1DEG) dataset used as the underlying resource layer in global
solar/wind bankability studies (World Bank ESMAP Global Solar Atlas, IRENA,
NREL).

This is the primary volume table: one API call per location returns its
full multi-year daily series in a single request (NASA POWER supports
arbitrary date ranges per call). State capitals give broad regional
coverage; the named RE_PARKS locations give site-specific resource data at
actual installations (a state capital can be hundreds of km from its RE
parks, which matters for project-level bankability screening).

NASA POWER uses -999 as a fill value for not-yet-processed/missing days
(there's a several-day satellite processing lag) — those are stored as
NULL, never as -999, to avoid polluting the dataset with a sentinel value.
"""
import time
from datetime import date, datetime

import requests

from app.database import SessionLocal, init_db
from app.models import SolarWindResourceDaily
from app.seed_states import STATES, RE_PARKS

API_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = "ALLSKY_SFC_SW_DWN,WS10M,T2M"
START = "20100101"
END = datetime.utcnow().strftime("%Y%m%d")
FILL_VALUE = -999.0


def _clean(v):
    if v is None or float(v) <= FILL_VALUE + 1:
        return None
    return float(v)


def fetch_location(name, lat, lon):
    resp = requests.get(API_URL, params={
        "parameters": PARAMS,
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": START,
        "end": END,
        "format": "JSON",
    }, timeout=120)
    resp.raise_for_status()
    data = resp.json()["properties"]["parameter"]
    ghi = data.get("ALLSKY_SFC_SW_DWN", {})
    wind = data.get("WS10M", {})
    temp = data.get("T2M", {})
    return ghi, wind, temp


def run():
    init_db()
    db = SessionLocal()

    existing_locations = {
        r[0] for r in db.query(SolarWindResourceDaily.location_name).distinct()
    }

    locations = [(name, name, lat, lon) for name, region, lat, lon in STATES]
    locations += [(name, state, lat, lon) for name, state, lat, lon, _type in RE_PARKS]

    total = 0
    for name, state, lat, lon in locations:
        if name in existing_locations:
            print(f"[skip] {name} already loaded")
            continue
        print(f"Fetching NASA POWER data for {name} ({lat}, {lon}) ...")
        try:
            ghi, wind, temp = fetch_location(name, lat, lon)
        except Exception as e:
            print(f"  [error] {name}: {e}")
            continue

        rows = []
        for day_str in ghi.keys():
            d = date(int(day_str[:4]), int(day_str[4:6]), int(day_str[6:8]))
            rows.append(SolarWindResourceDaily(
                location_name=name,
                state=state,
                latitude=lat,
                longitude=lon,
                date=d,
                ghi_kwh_m2_day=_clean(ghi.get(day_str)),
                wind_speed_10m_ms=_clean(wind.get(day_str)),
                temperature_2m_c=_clean(temp.get(day_str)),
            ))
        db.bulk_save_objects(rows)
        db.commit()
        total += len(rows)
        print(f"  -> {len(rows)} daily rows (running total {total})")
        time.sleep(1)  # be polite to the free public API

    db.close()
    print(f"NASA POWER ingestion complete: {total} rows")


if __name__ == "__main__":
    run()
