from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import State
from app.schemas import StateOut

router = APIRouter(prefix="/states", tags=["States"])


@router.get("", response_model=List[StateOut])
def list_states(db: Session = Depends(get_db)):
    return db.query(State).order_by(State.name).all()
