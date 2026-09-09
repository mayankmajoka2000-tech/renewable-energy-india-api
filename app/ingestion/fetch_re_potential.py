"""
State-wise Renewable Energy Potential (MW), from MNRE's official
"Renewable Energy Statistics 2024-25" publication, Table 7.1 ("Estimated
potential in RE Sector"), page 36.

This replaces the originally planned data.gov.in route: that dataset
requires a personal API key and data.gov.in returns HTTP 403 to
unauthenticated/automated requests, so it can't be fetched without a human
in the loop. This MNRE statistical yearbook is a more authoritative primary
source for the same figure anyway (MNRE is literally where data.gov.in's
copy would have come from) and is publicly downloadable without any key:

  https://cdnbbsr.s3waas.gov.in/s3716e1b8c6cd17b771da77391355749f3/uploads/2025/11/202511061627678782.pdf

The table is transcribed here (not scraped at runtime) because it's a fixed
annual publication, extracted with pdfplumber word-position analysis
(bucketing each number by its x-coordinate under the correct column header)
and independently verified: every one of the 6 technology columns below
sums to the exact "Total" row the report itself publishes on the same page
(e.g. Wind sums to 1,163,856 MW against the report's stated 1163.86 GW).
Two very small (<0.01 MW) rounding remainders on the Biomass column are the
report's own rounding, not a transcription error.

Per the report's chapter 7.1 text, each technology's potential comes from
its own separate national assessment:
  - Wind: National Institute of Wind Energy (NIWE), 2023, at 150m AGL
  - Solar (ground-mounted): National Institute of Solar Energy (NISE), Sep 2025
  - Large Hydro: Central Electricity Authority (CEA), exploitable capacity
  - Small Hydro (up to 25 MW): IIT Roorkee, 2016
  - Biomass / Bagasse Cogeneration: Administrative Staff College of India, 2021
"""
from app.database import SessionLocal, init_db
from app.models import REPotential

SOURCE_URL = "https://cdnbbsr.s3waas.gov.in/s3716e1b8c6cd17b771da77391355749f3/uploads/2025/11/202511061627678782.pdf"
SOURCE_LABEL = "MNRE Renewable Energy Statistics 2024-25, Table 7.1 (p.36)"

# technology -> as_on (assessing body / year, per report text)
AS_ON = {
    "Wind": "NIWE, 2023 (at 150m AGL)",
    "Solar (Ground Mounted)": "NISE, Sep 2025",
    "Large Hydro": "CEA, exploitable capacity",
    "Small Hydro": "IIT Roorkee, 2016",
    "Biomass": "Administrative Staff College of India, 2021",
    "Bagasse Cogeneration": "Administrative Staff College of India, 2021",
}

# state -> {technology_key: potential_mw}, technology_key in
# {wind, small_hydro, biomass, bagasse, solar, large_hydro}
DATA = {
    "Andhra Pradesh": {"wind": 123336, "small_hydro": 409.32, "biomass": 1999.49, "bagasse": 279.6, "solar": 299312.12, "large_hydro": 2596},
    "Arunachal Pradesh": {"wind": 246, "small_hydro": 2064.92, "biomass": 18.46, "solar": 467.52, "large_hydro": 50394},
    "Assam": {"wind": 459, "small_hydro": 201.99, "biomass": 321.89, "solar": 19173.13, "large_hydro": 643},
    "Bihar": {"wind": 4023, "small_hydro": 526.98, "biomass": 964.37, "bagasse": 346.6, "solar": 32991.49, "large_hydro": 130.1},
    "Chhattisgarh": {"wind": 2749, "small_hydro": 1098.2, "biomass": 353.68, "solar": 126484.29, "large_hydro": 1311},
    "Goa": {"wind": 14, "small_hydro": 4.7, "biomass": 32.97, "solar": 6752.35},
    "Gujarat": {"wind": 180790, "small_hydro": 201.97, "biomass": 2637.84, "bagasse": 554.7, "solar": 243219.9, "large_hydro": 550},
    "Haryana": {"wind": 593, "small_hydro": 107.4, "biomass": 1353.35, "bagasse": 362.1, "solar": 6468.1},
    "Himachal Pradesh": {"wind": 239, "small_hydro": 3460.34, "biomass": 69.71, "solar": 21501.61, "large_hydro": 18305},
    "Jammu and Kashmir": {"small_hydro": 1707.45, "biomass": 82.82, "solar": 8588.94, "large_hydro": 12971.5},
    "Ladakh": {"wind": 1, "solar": 8556.64},
    "Jharkhand": {"wind": 16, "small_hydro": 227.96, "biomass": 146.31, "solar": 51831.29, "large_hydro": 300},
    "Karnataka": {"wind": 169251, "small_hydro": 3726.49, "biomass": 1793.88, "bagasse": 1762.1, "solar": 223278.99, "large_hydro": 4414.4},
    "Kerala": {"wind": 2621, "small_hydro": 647.15, "biomass": 778.41, "solar": 12404.71, "large_hydro": 2472.75},
    "Madhya Pradesh": {"wind": 55423, "small_hydro": 820.44, "biomass": 2516.42, "solar": 318972.16, "large_hydro": 2819},
    "Maharashtra": {"wind": 173868, "small_hydro": 786.46, "biomass": 2629.55, "bagasse": 3917, "solar": 486678.68, "large_hydro": 3144},
    "Manipur": {"small_hydro": 99.95, "biomass": 62.31, "solar": 2293.92, "large_hydro": 615},
    "Meghalaya": {"wind": 55, "small_hydro": 230.05, "biomass": 68.54, "solar": 14674.1, "large_hydro": 2026},
    "Mizoram": {"small_hydro": 168.9, "biomass": 2.90, "solar": 612.21, "large_hydro": 1926.7},
    "Nagaland": {"small_hydro": 182.18, "biomass": 53.90, "solar": 190.96, "large_hydro": 325},
    "Odisha": {"wind": 12129, "small_hydro": 286.22, "biomass": 298.72, "solar": 139474.33, "large_hydro": 2824.5},
    "Punjab": {"wind": 428, "small_hydro": 578.28, "biomass": 3022.11, "bagasse": 414.4, "solar": 9210.19, "large_hydro": 1300.73},
    "Rajasthan": {"wind": 284250, "small_hydro": 51.67, "biomass": 1299.55, "solar": 828781.44, "large_hydro": 411},
    "Sikkim": {"small_hydro": 266.64, "biomass": 4.73, "solar": 254.46, "large_hydro": 6051},
    "Tamil Nadu": {"wind": 95107, "small_hydro": 604.46, "biomass": 1560.08, "bagasse": 639.3, "solar": 204765.06, "large_hydro": 1785.2},
    "Telangana": {"wind": 54717, "small_hydro": 102.25, "biomass": 1678.36, "bagasse": 117.4, "solar": 140451.26, "large_hydro": 1302},
    "Tripura": {"small_hydro": 46.86, "biomass": 34.35, "solar": 9105.85},
    "Uttar Pradesh": {"wind": 510, "small_hydro": 460.75, "biomass": 2800.31, "bagasse": 4925.7, "solar": 97842.99, "large_hydro": 501.6},
    "Uttarakhand": {"wind": 49, "small_hydro": 1664.31, "biomass": 93.34, "bagasse": 215.1, "solar": 4436.24, "large_hydro": 13481.35},
    "West Bengal": {"wind": 1281, "small_hydro": 392.06, "biomass": 1741.74, "solar": 22742.39, "large_hydro": 809.2},
    "Andaman and Nicobar Islands": {"wind": 1245, "small_hydro": 7.27, "biomass": 18.13, "solar": 594.22},
    "Chandigarh": {"biomass": 0.15, "solar": 22.42},
    "Dadra and Nagar Haveli and Daman and Diu": {"wind": 17, "biomass": 2.16, "solar": 498.31},
    "Delhi": {"solar": 550.22},
    "Lakshadweep": {"wind": 31, "biomass": 1.39},
    "Puducherry": {"wind": 408, "biomass": 5.00, "solar": 195.9},
    "Others (unspecified)": {"bagasse": 284.4},
}

TECH_LABELS = {
    "wind": "Wind",
    "small_hydro": "Small Hydro",
    "biomass": "Biomass",
    "bagasse": "Bagasse Cogeneration",
    "solar": "Solar (Ground Mounted)",
    "large_hydro": "Large Hydro",
}

# Checksum against the report's own published "Total" row (Table 7.1) —
# run() re-verifies this at insert time so a future transcription edit
# can't silently drift from the source.
EXPECTED_TOTALS = {
    "wind": 1163856, "small_hydro": 21133.62, "biomass": 28446.91,
    "bagasse": 13818.4, "solar": 3343378.39, "large_hydro": 133410.03,
}


def run():
    sums = {k: 0.0 for k in EXPECTED_TOTALS}
    for state_values in DATA.values():
        for k, v in state_values.items():
            sums[k] += v
    for k, expected in EXPECTED_TOTALS.items():
        if abs(sums[k] - expected) > 0.5:
            raise ValueError(
                f"Checksum failed for {k}: computed {sums[k]}, "
                f"report total {expected}. Refusing to seed unverified data."
            )

    init_db()
    db = SessionLocal()
    existing = {(r.state, r.technology) for r in db.query(REPotential)}
    count = 0

    for state, values in DATA.items():
        for tech_key, potential_mw in values.items():
            technology = TECH_LABELS[tech_key]
            key = (state, technology)
            if key in existing:
                continue
            db.add(REPotential(
                state=state,
                technology=technology,
                potential_mw=potential_mw,
                as_on=AS_ON[technology],
                source=SOURCE_LABEL,
                source_url=SOURCE_URL,
            ))
            count += 1

    db.commit()
    db.close()
    print(f"RE potential ingestion complete: {count} rows (checksum verified against report totals)")


if __name__ == "__main__":
    run()
