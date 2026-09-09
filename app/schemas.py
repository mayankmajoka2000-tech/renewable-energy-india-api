from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class StateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    region: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]


class PowerUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    database_version: str
    plant_name: Optional[str]
    unit_no: Optional[int]
    commissioning_date: Optional[date]
    capacity_mw: Optional[float]
    plant_type: Optional[str]
    state: Optional[str]
    sector: Optional[str]
    system_owner: Optional[str]
    fuel1: Optional[str]
    fuel2: Optional[str]
    net_generation_mu: Optional[float]
    co2_tons_total: Optional[float]
    emission_factor_ton_per_mwh: Optional[float]
    source: Optional[str]
    source_url: Optional[str]


class EmissionFactorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    database_version: str
    financial_year: Optional[str]
    combined_margin_emission_factor: Optional[float]
    operating_margin_emission_factor: Optional[float]
    build_margin_emission_factor: Optional[float]
    source: Optional[str]


class RECapacityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    state: str
    region: Optional[str]
    month: date
    source_type: str
    capacity_mw: float
    source: Optional[str]


class REPotentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    state: str
    technology: str
    potential_mw: Optional[float]
    as_on: Optional[str]
    source: Optional[str]


class SolarWindResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    location_name: str
    state: str
    latitude: float
    longitude: float
    date: date
    ghi_kwh_m2_day: Optional[float]
    wind_speed_10m_ms: Optional[float]
    temperature_2m_c: Optional[float]
    source: Optional[str]


class AvoidedEmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    state: str
    financial_year: str
    re_generation_mu: float
    grid_emission_factor_used: float
    co2_avoided_tons: float
    methodology: Optional[str]


class REProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plant_name: str
    developer: Optional[str]
    capacity_mw: float
    technology: str
    technology_group: str
    location_district: Optional[str]
    state: str
    commissioning_date_raw: Optional[str]
    state_tech_verified: bool
    source: Optional[str]
    source_url: Optional[str]


class SummaryOut(BaseModel):
    table: str
    row_count: int
    source: str
    source_url: Optional[str] = None
