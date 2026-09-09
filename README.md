# India Renewable Energy & Sustainable Finance API

[![CI](https://github.com/mayankmajoka2000-tech/renewable-energy-india-api/actions/workflows/ci.yml/badge.svg)](https://github.com/mayankmajoka2000-tech/renewable-energy-india-api/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Live API:** https://renewable-energy-india-api.onrender.com/docs
(free tier — spins down after 15 min idle, first request after that takes
~30-60s to wake up)

A FastAPI service over **426,718 real, sourced records** covering India's renewable
energy sector: plant/unit-wise generation and CO2 emissions, individual named RE
projects, state-wise renewable capacity, and daily satellite-measured solar/wind
resource data. Built for use in sustainable finance research (project bankability
screening, avoided-emissions / carbon-credit estimation, grid decarbonization
tracking).

**Every row carries `source`, `source_url`, and `retrieved_at` fields.** Nothing
in this database is synthetic, interpolated, or estimated unless explicitly
labeled as `AvoidedEmission` (a documented derived calculation).

## Current data inventory

| Table | Rows | Source | Coverage |
|---|---:|---|---|
| `power_units` | 128,815 | CEA CO2 Baseline Database for the Indian Power Sector (all 21 archived versions, 2000–2024) | Every grid-connected thermal/hydro/nuclear generating unit in India, unit-wise net generation (MU) and CO2 emissions, multi-year |
| `solar_wind_resource_daily` | 274,320 | NASA POWER (MERRA-2/SYN1DEG satellite reanalysis) | Daily GHI, 10m wind speed, 2m temperature at 33 state/UT capitals + 11 named major solar/wind installations (Bhadla, Pavagada, Kurnool, Rewa, Charanka, Jaisalmer, Muppandal, Kamuthi, NP Kunta, Dhule, Bhuj), 2010-01-01 to present |
| `re_capacity_monthly` | 4,781 | CEA RE-India state-wise capacity series | State x source (wind/solar/biomass/bagasse/small-hydel/others) x month, Apr 2018 – Jan 2020 |
| `emission_factors_yearly` | 14 | CEA CO2 Baseline Database, Results sheet | Grid-wide combined/operating/build margin emission factors, FY2011-12 to FY2024-25 (3 years incomplete due to legacy file format) |
| `avoided_emissions` | 7 | **Derived**: officially published net RE generation x matching year's grid emission factor | All-India, FY2018-19 to FY2024-25 |
| `re_potential` | 165 | MNRE Renewable Energy Statistics 2024-25, Table 7.1 (official yearbook, not data.gov.in) | State/UT x technology (Wind, Solar, Large Hydro, Small Hydro, Biomass, Bagasse Cogeneration) estimated potential in MW |
| `re_projects` | 18,582 | CEA Renewable Project Monitoring Division - Plant-wise details of RE Installed Capacity (as of Oct/Dec 2019) | Individual named wind/solar/biopower/small-hydro plants: name, developer, capacity, district, commissioning date. 4,354 rows are checksum-verified against CEA's own published state x technology totals; see caveat below |
| `states` | 34 | Curated reference (28 states + 6 UTs, region classification, capital coordinates) | Master/lookup table |
| **Total** | **426,718** | | |

The 11 named installations give site-specific resource data (a state capital
can be hundreds of km from its actual RE parks, which matters for
project-level bankability screening) — their coordinates are individually
verified against Wikipedia/Global Energy Monitor entries, not estimated from
the state centroid.

Numbers hold up against public benchmarks: computed avoided emissions run
150–190 million tCO2/year for FY2019–FY2025, consistent with independent estimates
in Indian energy-transition literature.

## Why these sources, and what's *not* here

I prioritized real, citable, government/scientific sources over hitting a row
count artificially.

- **`re_potential` was originally planned to come from data.gov.in**, which
  requires a free personal API key and blocks unauthenticated automated
  requests (HTTP 403) — not something obtainable without a human in the
  loop. Instead it's sourced from MNRE's own **"Renewable Energy Statistics
  2024-25"** official yearbook (Table 7.1, page 36) — a more authoritative
  primary source anyway, since MNRE is where data.gov.in's copy would have
  come from. The 6-technology-column table (Wind, Solar, Large Hydro, Small
  Hydro, Biomass, Bagasse Cogeneration x 37 states/UTs) was extracted with
  `pdfplumber` word-position analysis and is checksum-verified against the
  report's own published totals at ingestion time
  (`app/ingestion/fetch_re_potential.py` re-verifies and refuses to seed if
  a column sum doesn't match the source's stated total) — see the module
  docstring for the full sourcing/verification chain.
- **`re_projects` (plant-level project database) — how it's verified, and its
  real limitation.** CEA's Renewable Project Monitoring Division publishes a
  1,958-page PDF ("Plant-wise details of RE Installed Capacity", snapshot
  dated April 2020 / data as of Oct-Dec 2019 — the most recent structured
  plant-level listing CEA has published) listing every individual wind,
  solar, biopower and small-hydro project by name, developer, capacity,
  district and commissioning date, state by state. It has at least 15
  different table layouts across those pages and dozens of state-name typos,
  so instead of trusting a single parse, `app/ingestion/fetch_re_projects.py`
  reuses the same trick as `fetch_re_potential.py`: the report's own page 1
  already sums the plant list into a "Plantwise data furnished by State"
  total per state x technology — i.e. CEA published its own checksum of this
  exact plant list. The ingestion script reproduces that same aggregation
  from the rows it parses and compares it against CEA's stated total for
  every (state, technology) group. **4,354 of 18,582 rows (130 of 148
  groups) reconcile within 3%** and are flagged `state_tech_verified: true`;
  the remaining rows are still real, directly transcribed plant records —
  just from report sections (mostly a few very large investor-model wind
  listings in Tamil Nadu and Gujarat) where a handful of pages have PDF text
  overflowing between columns, which prevented a clean reconciliation for
  that group. Rather than silently drop 77% of genuinely real records or
  claim false precision, both are included with the flag disclosed — filter
  with `?verified_only=true` on `/projects` if you need only the
  reconciled subset.
- **`net_generation_mu` is null for ~55,700 of the 128,815 power_unit rows** —
  these are units where a database version's Results sheet reported CO2/emission-factor
  data without a matching generation figure in the same row (typically very old,
  since-decommissioned or specialty units in the 2006–2010 archives). Left as
  NULL rather than backfilled.

## Architecture

```
app/
  main.py           FastAPI app + router registration
  models.py         SQLAlchemy schema (8 tables, full provenance columns)
  database.py       DB engine/session — SQLite by default, reads DATABASE_URL for Postgres
  rate_limit.py     Per-IP fixed-window rate limiting middleware
  schemas.py        Pydantic response models
  seed_states.py    33-state/UT reference list + named RE park coordinates
  routers/          states, emissions, capacity, resource, stats, projects endpoints
  ingestion/        one script per data source — re-runnable, idempotent-ish
                     (checks existing rows before re-inserting where practical)
data/
  renewable_energy_india.db   SQLite database (~119 MB) — NOT committed to this repo
                               (exceeds GitHub's 100MB file limit); generate it
                               locally with the ingestion commands below (~12 min total)
scripts/
  migrate_sqlite_to_postgres.py   one-time copy of all rows into a Postgres target
tests/
  test_api.py       smoke tests (pytest + FastAPI TestClient) against a throwaway
                     temp DB — routing, schema, and empty-table edge cases; run in CI
Dockerfile, docker-compose.yml, .env.example   containerized run + Postgres deployment
.github/workflows/ci.yml   GitHub Actions: ruff lint + pytest on every push/PR
```

Run the test suite locally with:

```bash
pip install -r requirements-dev.txt
pytest -v
ruff check app/ tests/ scripts/
```

## Running it

**First-time setup — get the database:**

The SQLite database isn't committed to this repo (it's ~119 MB, over
GitHub's 100 MB file limit). Two ways to get it:

**Option A — download the pre-built snapshot (instant):**

```bash
cd renewable-energy-india-api
mkdir -p data
curl -L -o data/renewable_energy_india.db \
  https://github.com/mayankmajoka2000-tech/renewable-energy-india-api/releases/download/v1.0.0-data/renewable_energy_india.db
```

**Option B — regenerate it yourself from the live sources (~12 min, verifies
every checksum fresh):**

```bash
cd renewable-energy-india-api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 -m app.ingestion.fetch_cea_co2_database
python3 -m app.ingestion.fetch_re_capacity
python3 -m app.ingestion.fetch_nasa_power
python3 -m app.ingestion.fetch_emission_factors
python3 -m app.ingestion.compute_avoided_emissions
python3 -m app.ingestion.fetch_re_potential
python3 -m app.ingestion.fetch_re_projects
```

**Local (SQLite):**

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8420
```

Open `http://127.0.0.1:8420/docs` for interactive OpenAPI documentation.

**Docker (SQLite):**

Run the ingestion pipeline above first (it writes to `./data/`, which is
mounted into the container), then:

```bash
docker compose up app
```

**Render (free, live hosting):**

This repo includes a `render.yaml` Blueprint. On [render.com](https://render.com),
sign up with GitHub, then **New +** → **Blueprint** → select this repo → **Apply**.
It builds on Render's free Python runtime and downloads the pre-built database
from the `v1.0.0-data` GitHub Release automatically (no ingestion run needed).
Free-tier services spin down after 15 min idle and cold-start on the next
request. The reference deployment above (https://renewable-energy-india-api.onrender.com)
runs exactly this way.

## Deployment (Postgres)

For a real shared/hosted deployment, swap the locally-generated SQLite file
for Postgres. `app/database.py` reads `DATABASE_URL` from the environment and
falls back to SQLite only if it's unset:

```bash
cp .env.example .env   # then edit if you're not using the docker-compose defaults
docker compose up      # starts Postgres + the app, app waits for Postgres healthcheck
```

The app will create empty tables on Postgres automatically on startup
(`init_db()` in `app/main.py`), but they'll be empty — to carry over the
426k+ existing records from your local SQLite file, run the one-time
migration script against your running Postgres instance:

```bash
export DATABASE_URL=postgresql://renewable:renewable@localhost:5432/renewable_energy_india
python3 -m scripts.migrate_sqlite_to_postgres
```

It copies every table in chunks of 5,000 rows, preserves primary keys, fixes
up Postgres's auto-increment sequences afterward, and is safe to re-run
(skips any table that already has rows on the target instead of duplicating).

To actually put this on the public internet you'll need your own hosting
account — this repo doesn't include one. Any host that runs a Docker image
plus a managed Postgres add-on works (e.g. Render, Railway, Fly.io); point
its `DATABASE_URL` env var at the managed Postgres instance and it uses the
same `docker-compose.yml` topology.

**Honesty note on this section:** Docker, Postgres, and Homebrew aren't
installed on the machine this was built on, so the Postgres/Docker path
above is written to standard, well-tested patterns (official `postgres`
image, healthcheck-gated `depends_on`, `psycopg2-binary` driver) but hasn't
been locally end-to-end executed here. The SQLite path (both bare `uvicorn`
and `docker compose up app`) has been run and verified.

## Re-running / extending the data pipeline

```bash
python3 -m app.ingestion.fetch_cea_co2_database     # ~5 min, ~130k rows
python3 -m app.ingestion.fetch_re_capacity            # ~seconds, ~4.8k rows
python3 -m app.ingestion.fetch_nasa_power             # ~3 min, ~274k rows (33 state capitals + 11 named RE parks)
python3 -m app.ingestion.fetch_emission_factors       # ~2 min, 14 rows
python3 -m app.ingestion.compute_avoided_emissions    # ~1 min, 7 rows (derived)
python3 -m app.ingestion.fetch_re_potential           # instant, 165 rows (transcribed from MNRE yearbook, checksum-verified)
python3 -m app.ingestion.fetch_re_projects            # ~1 min, ~18.6k rows (CEA plant-wise PDF, state x technology checksum-verified)
```

To add more geographic granularity to the resource table (e.g. more named
solar/wind park locations), add verified coordinates to the `RE_PARKS` list in
`app/seed_states.py` and re-run `fetch_nasa_power` — NASA POWER is free,
requires no API key, and one call returns a location's entire multi-year
daily series.

## Endpoints

- `GET /states`
- `GET /emissions/units` — filter by `state`, `plant_type`, `fuel1`, `database_version`
- `GET /emissions/grid-factor`
- `GET /emissions/avoided` — filter by `state`, `financial_year`
- `GET /capacity` — filter by `state`, `source_type`, `month_from`, `month_to`
- `GET /potential` — filter by `state`, `technology`
- `GET /projects` — plant-level RE project registry; filter by `state`, `technology_group`, `min_capacity_mw`, `verified_only`
- `GET /resource/solar-wind` — filter by `state`, `date_from`, `date_to`
- `GET /resource/solar-wind/average` — quick feasibility-screening averages
- `GET /stats/summary` — row counts + source per table (transparency endpoint)

## Public deployment notes

This is an open, no-signup API by design (matching the open-government-data
spirit of the underlying CEA/MNRE/NASA sources) — no API keys required. Two
things are wired in for safe public exposure:

- **Rate limiting** (`app/rate_limit.py`): a per-IP fixed-window limiter,
  120 requests/60s, returns `429` when exceeded. In-memory, single-process —
  swap for Redis-backed limiting if you scale to multiple workers/instances.
- **CORS**: open to all origins, `GET`-only (the API has no write endpoints),
  so it can be called directly from browser-based research tools/dashboards.

## Licensing note

CEA and MNRE publish this data as open government data for public use.
NASA POWER data is public domain, citation requested:
*"These data were obtained from the NASA Langley Research Center POWER
Project funded through the NASA Earth Science Directorate Applied Science Program."*
Cite the underlying government sources (not this API) in any academic or
published work — this API is a convenience layer, not a primary source.
