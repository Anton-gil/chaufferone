"""Chaufferone - the local-first obligation engine.

Run with: uv run uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.engine_routes import router as engine_router
from app.api.ingest_routes import router as ingest_router
from app.api.routes import router
from app.config import ROOT
from app.db.seeds import seed_dependency_templates
from app.db.session import SessionLocal
from app.knowledge_pack import load_all as load_knowledge_packs


def run_migrations() -> None:
    """Bring the SQLite schema to head on startup, so a fresh clone just works."""
    from alembic.config import Config

    from alembic import command

    (ROOT / "data").mkdir(exist_ok=True)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    db = SessionLocal()
    try:
        added = seed_dependency_templates(db)
        if added:
            print(f"[chaufferone] seeded {added} dependency templates")
        packs = load_knowledge_packs(db)
        for p in packs:
            print(
                f"[chaufferone] knowledge pack '{p.name}' v{p.version} "
                f"({p.templates_installed} new, {p.templates_updated} updated)"
            )
    finally:
        db.close()
    yield


app = FastAPI(
    title="Chaufferone",
    description="The obligation engine: every message becomes an obligation; one sequenced plan.",
    version="0.2.0",
    lifespan=lifespan,
)

import os

_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"]
_env_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_env_origins or _default_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(engine_router)
app.include_router(ingest_router)
