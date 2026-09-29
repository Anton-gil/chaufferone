"""Auto-wire prerequisite edges from the dependency template knowledge pack.

When an obligation with category X exists, and a template says X depends on
category Y, and the user has an obligation with category Y, we create the edge.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import DependencyTemplate, Obligation, PrerequisiteEdge


def auto_link_prerequisites(db: Session, user_id: str) -> int:
    """Idempotent: skips edges that already exist. Returns count added."""
    obligations = db.query(Obligation).filter(Obligation.user_id == user_id).all()
    by_cat: dict[str, list[Obligation]] = {}
    for o in obligations:
        if o.category:
            by_cat.setdefault(o.category, []).append(o)

    templates = db.query(DependencyTemplate).all()
    existing = {
        (e.obligation_id, e.prerequisite_id)
        for e in db.query(PrerequisiteEdge).all()
    }

    added = 0
    for tmpl in templates:
        parents = by_cat.get(tmpl.parent_category, [])
        prereqs = by_cat.get(tmpl.prereq_category, [])
        if not parents or not prereqs:
            continue
        for parent in parents:
            for prereq in prereqs:
                if parent.id == prereq.id:
                    continue
                key = (parent.id, prereq.id)
                if key in existing:
                    continue
                db.add(
                    PrerequisiteEdge(
                        obligation_id=parent.id,
                        prerequisite_id=prereq.id,
                        lead_time_days=tmpl.lead_time_days,
                        confidence=float(tmpl.confidence),
                        legal_basis=tmpl.legal_basis,
                        is_blocking=True,
                        edge_kind="needs_first",
                    )
                )
                existing.add(key)
                added += 1
    if added:
        db.commit()
    return added
