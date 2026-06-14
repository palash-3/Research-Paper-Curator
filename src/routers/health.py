from fastapi import APIRouter
from sqlalchemy import text

from src.services.database import SessionLocal

router = APIRouter()


@router.get("/api/v1/health")
async def health_check():
    checks = {}

    # Check PostgreSQL
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["postgres"] = "healthy"
    except Exception as e:
        checks["postgres"] = f"unhealthy: {e}"

    return {"status": "ok", "checks": checks}
