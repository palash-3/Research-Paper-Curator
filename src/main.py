from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.routers import health, papers
from src.services.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="arXiv Paper Curator", version="1.0.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(papers.router, prefix="/api/v1")
