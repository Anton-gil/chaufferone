"""Versioned knowledge pack loader (§3.3 + §7.6).

Knowledge packs are JSON files in data/knowledge/ that ship with the app or
arrive via the update stream. Each pack declares a name + version and a list
of dependency_templates (the graph's 'needs first' rules). On boot the loader
upserts these into the existing dependency_templates table so the engine picks
them up transparently.

This is the concrete backing for two claims in the handoff:
- §3.3: "Built-in knowledge packs, e.g. 'insurance renewal for a vehicle needs
  a valid PUC' ships with the app."
- §7.6: "Update stream (main revenue): bank SMS formats, biller lists, RBI
  rules and knowledge packs keep changing, so an unpaid copy slowly gets worse
  at reading your messages."

For the demo, packs are read from disk. In production this loader is fed by
the update stream (also signed by the same key that validates the license).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import ROOT
from app.db.models import DependencyTemplate

log = logging.getLogger(__name__)


@dataclass
class LoadedPack:
    name: str
    version: str
    country: str
    description: str
    templates_installed: int
    templates_updated: int


_loaded: list[LoadedPack] = []


def status() -> list[dict[str, Any]]:
    return [
        {
            "name": p.name,
            "version": p.version,
            "country": p.country,
            "description": p.description,
            "templates_installed": p.templates_installed,
            "templates_updated": p.templates_updated,
        }
        for p in _loaded
    ]


def _upsert(db: Session, tpl: dict[str, Any], country: str) -> tuple[bool, bool]:
    parent = tpl["parent_category"]
    prereq = tpl["prereq_category"]
    existing = (
        db.query(DependencyTemplate)
        .filter(
            DependencyTemplate.parent_category == parent,
            DependencyTemplate.prereq_category == prereq,
            DependencyTemplate.country == country,
        )
        .first()
    )
    lead = int(tpl.get("lead_time_days", 0))
    basis = tpl.get("legal_basis")
    conf = float(tpl.get("confidence", 1.0))
    if existing is None:
        db.add(
            DependencyTemplate(
                parent_category=parent,
                prereq_category=prereq,
                lead_time_days=lead,
                legal_basis=basis,
                confidence=conf,
                country=country,
            )
        )
        return True, False
    changed = (
        existing.lead_time_days != lead
        or existing.legal_basis != basis
        or float(existing.confidence or 0) != conf
    )
    if changed:
        existing.lead_time_days = lead
        existing.legal_basis = basis
        existing.confidence = conf
    return False, changed


def load_all(db: Session, packs_dir: Path | None = None) -> list[LoadedPack]:
    global _loaded
    _loaded = []
    packs_dir = packs_dir or (ROOT / "data" / "knowledge")
    if not packs_dir.exists():
        return _loaded
    for path in sorted(packs_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log.warning("skipping knowledge pack %s: %s", path.name, e)
            continue
        if not isinstance(raw, dict) or "dependency_templates" not in raw:
            log.warning("skipping knowledge pack %s: missing dependency_templates", path.name)
            continue
        country = raw.get("country", "IN")
        installed = updated = 0
        for tpl in raw["dependency_templates"]:
            try:
                created, changed = _upsert(db, tpl, country)
            except (KeyError, TypeError, ValueError) as e:
                log.warning("bad template in %s: %s", path.name, e)
                continue
            installed += int(created)
            updated += int(changed)
        db.commit()
        _loaded.append(
            LoadedPack(
                name=raw.get("name", path.stem),
                version=raw.get("version", "unknown"),
                country=country,
                description=raw.get("description", ""),
                templates_installed=installed,
                templates_updated=updated,
            )
        )
    return _loaded
