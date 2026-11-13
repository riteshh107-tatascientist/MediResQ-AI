"""Human-in-the-loop approval workflow with full audit trail."""
from __future__ import annotations
from datetime import datetime

import pandas as pd

from .auth import audit, can
from .db import AuditLog, Recommendation


def decide(session, rec_id: int, user: str, role: str, decision: str, comment: str = "", new_qty: int | None = None) -> Recommendation:
    if not can(role, "approve"):
        raise PermissionError("Your role is not permitted to approve or reject recommendations.")
    if decision not in ("Approve", "Reject", "Modify"):
        raise ValueError("Invalid decision")
    r = session.get(Recommendation, rec_id)
    if r is None:
        raise ValueError("Recommendation not found")
    if r.status != "Pending":
        raise ValueError(f"Recommendation already {r.status}")
    if decision == "Reject" and not comment.strip():
        raise ValueError("A comment is required when rejecting")
    if decision == "Modify":
        if not new_qty or new_qty <= 0 or new_qty > r.quantity * 3:
            raise ValueError("Modified quantity must be positive and within 3x of the original")
        r.approved_qty = int(new_qty); r.status = "Modified"
    elif decision == "Approve":
        r.approved_qty = r.quantity; r.status = "Approved"
    else:
        r.status = "Rejected"
    r.decided_by, r.decided_at, r.comment = user, datetime.now(), comment.strip()[:1000]
    audit(session, user, decision.upper(), "recommendation", rec_id,
          f"{r.kind} qty {r.quantity}" + (f" -> {new_qty}" if decision == "Modify" else "") + (f" | {comment}" if comment else ""))
    session.commit()
    return r


def audit_table(session, limit: int = 500) -> pd.DataFrame:
    rows = session.query(AuditLog).order_by(AuditLog.ts.desc()).limit(limit).all()
    return pd.DataFrame([dict(time=a.ts, user=a.user, action=a.action, entity=a.entity, entity_id=a.entity_id, details=a.details) for a in rows])
