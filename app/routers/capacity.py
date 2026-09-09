from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RECapacityMonthly, REPotential
from app.schemas import RECapacityOut, REPotentialOut

router = APIRouter(tags=["Capacity & Potential"])


@router.get("/capacity", response_model=List[RECapacityOut])
def list_capacity(
    state: Optional[str] = None,
    source_type: Optional[str] = Query(None, description="WIND, SOLAR, BIOMASS, BAGASSE, SMALL_HYDEL, OTHERS"),
    month_from: Optional[date] = None,
    month_to: Optional[date] = None,
    limit: int = Query(200, le=2000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(RECapacityMonthly)
    if state:
        q = q.filter(RECapacityMonthly.state.ilike(f"%{state}%"))
    if source_type:
        q = q.filter(RECapacityMonthly.source_type == source_type.upper())
    if month_from:
        q = q.filter(RECapacityMonthly.month >= month_from)
    if month_to:
        q = q.filter(RECapacityMonthly.month <= month_to)
    return q.order_by(RECapacityMonthly.month).offset(offset).limit(limit).all()


@router.get("/potential", response_model=List[REPotentialOut])
def list_potential(
    state: Optional[str] = None,
    technology: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(REPotential)
    if state:
        q = q.filter(REPotential.state.ilike(f"%{state}%"))
    if technology:
        q = q.filter(REPotential.technology.ilike(f"%{technology}%"))
    return q.all()
