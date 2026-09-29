"""Engine hooks that run after any batch of new messages lands.

Every ingest path (Gmail, SMS forwarder, SMS backup, WhatsApp, .eml, demo inject)
calls after_ingest() once per batch so the graph, plan and consent loop stay in sync.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.graph.linker import auto_link_prerequisites


def after_ingest(db: Session, user_id: str) -> dict[str, object]:
    edges = auto_link_prerequisites(db, user_id)
    out: dict[str, object] = {"edges_linked": edges}
    try:
        from app.planner import replan_and_check

        out.update(replan_and_check(db, user_id))
    except ImportError:
        pass
    return out
