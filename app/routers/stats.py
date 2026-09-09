from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    PowerUnit, EmissionFactorYearly, RECapacityMonthly,
    REPotential, SolarWindResourceDaily, AvoidedEmission, State, REProject,
)
from app.schemas import SummaryOut

router = APIRouter(prefix="/stats", tags=["Stats"])

TABLES = [
    (State, "states", "Curated master list (region + capital coordinates)"),
    (PowerUnit, "emissions/units", "CEA CO2 Baseline Database for the Indian Power Sector (all archived versions)"),
    (EmissionFactorYearly, "emissions/grid-factor", "CEA CO2 Baseline Database - Results sheet"),
    (RECapacityMonthly, "capacity", "CEA RE-India state-wise capacity time series"),
    (REPotential, "potential", "MNRE Renewable Energy Statistics 2024-25, Table 7.1"),
    (REProject, "projects", "CEA Renewable Project Monitoring Division - Plant-wise details of RE Installed Capacity"),
    (SolarWindResourceDaily, "resource/solar-wind", "NASA POWER (MERRA-2/SYN1DEG satellite reanalysis)"),
    (AvoidedEmission, "emissions/avoided", "Derived: RE generation x grid emission factor"),
]


@router.get("/summary", response_model=List[SummaryOut])
def summary(db: Session = Depends(get_db)):
    out = []
    for model, endpoint, source in TABLES:
        out.append(SummaryOut(table=endpoint, row_count=db.query(model).count(), source=source))
    return out
