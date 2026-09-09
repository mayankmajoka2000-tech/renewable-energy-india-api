"""
SQLAlchemy models for the India Renewable Energy & Sustainable Finance API.

Every fact table carries `source`, `source_url`, and `retrieved_at` so any
consumer (e.g. a researcher citing this in a thesis) can trace a number back
to the exact government/scientific publication it came from. Nothing in this
schema is a placeholder for synthetic data — tables are only populated by the
ingestion scripts in app/ingestion/, which pull from live official sources.
"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, UniqueConstraint, Index, Boolean
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class State(Base):
    __tablename__ = "states"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    region = Column(String)          # NR, WR, SR, ER, NER
    latitude = Column(Float)         # capital / centroid, used for resource lookups
    longitude = Column(Float)


class PowerUnit(Base):
    """
    Unit-wise generation + CO2 emissions, sourced from CEA's
    'CO2 Baseline Database for the Indian Power Sector' (thermal/hydro/nuclear).
    One row per generating unit per published database version (roughly one
    version per year), so the same physical unit appears multiple times across
    years — this is intentional: it's a real longitudinal record, not a duplicate.
    """
    __tablename__ = "power_units"

    id = Column(Integer, primary_key=True)
    database_version = Column(String, nullable=False)   # e.g. "20.0_2023_24"
    s_no = Column(Integer)
    plant_name = Column(String, nullable=False)
    unit_no = Column(Integer)
    commissioning_date = Column(Date)
    capacity_mw = Column(Float)
    plant_type = Column(String)      # THERMAL / HYDRO / NUCLEAR
    state = Column(String)
    sector = Column(String)          # STATE / CENTRAL / PVT
    system_owner = Column(String)
    fuel1 = Column(String)
    fuel2 = Column(String)
    net_generation_mu = Column(Float)      # million units (GWh)
    co2_tons_total = Column(Float)
    emission_factor_ton_per_mwh = Column(Float)

    source = Column(String, default="CEA CO2 Baseline Database for the Indian Power Sector")
    source_url = Column(String)
    retrieved_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_power_units_state_version", "state", "database_version"),
    )


class EmissionFactorYearly(Base):
    """Grid-wide combined/OM/BM CO2 emission factors, one row per published database version."""
    __tablename__ = "emission_factors_yearly"

    id = Column(Integer, primary_key=True)
    database_version = Column(String, nullable=False, unique=True)
    financial_year = Column(String)
    combined_margin_emission_factor = Column(Float)   # tCO2/MWh
    operating_margin_emission_factor = Column(Float)
    build_margin_emission_factor = Column(Float)

    source = Column(String, default="CEA CO2 Baseline Database - Results sheet")
    source_url = Column(String)
    retrieved_at = Column(DateTime, default=datetime.utcnow)


class RECapacityMonthly(Base):
    """
    State x renewable-source x month installed capacity (MW), from CEA's
    RE-India state-wise capacity time series.
    """
    __tablename__ = "re_capacity_monthly"

    id = Column(Integer, primary_key=True)
    state = Column(String, nullable=False)
    region = Column(String)
    month = Column(Date, nullable=False)   # normalized to first-of-month
    source_type = Column(String, nullable=False)  # WIND / SOLAR / BIOMASS / BAGASSE / SMALL_HYDEL / OTHERS
    capacity_mw = Column(Float, nullable=False)

    source = Column(String, default="Central Electricity Authority (CEA) - RE India state-wise capacity")
    source_url = Column(String)
    retrieved_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("state", "month", "source_type", name="uq_capacity_state_month_source"),
    )


class REPotential(Base):
    """State-wise renewable energy potential (MW) by technology, from MNRE's
    official 'Renewable Energy Statistics 2024-25' yearbook (Table 7.1)."""
    __tablename__ = "re_potential"

    id = Column(Integer, primary_key=True)
    state = Column(String, nullable=False)
    technology = Column(String, nullable=False)   # Wind, Small Hydro, Biomass, Bagasse Cogeneration, Solar, Large Hydro
    potential_mw = Column(Float)
    as_on = Column(String)   # assessing body/year for that technology's estimate, per MNRE

    source = Column(String, default="Ministry of New and Renewable Energy (MNRE) Renewable Energy Statistics 2024-25")
    source_url = Column(String)
    retrieved_at = Column(DateTime, default=datetime.utcnow)


class SolarWindResourceDaily(Base):
    """
    Daily satellite-derived solar irradiance / wind speed / temperature at
    representative Indian locations, from NASA POWER (MERRA-2 / SYN1DEG
    reanalysis). This is the same underlying data used in global solar/wind
    bankability studies (World Bank ESMAP, IRENA Global Atlas, NREL).
    This is the primary volume table in the database.
    """
    __tablename__ = "solar_wind_resource_daily"

    id = Column(Integer, primary_key=True)
    location_name = Column(String, nullable=False)
    state = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    date = Column(Date, nullable=False)

    ghi_kwh_m2_day = Column(Float)     # ALLSKY_SFC_SW_DWN - all-sky surface shortwave irradiance
    wind_speed_10m_ms = Column(Float)  # WS10M
    temperature_2m_c = Column(Float)   # T2M

    source = Column(String, default="NASA POWER (Prediction Of Worldwide Energy Resources)")
    source_url = Column(String, default="https://power.larc.nasa.gov/")
    retrieved_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("location_name", "date", name="uq_resource_location_date"),
        Index("ix_resource_state_date", "state", "date"),
    )


class REProject(Base):
    """
    Individual renewable energy plants/projects (name, developer, capacity,
    district, commissioning date), transcribed from CEA's Renewable Project
    Monitoring Division "Plant-wise details of RE Installed Capacity" report
    (as of Oct/Dec 2019 -- the most recent structured plant-level listing CEA
    has published; see module docstring in app/ingestion/fetch_re_projects.py
    for the full sourcing/verification chain and known limitations).

    `state_tech_verified` marks whether this row's (state, technology_group)
    total reconciles with CEA's own published "Plantwise data furnished by
    State" aggregate for that state/technology (i.e. the same report
    checksums its own plant list against a summary table up front) within a
    3% tolerance. Rows in unverified groups are still real, directly
    transcribed plant records -- they just come from report sections with
    known PDF text-extraction artifacts (overlapping cell text in a few
    hundred of the 1,958 source pages) that prevented a clean reconciliation,
    so treat them as lower-confidence than the verified rows.
    """
    __tablename__ = "re_projects"

    id = Column(Integer, primary_key=True)
    plant_name = Column(String, nullable=False)
    developer = Column(String)
    capacity_mw = Column(Float, nullable=False)
    technology = Column(String, nullable=False)         # raw label as printed, e.g. "Bagasse", "Bio-mass"
    technology_group = Column(String, nullable=False)    # bucketed: Wind / Solar / Biopower / Small Hydro
    location_district = Column(String)
    state = Column(String, nullable=False)
    commissioning_date_raw = Column(String)              # kept as-is; source has inconsistent date formats
    source_page = Column(Integer)                         # page number in the source PDF, for traceability
    state_tech_verified = Column(Boolean, nullable=False, default=False)

    source = Column(String, default="CEA Renewable Project Monitoring Division - Plant-wise details of RE Installed Capacity")
    source_url = Column(String, default="https://cea.nic.in/wp-content/uploads/2020/04/Plant-wise-details-of-RE-Installed-Capacity-merged.pdf")
    retrieved_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_re_projects_state_tech", "state", "technology_group"),
    )


class AvoidedEmission(Base):
    """
    Derived metric: renewable generation (MU) x grid combined-margin emission
    factor for the matching year = tons of CO2 avoided. Clearly marked as
    computed, not independently observed, per financial-year and state.
    """
    __tablename__ = "avoided_emissions"

    id = Column(Integer, primary_key=True)
    state = Column(String, nullable=False)
    financial_year = Column(String, nullable=False)
    re_generation_mu = Column(Float, nullable=False)
    grid_emission_factor_used = Column(Float, nullable=False)
    co2_avoided_tons = Column(Float, nullable=False)

    methodology = Column(String, default=(
        "CO2 avoided = RE generation (MU) * 1000 * grid combined-margin emission "
        "factor (tCO2/MWh) for the corresponding CEA CO2 Baseline Database version"
    ))
    retrieved_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("state", "financial_year", name="uq_avoided_state_fy"),
    )
