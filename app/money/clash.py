"""Group breach days into contiguous clashes."""

from __future__ import annotations

from app.schemas.money import Clash, DayPoint


def detect_clashes(points: list[DayPoint]) -> list[Clash]:
    clashes: list[Clash] = []
    current: dict | None = None
    for p in points:
        if p.breach_type == "none":
            if current:
                clashes.append(_finalize(current))
                current = None
            continue
        if current is None:
            current = {
                "first": p.date,
                "last": p.date,
                "tier": p.breach_type,
                "max_depth": p.breach_depth_inr,
                "obligations": {(d.obligation_id, d.title) for d in p.debits},
            }
        else:
            current["last"] = p.date
            if p.breach_type == "floor" and current["tier"] == "cushion":
                current["tier"] = "floor"
            current["max_depth"] = max(current["max_depth"], p.breach_depth_inr)
            current["obligations"].update({(d.obligation_id, d.title) for d in p.debits})
    if current:
        clashes.append(_finalize(current))
    return clashes


def _finalize(c: dict) -> Clash:
    ob_pairs = sorted(c["obligations"])
    ids = [i for i, _ in ob_pairs]
    titles = [t for _, t in ob_pairs]
    return Clash(
        id=f"clash-{c['first'].isoformat()}",
        first_breach_date=c["first"],
        last_breach_date=c["last"],
        tier=c["tier"],
        max_depth_inr=c["max_depth"],
        obligations_involved=ids,
        obligation_titles=titles,
    )
