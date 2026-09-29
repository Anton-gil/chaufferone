"""Voice consent loop: clash -> proposal -> spoken speech -> parsed reply -> validated change.

The LLM never computes money. Speech is templated from engine numbers; replies are parsed
by rules first. Only if rules can't understand a reply, and VOICE_LLM_ENABLED with a key set,
the hosted model maps it to {intent, option, moves} - it sees the reply, the option
descriptions and obligation titles/dates only, never raw messages. The engine validates
every move (deadline, prerequisite order, hard floor) before anything is saved, and every
turn is written to consent_log.
"""

from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app import events
from app.clock import today as clock_today
from app.config import settings
from app.db.models import ConsentLog, Obligation
from app.graph.dag import blocking_subgraph, build_graph
from app.money.clash import detect_clashes
from app.money.fixes import latest_allowed, propose_fixes
from app.money.forecast import effective_date, forecast_daily, is_active
from app.schemas.money import Clash, Fix

# ---------------------------------------------------------------- proposals


@dataclass
class Proposal:
    id: str
    user_id: str
    clash: Clash
    options: list[Fix]
    speech: str
    signature: str
    trigger_id: str | None = None
    status: str = "open"  # open | accepted | declined
    created_at: datetime = field(default_factory=datetime.now)

    def payload(self) -> dict[str, Any]:
        return {
            "proposal_id": self.id,
            "status": self.status,
            "speech": self.speech,
            "clash": self.clash.model_dump(mode="json"),
            "options": [f.model_dump(mode="json") for f in self.options],
            "trigger_id": self.trigger_id,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }


_lock = threading.Lock()
_proposals: dict[str, Proposal] = {}


def current_proposal(user_id: str) -> Proposal | None:
    with _lock:
        return _proposals.get(user_id)


def clear_proposal(user_id: str) -> None:
    with _lock:
        _proposals.pop(user_id, None)


def _signature(clash: Clash) -> str:
    return f"{clash.first_breach_date}|{clash.tier}|{','.join(sorted(clash.obligations_involved))}"


def open_proposal_for(
    db: Session, user_id: str, clash: Clash, trigger_id: str | None = None
) -> Proposal | None:
    sig = _signature(clash)
    existing = current_proposal(user_id)
    if existing and existing.signature == sig:
        # Same clash: keep the open proposal; don't re-ask one the user just declined.
        return existing if existing.status == "open" else None
    options = propose_fixes(db, user_id, clash)
    if not options:
        return None
    speech = build_speech(db, user_id, clash, options, trigger_id)
    p = Proposal(
        id=uuid.uuid4().hex[:12],
        user_id=user_id,
        clash=clash,
        options=options,
        speech=speech,
        signature=sig,
        trigger_id=trigger_id,
    )
    with _lock:
        _proposals[user_id] = p
    events.publish("consent_needed", p.payload())
    return p


# ---------------------------------------------------------------- speech helpers


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def day(d: date | None) -> str:
    return f"{d:%A} the {_ordinal(d.day)}" if d else "an unscheduled day"


def money(x: float | None) -> str:
    return f"₹{float(x or 0):,.0f}"


def spoken(o: Obligation) -> str:
    cat = o.category or ""
    if cat == "puc_certificate":
        return "the PUC"
    if cat == "motor_insurance_renewal":
        return "insurance"
    if cat == "rent":
        return "rent"
    if o.obligation_type == "income":
        return o.title.split(" — ")[0].split(" - ")[0].lower()
    if o.auto_pay_enabled and o.vendor:
        return o.vendor
    return o.title


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def build_speech(
    db: Session, user_id: str, clash: Clash, options: list[Fix], trigger_id: str | None
) -> str:
    obs = {o.id: o for o in db.query(Obligation).filter(Obligation.user_id == user_id).all()}
    parts: list[str] = []
    trigger = obs.get(trigger_id) if trigger_id else None
    if trigger is not None and trigger.auto_pay_enabled:
        parts.append(
            f"Heads up. A {money(trigger.amount)} auto-debit for {trigger.vendor or trigger.title} "
            f"is scheduled for {day(trigger.due_date)}."
        )
        lead = "With it, paying"
    else:
        parts.append("Heads up.")
        lead = "Paying"

    points, _ = forecast_daily(db, user_id)
    breach_day = next((p for p in points if p.date == clash.first_breach_date), None)
    culprit = None
    if breach_day and breach_day.debits:
        biggest = max(breach_day.debits, key=lambda e: e.amount)
        culprit = obs.get(biggest.obligation_id)
    what = f"{lead} {spoken(culprit)}" if culprit else f"{lead} everything as planned"
    parts.append(
        f"{what} on {day(clash.first_breach_date)} would take you {money(clash.max_depth_inr)} "
        f"below your emergency floor."
    )

    a = options[0]
    if a.kind == "defer":
        o = obs[a.obligation_id]
        name = spoken(o)
        if a.depends_on_income and a.income_date:
            inc = next((x for x in obs.values() if x.title == a.depends_on_income), None)
            inc_name = spoken(inc) if inc else a.depends_on_income
            parts.append(
                f"Your {inc_name} is due {day(a.income_date)}, and {name} isn't due till "
                f"{day(o.due_date)}, so I'd pay it {day(a.new_date)}."
            )
        else:
            parts.append(f"{_cap(name)} isn't due till {day(o.due_date)}, so I'd move it to {day(a.new_date)}.")
        sub = blocking_subgraph(build_graph(db, user_id))
        if o.id in sub:
            for pre_id in sub.predecessors(o.id):
                pre = obs.get(pre_id)
                if pre is not None and is_active(pre):
                    parts.append(
                        f"{_cap(spoken(pre))} has to come first, so I'd do that {day(effective_date(pre))}."
                    )
    elif a.kind == "pause_mandate":
        o = obs[a.obligation_id]
        parts.append(f"I'd pause {o.vendor or o.title} in your UPI app before {day(a.deadline)}.")
    else:
        parts.append(f"I'd {a.description[0].lower()}{a.description[1:]}.")

    if len(options) > 1:
        b = options[1]
        ob = obs.get(b.obligation_id)
        if b.kind == "pause_mandate" and ob is not None:
            parts.append(
                f"Or, if you don't need {ob.vendor or ob.title}, pause it in your UPI app before {day(b.deadline)}."
            )
        elif b.kind == "defer" and ob is not None:
            parts.append(f"Or I could move {spoken(ob)} to {day(b.new_date)}.")
        parts.append("Which one?")
    else:
        parts.append("Okay?")
    return " ".join(parts)


# ---------------------------------------------------------------- reply parsing

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}
MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july", "august",
         "september", "october", "november", "december"]
    )
}
_WD_RE = re.compile(r"\b(" + "|".join(sorted(WEEKDAYS, key=len, reverse=True)) + r")\b")
_ORD_RE = re.compile(r"\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b|\bon\s+the\s+(\d{1,2})\b")
_MONTH_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + "|".join(MONTHS) + r")\b|\b("
    + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b"
)
_OPTION_RE = {
    "A": re.compile(r"\b(first( one)?|1st|option (a|1|one)|plan a|the former)\b"),
    "B": re.compile(r"\b(second( one)?|2nd|option (b|2|two)|plan b|the latter)\b"),
    "C": re.compile(r"\b(third( one)?|3rd|option (c|3|three)|plan c)\b"),
}
_AFFIRM_RE = re.compile(
    r"\b(yes|yeah|yep|yup|ok|okay|sure|go ahead|do it|sounds good|fine|alright|all right|approve|confirm|done)\b"
)
_NEGATE_RE = re.compile(r"\b(no|nope|don'?t|do not|cancel|stop|reject|never mind)\b")
_CLAUSE_SPLIT = re.compile(r"[,.;!?]|\bbut\b|\band\b|\bbecause\b|\bcause\b|\bcoz\b|\bsince\b|\bas\b")
_STOPWORDS = {
    "renewal", "payment", "certificate", "subscription", "monthly", "october", "november",
    "the", "for", "with", "from", "bill", "fee", "fees", "contribution", "two-wheeler",
}


def _normalize(text: str) -> str:
    t = text.lower().replace("’", "'")
    t = re.sub(r"\bp\s*\.?\s*u\s*\.?\s*c\b\.?", "puc", t)
    t = re.sub(r"\bpollution(\s+(check|certificate|test|under control))?\b", "puc", t)
    t = re.sub(r"\bpc\b", "puc", t)
    return t


def _aliases(o: Obligation) -> set[str]:
    a: set[str] = set()
    cat = o.category or ""
    title = (o.title or "").lower()
    if cat == "puc_certificate" or "puc" in title:
        a |= {"puc"}
    if cat == "motor_insurance_renewal" or "insurance" in title:
        a |= {"insurance", "policy"}
    if cat == "rent" or "rent" in title:
        a.add("rent")
    if "birthday" in title or "gift" in title:
        a |= {"gift", "birthday", "bday"}
    if o.vendor:
        a.add(o.vendor.lower())
    for w in re.findall(r"[a-z][a-z\-]{3,}", title):
        if w not in _STOPWORDS:
            a.add(w)
    return a


def _resolve_weekday(wd: int, anchor: date | None, today: date) -> date:
    ref = anchor if anchor and anchor >= today else today
    best: tuple[int, date] | None = None
    for k in range(-6, 7):
        d = ref + timedelta(days=k)
        if d.weekday() != wd or d < today:
            continue
        rank = abs(k) * 2 + (1 if k < 0 else 0)  # nearest to the current plan, ties go later
        if best is None or rank < best[0]:
            best = (rank, d)
    return best[1] if best else ref


def _parse_date(clause: str, anchor: date | None, today: date) -> date | None:
    if re.search(r"\bday after tomorrow\b", clause):
        return today + timedelta(days=2)
    if re.search(r"\btomorrow\b", clause):
        return today + timedelta(days=1)
    if re.search(r"\btoday\b", clause):
        return today
    m = _MONTH_RE.search(clause)
    if m:
        dnum = int(m.group(1) or m.group(4))
        month = MONTHS[m.group(2) or m.group(3)]
        year = today.year + (1 if month < today.month else 0)
        try:
            return date(year, month, dnum)
        except ValueError:
            return None
    m = _ORD_RE.search(clause)
    if m:
        dnum = int(m.group(1) or m.group(2))
        ref = anchor or today
        for months_ahead in range(0, 3):
            y, mo = ref.year, ref.month + months_ahead
            while mo > 12:
                y, mo = y + 1, mo - 12
            try:
                cand = date(y, mo, dnum)
            except ValueError:
                continue
            if cand >= today:
                return cand
        return None
    m = _WD_RE.search(clause)
    if m:
        return _resolve_weekday(WEEKDAYS[m.group(1)], anchor, today)
    return None


@dataclass
class ParsedReply:
    intent: str  # approve | reject | unclear
    option_id: str | None = None
    moves: dict[str, date] = field(default_factory=dict)
    parsed_by: str = "rules"


def parse_reply(
    text: str, option_ids: list[str], candidates: list[Obligation], today: date
) -> ParsedReply:
    t = _normalize(text)
    option = next((oid for oid, rx in _OPTION_RE.items() if oid in option_ids and rx.search(t)), None)
    affirm = bool(_AFFIRM_RE.search(t))
    negate = bool(_NEGATE_RE.search(t))

    alias_map = [(o, _aliases(o)) for o in candidates]
    moves: dict[str, date] = {}
    for clause in _CLAUSE_SPLIT.split(t):
        clause = clause.strip()
        if not clause:
            continue
        hits = [
            o for o, al in alias_map
            if any(re.search(rf"\b{re.escape(a)}\b", clause) for a in al)
        ]
        if len(hits) != 1:
            continue
        o = hits[0]
        d = _parse_date(clause, effective_date(o), today)
        if d:
            moves[o.id] = d

    if option or moves or (affirm and not negate):
        return ParsedReply("approve", option or (option_ids[0] if option_ids else None), moves)
    if negate:
        return ParsedReply("reject")
    return ParsedReply("unclear")


def _llm_parse(
    text: str, proposal: Proposal | None, candidates: list[Obligation], today: date
) -> ParsedReply | None:
    if not settings.voice_llm_enabled or not settings.anthropic_api_key:
        return None
    try:
        from app.extract.llm import _get_client

        ids = [o.id for o in candidates]
        option_ids = [f.id for f in proposal.options] if proposal else []
        tool = {
            "name": "record_reply",
            "description": "Record what the user decided about the cash plan.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "enum": ["approve", "reject", "unclear"]},
                    "option_id": {"type": ["string", "null"], "enum": [*option_ids, None]},
                    "moves": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "obligation_id": {"type": "string", "enum": ids},
                                "new_date": {"type": "string", "description": "YYYY-MM-DD"},
                            },
                            "required": ["obligation_id", "new_date"],
                        },
                    },
                },
                "required": ["intent"],
            },
        }
        context = {
            "today": today.isoformat(),
            "weekday_today": f"{today:%A}",
            "proposal": proposal.speech if proposal else None,
            "options": [{"id": f.id, "description": f.description} for f in proposal.options]
            if proposal
            else [],
            "obligations": [
                {
                    "id": o.id,
                    "title": o.title,
                    "planned_on": str(effective_date(o)),
                    "due_date": str(o.due_date),
                }
                for o in candidates
            ],
            "user_reply": text,
        }
        resp = _get_client().messages.create(
            model=settings.anthropic_voice_model,
            max_tokens=300,
            system=(
                "You map a user's spoken reply about their cash plan to a structured decision. "
                "Use only the obligation ids given. Resolve weekday names to the date nearest the "
                "obligation's planned_on that is not before today. If unsure, intent=unclear."
            ),
            tools=[tool],
            tool_choice={"type": "tool", "name": "record_reply"},
            messages=[{"role": "user", "content": str(context)}],
        )
        payload = next(
            (b.input for b in resp.content if getattr(b, "type", None) == "tool_use"), None
        )
        if not payload:
            return None
        moves = {}
        for m in payload.get("moves") or []:
            try:
                moves[m["obligation_id"]] = date.fromisoformat(m["new_date"])
            except (KeyError, ValueError):
                continue
        return ParsedReply(
            payload.get("intent", "unclear"), payload.get("option_id"), moves, parsed_by="llm"
        )
    except Exception as exc:  # the rules path must keep working if the hosted model is down
        print(f"[consent] LLM fallback failed: {exc}")
        return None


# ---------------------------------------------------------------- validation + apply


def _validate(
    db: Session, user_id: str, date_moves: dict[str, date], pauses: set[str], today: date
) -> tuple[list[str], dict[str, date | None]]:
    obs = {o.id: o for o in db.query(Obligation).filter(Obligation.user_id == user_id).all()}
    sub = blocking_subgraph(build_graph(db, user_id))
    new_planned = {oid: effective_date(o) for oid, o in obs.items()}
    new_planned.update(date_moves)
    errors: list[str] = []
    for oid, d in date_moves.items():
        o = obs[oid]
        name = spoken(o)
        if o.obligation_type == "income":
            errors.append("I can't move money coming in, only what goes out.")
            continue
        if o.auto_pay_enabled:
            errors.append(
                f"{_cap(name)} is an auto-debit, so its date is set by the mandate. "
                f"You can pause it in your UPI app instead."
            )
            continue
        if d < today:
            errors.append(f"{_cap(name)} can't be planned in the past.")
            continue
        latest = latest_allowed(o, today)
        if latest and d > latest:
            errors.append(
                f"{_cap(name)} is due {day(o.due_date)}, so the latest I can do it is {day(latest)}."
            )
            continue
        if oid in sub:
            for dep in sub.successors(oid):
                dep_date = new_planned.get(dep)
                if dep_date and d >= dep_date and dep not in pauses:
                    errors.append(
                        f"{_cap(name)} has to happen before {spoken(obs[dep])} on {day(dep_date)}, "
                        f"so the latest is {day(dep_date - timedelta(days=1))}."
                    )
            for pre in sub.predecessors(oid):
                pre_date = new_planned.get(pre)
                if pre_date and pre_date >= d and is_active(obs[pre]):
                    errors.append(
                        f"{_cap(spoken(obs[pre]))} has to come first, on {day(pre_date)}, "
                        f"so {name} can't be before {day(pre_date + timedelta(days=1))}."
                    )
    overrides: dict[str, date | None] = dict(date_moves)
    overrides.update({oid: None for oid in pauses})
    return errors, overrides


def _candidates(db: Session, user_id: str, proposal: Proposal | None) -> list[Obligation]:
    """Obligations a reply may refer to: the proposal's, plus their graph neighbours."""
    active = [o for o in db.query(Obligation).filter(Obligation.user_id == user_id).all() if is_active(o)]
    if proposal is None:
        return active
    sub = blocking_subgraph(build_graph(db, user_id))
    ids: set[str] = set(proposal.clash.obligations_involved)
    for f in proposal.options:
        ids.add(f.obligation_id)
    if proposal.trigger_id:
        ids.add(proposal.trigger_id)
    for oid in list(ids):
        if oid in sub:
            ids |= set(sub.predecessors(oid)) | set(sub.successors(oid))
    return [o for o in active if o.id in ids]


def _log(
    db: Session,
    user_id: str,
    proposal: Proposal | None,
    text: str,
    intent: str,
    parsed_by: str,
    moves: list[dict[str, Any]],
    reply: str,
) -> None:
    db.add(
        ConsentLog(
            user_id=user_id,
            proposal_id=proposal.id if proposal else None,
            spoken_proposal=proposal.speech if proposal else None,
            utterance=text,
            intent=intent,
            parsed_by=parsed_by,
            applied_moves=moves,
            reply=reply,
        )
    )
    db.commit()


def handle_turn(db: Session, user_id: str, text: str, proposal_id: str | None = None) -> dict[str, Any]:
    today = clock_today()
    proposal = current_proposal(user_id)
    if proposal is not None and (proposal.status != "open" or (proposal_id and proposal.id != proposal_id)):
        proposal = None
    candidates = _candidates(db, user_id, proposal)
    option_ids = [f.id for f in proposal.options if f.id] if proposal else []

    parsed = parse_reply(text, option_ids, candidates, today)
    if proposal is None and parsed.intent == "approve" and not parsed.moves:
        parsed = ParsedReply("unclear")  # nothing pending to approve
    if parsed.intent == "unclear":
        parsed = _llm_parse(text, proposal, candidates, today) or parsed

    def done(intent: str, speech: str, moves: list[dict[str, Any]], changed: bool) -> dict[str, Any]:
        _log(db, user_id, proposal, text, intent, parsed.parsed_by, moves, speech)
        return {
            "speech": speech,
            "intent": intent,
            "parsed_by": parsed.parsed_by,
            "applied_moves": moves,
            "plan_changed": changed,
            "proposal_id": proposal.id if proposal else None,
        }

    if parsed.intent == "unclear":
        return done(
            "unclear",
            "Sorry, I didn't catch that. Say 'first one' or 'second one', or give me a day, "
            "like 'do the PUC on Sunday'.",
            [],
            False,
        )

    if parsed.intent == "reject":
        if proposal:
            proposal.status = "declined"
            speech = (
                f"Okay, I won't change anything. You're still {money(proposal.clash.max_depth_inr)} "
                f"short on {day(proposal.clash.first_breach_date)}, so I'll check with you again before then."
            )
        else:
            speech = "Okay, nothing changed."
        return done("reject", speech, [], False)

    option = next((f for f in proposal.options if f.id == parsed.option_id), None) if proposal else None
    # The user's own changes win, and come first so any refusal explains what *they* said.
    date_moves: dict[str, date] = dict(parsed.moves)
    pauses: set[str] = set()
    if option is not None:
        if option.kind == "defer" and option.new_date:
            date_moves.setdefault(option.obligation_id, option.new_date)
        elif option.kind in ("pause_mandate", "pause_subscription"):
            pauses.add(option.obligation_id)

    errors, overrides = _validate(db, user_id, date_moves, pauses, today)
    if errors:
        return done("rejected_move", errors[0] + " Want to try another day?", [], False)

    points, _ = forecast_daily(db, user_id, overrides=overrides)
    floor = [c for c in detect_clashes(points) if c.tier == "floor"]
    if floor:
        c = floor[0]
        return done(
            "rejected_move",
            f"That would still take you {money(c.max_depth_inr)} below your floor on "
            f"{day(c.first_breach_date)}, so I've kept the plan as it was. Want to try the other option?",
            [],
            False,
        )

    obs = {o.id: o for o in db.query(Obligation).filter(Obligation.id.in_(list(overrides))).all()}
    applied: list[dict[str, Any]] = []
    for oid, d in sorted(date_moves.items(), key=lambda kv: kv[1]):
        o = obs[oid]
        applied.append({"obligation_id": oid, "title": o.title, "from": str(effective_date(o)), "to": str(d)})
        o.planned_on = d
        o.plan_locked = True
        o.status = "approved"
        o.verification_state = "approved"
    for oid in pauses:
        o = obs[oid]
        applied.append({"obligation_id": oid, "title": o.title, "from": str(effective_date(o)), "to": "paused"})
        o.status = "pause_requested"
    db.commit()

    bits = [f"{spoken(obs[m['obligation_id']])} on {day(date.fromisoformat(m['to']))}" for m in applied if m["to"] != "paused"]
    speech = "Done. " + (_cap(", ".join(bits)) + ". " if bits else "")
    for m in applied:
        if m["to"] == "paused":
            o = obs[m["obligation_id"]]
            speech += (
                f"Please pause {o.vendor or o.title} in your UPI app before "
                f"{day((effective_date(o) or today) - timedelta(days=1))}. I'll watch for the bank's confirmation. "
            )
    speech += "Nothing touches your floor."
    if option is not None and option.depends_on_income and option.income_date:
        speech += (
            f" If the {option.depends_on_income.split(' — ')[0].lower()} isn't in by "
            f"{day(option.income_date)} night, I'll check with you again."
        )
    speech = speech[0].upper() + speech[1:]
    if proposal:
        proposal.status = "accepted"
    events.publish("plan_changed", {"source": "voice", "applied_moves": applied})

    result = done("approve", speech, applied, True)
    from app.planner import replan_and_check

    replan_and_check(db, user_id)
    return result
