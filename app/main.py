"""Sutradhar - the local-first obligation engine.

Run with: uv run uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.seeds import seed_dependency_templates
from app.db.session import SessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        added = seed_dependency_templates(db)
        if added:
            print(f"[chaufferone] seeded {added} dependency templates")
    finally:
        db.close()
    yield


app = FastAPI(
    title="Sutradhar",
    description="The one who holds every thread of your life admin.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
