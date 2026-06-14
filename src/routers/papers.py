from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.services.database import get_db

router = APIRouter()


@router.get("/papers")
def list_papers(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return db.query(Paper).offset(skip).limit(limit).all()


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str, db: Session = Depends(get_db)):
    return db.query(Paper).filter(Paper.id == paper_id).first()
