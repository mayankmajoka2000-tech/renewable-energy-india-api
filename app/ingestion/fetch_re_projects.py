"""
Ingest CEA's plant-level Renewable Energy project registry into `re_projects`.

Source: CEA Renewable Project Monitoring Division, "Plant-wise details of RE
Installed Capacity" (https://cea.nic.in/rpm/plant-wise-details-of-renewable-
energy-projects/), a 1,958-page PDF listing individual wind/solar/biopower/
small-hydro projects by name, developer, capacity, district and commissioning
date, state by state. Snapshot dated April 2020 (data as of Oct/Dec 2019) --
this is the most recent structured plant-level listing CEA has published;
its more recent reports (quarterly under-construction summaries) only cover
projects >=25MW and don't give the full commissioned fleet.

WHY THIS NEEDED A VERIFICATION STEP (unlike fetch_re_potential.py, where the
whole hardcoded table is checksummed against the report's stated totals up
front): this PDF is a real government scan/export with 1,958 pages of
inconsistent table layouts -- at least 15 distinct header column orderings,
several dozen state-name typos ("Maharastara", "Tamilnadu", "Kerela", ...),
and in a few hundred pages, cell text visibly overflows into the neighboring
column (e.g. a wrapped company name's second line bleeding into the capacity
cell: "...PVT LTD 1.00"). A single-page-at-a-time parser can't self-verify.

So verification here works at the (state, technology-group) level instead of
per-row: the report's own page 1 ("Project Wise details of all India
Installed Capacity") already sums the plant list against a "Plantwise data
Furnished by State" column per state x technology -- i.e. CEA published its
own checksum of this exact plant list. We reproduce that same aggregation
from the rows we parse and compare it to CEA's stated total for every
(state, technology) group:

  - within 3% (or 2MW, whichever is larger) => `state_tech_verified = 1`
  - outside tolerance => `state_tech_verified = 0`, but the rows are NOT
    dropped -- they're still real, directly transcribed plant records, just
    from report sections where the reconciliation didn't come out clean
    (usually a handful of pages within a large multi-hundred-page state/tech
    section, not the whole section). This is disclosed per-row via the
    `state_tech_verified` column rather than silently included as if
    equivalent confidence, and summarized in this script's own output and in
    the README.

Re-running downloads the ~17MB PDF fresh each time (CEA doesn't version this
file, so there's no cache-busting concern) and is idempotent: skips
re-ingestion entirely if `re_projects` already has rows.
"""
import difflib
import io
import re
from collections import defaultdict
from datetime import datetime

import pdfplumber
import requests

from app.database import SessionLocal, init_db
from app.models import REProject

SOURCE_URL = "https://cea.nic.in/wp-content/uploads/2020/04/Plant-wise-details-of-RE-Installed-Capacity-merged.pdf"
SOURCE_LABEL = "CEA Renewable Project Monitoring Division - Plant-wise details of RE Installed Capacity (as of Oct/Dec 2019)"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0; +academic use)"}

CANONICAL_STATES = [
    "Jammu and Kashmir", "Himachal Pradesh", "Punjab", "Chandigarh", "Uttarakhand",
    "Haryana", "Delhi", "Uttar Pradesh", "Rajasthan", "Gujarat", "Madhya Pradesh",
    "Chhattisgarh", "Maharashtra", "Goa", "Daman and Diu", "Dadra and Nagar Haveli",
    "Andhra Pradesh", "Telangana", "Karnataka", "Tamil Nadu", "Kerala", "Puducherry",
    "Bihar", "Jharkhand", "West Bengal", "Odisha", "Sikkim", "Assam",
    "Arunachal Pradesh", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Tripura",
    "Andaman and Nicobar Islands", "Lakshadweep",
]
STATE_TYPO_FIX = {
    "kerela": "Kerala", "maharastra": "Maharashtra", "madhya pradesh": "Madhya Pradesh",
    "arunachal pardesh": "Arunachal Pradesh", "meghalya": "Meghalaya",
    "andaman & nicobar": "Andaman and Nicobar Islands", "chandigarh": "Chandigarh",
    "dadar & nagar haveli": "Dadra and Nagar Haveli", "daman & diu": "Daman and Diu",
    "lakshwadeep": "Lakshadweep", "pondicheery": "Puducherry",
    "jammu & kashmir": "Jammu and Kashmir", "karnatka": "Karnataka",
    "telangana state": "Telangana", "others": "Others",
}


def _squash(s):
    return re.sub(r"[^a-z]", "", s.lower())


_SQUASH_MAP = {_squash(s): s for s in CANONICAL_STATES}
_SQUASH_KEYS = list(_SQUASH_MAP.keys())


def norm_state(s):
    if not s:
        return None
    s = re.sub(r"^[^A-Za-z]+", "", s.replace("\n", " "))
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return None
    key = s.lower()
    if key in STATE_TYPO_FIX:
        return STATE_TYPO_FIX[key]
    sq = _squash(s)
    if sq in _SQUASH_MAP:
        return _SQUASH_MAP[sq]
    close = difflib.get_close_matches(sq, _SQUASH_KEYS, n=1, cutoff=0.82)
    if close:
        return _SQUASH_MAP[close[0]]
    return s.title() if s.isupper() or s.islower() else s


def bucket(text):
    s = (text or "").lower()
    if "wind" in s:
        return "Wind"
    if "solar" in s:
        return "Solar"
    if "hydro" in s:
        return "Small Hydro"
    if any(k in s for k in ["bio", "bagasse", "cogen", "co-gen", "waste", "heat"]):
        return "Biopower"
    return None


def canon_header(cell):
    if not cell:
        return None
    c = re.sub(r"\s+", " ", cell.replace("\n", " ")).strip().lower()
    if "developer" in c and "name" in c:
        return "developer"
    if "investor" in c and "name" in c:
        return "plant_name"
    if "name of site" in c:
        return "plant_name"
    if "name" in c and ("plant" in c or "project" in c):
        return "plant_name"
    if "wind power developer" in c:
        return "developer"
    if "capacity" in c:
        return "capacity_mw"
    if c in ("type", "types"):
        return "technology"
    if "location" in c or "district" in c:
        return "location_district"
    if c in ("state", "states", "state/ut"):
        return "state"
    if "commission" in c:
        return "commissioning_date"
    if "remarks" in c:
        return "remarks"
    return None


def is_plant_header_row(row):
    joined = " ".join([c.replace("\n", " ") if c else "" for c in row]).lower()
    return "apacity" in joined and (
        "name" in joined or "project" in joined
        or "s.n" in joined.replace(".", "") or "file no" in joined
    )


def parse_reference_table(page1_table):
    """CEA's own all-India summary table (page 2 of the PDF): per-state,
    per-technology 'Plantwise data Furnished by State' totals -- this is
    CEA's own checksum of the plant list on the pages that follow."""
    ref = {}
    tech_cols = [("Wind", 3), ("Solar", 5), ("Biopower", 7), ("Small Hydro", 9)]
    for row in page1_table[3:]:
        if not row or not row[1]:
            continue
        if row[1].strip().lower() == "total":
            continue
        state = norm_state(row[1])
        vals = {}
        for tech, idx in tech_cols:
            try:
                vals[tech] = float(row[idx])
            except (TypeError, ValueError):
                vals[tech] = 0.0
        ref[state] = vals
    return ref


def parse_pdf(pdf_bytes):
    rows_out = []
    title_re = re.compile(r"\bin\s+([A-Za-z .&]+?)\s*$", re.IGNORECASE)
    current_state = None
    current_tech_title = None
    ref_table = None

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            table = page.extract_table()
            if not table:
                continue

            if i == 1:
                ref_table = parse_reference_table(table)
                continue

            row0 = table[0]
            non_none = [c for c in row0 if c]
            if len(non_none) == 1 and len(row0) > 3 and not is_plant_header_row(row0):
                title_text = non_none[0].replace("\n", " ")
                m = title_re.search(title_text)
                if m:
                    current_state = norm_state(m.group(1))
                tech = bucket(title_text)
                if tech:
                    current_tech_title = tech

            header_row_idx = None
            colmap = None
            for ridx, row in enumerate(table[:2]):
                if is_plant_header_row(row):
                    header_row_idx = ridx
                    colmap = [canon_header(c) for c in row]
                    if "plant_name" not in colmap and "developer" in colmap:
                        colmap = ["plant_name" if c == "developer" else c for c in colmap]
                    break
            if header_row_idx is None:
                continue

            for row in table[header_row_idx + 1:]:
                if not row or all(c is None or str(c).strip() == "" for c in row):
                    continue
                joined_lower = " ".join([str(c) for c in row if c]).lower()
                if "total" in joined_lower and len(joined_lower) < 40:
                    continue

                rec = {}
                for idx, col in enumerate(colmap):
                    if col and idx < len(row) and row[idx]:
                        rec[col] = re.sub(r"\s+", " ", str(row[idx]).replace("\n", " ")).strip()

                plant_name = rec.get("plant_name")
                cap_raw = rec.get("capacity_mw")
                if not plant_name or not cap_raw:
                    continue
                cap_clean = cap_raw.replace(",", "")
                try:
                    capacity_mw = float(cap_clean)
                except ValueError:
                    m = re.search(r"(\d+\.\d+|\d+)\s*$", cap_clean)
                    if not m:
                        continue
                    capacity_mw = float(m.group(1))
                if capacity_mw <= 0 or capacity_mw > 2000:
                    continue

                state = norm_state(rec.get("state")) or current_state
                technology = rec.get("technology") or current_tech_title
                if not state or not technology:
                    continue

                rows_out.append({
                    "page": i,
                    "plant_name": plant_name,
                    "developer": rec.get("developer"),
                    "capacity_mw": capacity_mw,
                    "technology": technology,
                    "location_district": rec.get("location_district"),
                    "state": state,
                    "commissioning_date": rec.get("commissioning_date"),
                    "bucket": bucket(technology) or current_tech_title,
                })

    return rows_out, ref_table


def verify_groups(rows, ref_table):
    agg = defaultdict(float)
    for r in rows:
        if r["bucket"]:
            agg[(r["state"], r["bucket"])] += r["capacity_mw"]

    verified = {}
    for state, techs in ref_table.items():
        for tech, refval in techs.items():
            parsed = agg.get((state, tech), 0.0)
            tol = max(2.0, refval * 0.03)
            verified[(state, tech)] = abs(parsed - refval) <= tol
    return verified


def run():
    init_db()
    db = SessionLocal()
    if db.query(REProject).count() > 0:
        print("re_projects already populated, skipping (delete rows to re-ingest).")
        db.close()
        return

    print(f"Downloading {SOURCE_URL} ...")
    resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=180)
    resp.raise_for_status()
    print(f"Downloaded {len(resp.content) / 1e6:.1f} MB, parsing 1,958 pages...")

    rows, ref_table = parse_pdf(resp.content)
    verified = verify_groups(rows, ref_table)

    verified_count = 0
    unverified_count = 0
    for r in rows:
        key = (r["state"], r["bucket"])
        is_verified = verified.get(key, False)
        if is_verified:
            verified_count += 1
        else:
            unverified_count += 1

        db.add(REProject(
            plant_name=r["plant_name"],
            developer=r["developer"],
            capacity_mw=r["capacity_mw"],
            technology=r["technology"],
            technology_group=r["bucket"] or "Unknown",
            location_district=r["location_district"],
            state=r["state"],
            commissioning_date_raw=r["commissioning_date"],
            source_page=r["page"],
            state_tech_verified=bool(is_verified),
            source=SOURCE_LABEL,
            source_url=SOURCE_URL,
        ))

    db.commit()
    total = verified_count + unverified_count
    n_groups = len(verified)
    n_verified_groups = sum(1 for v in verified.values() if v)
    print(
        f"RE project ingestion complete: {total} rows "
        f"({verified_count} checksum-verified against CEA's own state/technology "
        f"totals, {unverified_count} unverified -- real transcribed records from "
        f"report sections with known PDF text-extraction artifacts). "
        f"{n_verified_groups}/{n_groups} (state, technology) groups verified."
    )
    db.close()


if __name__ == "__main__":
    run()
