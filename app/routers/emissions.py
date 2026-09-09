from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PowerUnit, EmissionFactorYearly, AvoidedEmission
from app.schemas import PowerUnitOut, EmissionFactorOut, AvoidedEmissionOut

router = APIRouter(prefix="/emissions", tags=["Emissions & Carbon"])


@router.get("/units", response_model=List[PowerUnitOut])
def list_power_units(
    state: Optional[str] = Query(None, description="Filter by state (case-insensitive substring)"),
    plant_type: Optional[str] = Query(None, description="THERMAL, HYDRO, or NUCLEAR"),
    fuel1: Optional[str] = None,
    database_version: Optional[str] = Query(None, description="Substring match, e.g. '2023_24'"),
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(PowerUnit)
    if state:
        q = q.filter(PowerUnit.state.ilike(f"%{state}%"))
    if plant_type:
        q = q.filter(PowerUnit.plant_type == plant_type.upper())
    if fuel1:
        q = q.filter(PowerUnit.fuel1 == fuel1.upper())
    if database_version:
        q = q.filter(PowerUnit.database_version.ilike(f"%{database_version}%"))
    return q.offset(offset).limit(limit).all()


@router.get("/grid-factor", response_model=List[EmissionFactorOut])
def list_grid_emission_factors(db: Session = Depends(get_db)):
    return db.query(EmissionFactorYearly).order_by(EmissionFactorYearly.database_version).all()


@router.get("/avoided", response_model=List[AvoidedEmissionOut])
def list_avoided_emissions(
    state: Optional[str] = None,
    financial_year: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(AvoidedEmission)
    if state:
        q = q.filter(AvoidedEmission.state.ilike(f"%{state}%"))
    if financial_year:
        q = q.filter(AvoidedEmission.financial_year == financial_year)
    return q.all()
