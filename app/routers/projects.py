from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import REProject
from app.schemas import REProjectOut

router = APIRouter(tags=["Plant-level Projects"])


@router.get("/projects", response_model=List[REProjectOut])
def list_projects(
    state: Optional[str] = None,
    technology_group: Optional[str] = Query(None, description="Wind, Solar, Biopower, Small Hydro"),
    verified_only: bool = Query(
        False,
        description="If true, only return rows whose (state, technology) total "
                     "reconciles with CEA's own published aggregate (see /stats/summary "
                     "and README for what this means -- roughly a quarter of rows are "
                     "verified this way; the rest are still real transcribed records, "
                     "just from report sections with known PDF parsing artifacts).",
    ),
    min_capacity_mw: Optional[float] = None,
    limit: int = Query(200, le=2000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(REProject)
    if state:
        q = q.filter(REProject.state.ilike(f"%{state}%"))
    if technology_group:
        q = q.filter(REProject.technology_group.ilike(f"%{technology_group}%"))
    if verified_only:
        q = q.filter(REProject.state_tech_verified.is_(True))
    if min_capacity_mw is not None:
        q = q.filter(REProject.capacity_mw >= min_capacity_mw)
    return q.order_by(REProject.capacity_mw.desc()).offset(offset).limit(limit).all()
