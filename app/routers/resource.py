from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SolarWindResourceDaily
from app.schemas import SolarWindResourceOut

router = APIRouter(prefix="/resource", tags=["Solar & Wind Resource"])


@router.get("/solar-wind", response_model=List[SolarWindResourceOut])
def list_resource_data(
    state: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(200, le=5000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Daily satellite-derived GHI (solar irradiance), 10m wind speed, and
    2m temperature at state-capital anchor points, from NASA POWER.
    """
    q = db.query(SolarWindResourceDaily)
    if state:
        q = q.filter(SolarWindResourceDaily.state.ilike(f"%{state}%"))
    if date_from:
        q = q.filter(SolarWindResourceDaily.date >= date_from)
    if date_to:
        q = q.filter(SolarWindResourceDaily.date <= date_to)
    return q.order_by(SolarWindResourceDaily.date).offset(offset).limit(limit).all()


@router.get("/solar-wind/average", tags=["Solar & Wind Resource"])
def average_resource(
    state: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Average GHI / wind speed / temperature for a state over an optional date range — useful for quick project feasibility screening."""
    from sqlalchemy import func

    q = db.query(
        func.avg(SolarWindResourceDaily.ghi_kwh_m2_day),
        func.avg(SolarWindResourceDaily.wind_speed_10m_ms),
        func.avg(SolarWindResourceDaily.temperature_2m_c),
        func.count(SolarWindResourceDaily.id),
    ).filter(SolarWindResourceDaily.state.ilike(f"%{state}%"))
    if date_from:
        q = q.filter(SolarWindResourceDaily.date >= date_from)
    if date_to:
        q = q.filter(SolarWindResourceDaily.date <= date_to)
    avg_ghi, avg_wind, avg_temp, n = q.one()
    return {
        "state": state,
        "days_averaged": n,
        "avg_ghi_kwh_m2_day": avg_ghi,
        "avg_wind_speed_10m_ms": avg_wind,
        "avg_temperature_c": avg_temp,
        "source": "NASA POWER",
    }
