from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyeai.product.models import ReferenceCounter


_PREFIXES = {
    "user": "USR",
    "patient": "PAT",
    "visit": "VIS",
    "prediction": "ANA",
    "note": "NOT",
    "alert": "ALT",
    "report": "REP",
    "conversation": "CHT",
    "message": "MSG",
}


def allocate_reference(
    session: Session,
    kind: str,
    *,
    timestamp: datetime | None = None,
) -> str:
    if kind not in _PREFIXES:
        raise ValueError(f"Unknown reference kind: {kind}")
    prefix = _PREFIXES[kind]
    dated = kind in {"visit", "prediction", "note", "alert", "report", "message"}
    date_token = (timestamp or datetime.now(timezone.utc)).strftime("%Y%m%d") if dated else None
    counter_key = f"{prefix}:{date_token}" if date_token else prefix

    counter = session.scalar(
        select(ReferenceCounter)
        .where(ReferenceCounter.key == counter_key)
        .with_for_update()
    )
    if counter is None:
        counter = ReferenceCounter(key=counter_key, next_value=1)
        session.add(counter)
        session.flush()
    value = int(counter.next_value)
    counter.next_value = value + 1
    if date_token:
        return f"{prefix}-{date_token}-{value:06d}"
    return f"{prefix}-{value:06d}"


def allocate_model_reference(
    session: Session,
    model: type[Any],
    kind: str,
    *,
    timestamp: datetime | None = None,
) -> str:
    while True:
        reference = allocate_reference(session, kind, timestamp=timestamp)
        existing = session.scalar(select(model.id).where(model.display_id == reference))
        if existing is None:
            return reference


def resolve_reference(session: Session, model: type[Any], reference: str) -> Any | None:
    entity = session.get(model, reference)
    if entity is not None:
        return entity
    display_column = getattr(model, "display_id", None)
    if display_column is None:
        return None
    return session.query(model).filter(display_column == reference).one_or_none()
