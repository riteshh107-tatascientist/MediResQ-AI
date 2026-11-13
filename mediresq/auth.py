"""Authentication (PBKDF2-SHA256 password hashing), role permissions and audit logging."""
from __future__ import annotations
import hashlib, hmac, os, re
from datetime import datetime

from .db import AuditLog, User

ITER = 200_000
PERMS = {
    "view": {"Administrator", "Supply Chain Manager", "Warehouse Manager", "Viewer"},
    "simulate": {"Administrator", "Supply Chain Manager", "Warehouse Manager", "Viewer"},
    "inventory_edit": {"Administrator", "Supply Chain Manager", "Warehouse Manager"},
    "inventory_delete": {"Administrator", "Supply Chain Manager"},
    "ack_alert": {"Administrator", "Supply Chain Manager", "Warehouse Manager"},
    "run_forecast": {"Administrator", "Supply Chain Manager"},
    "run_planner": {"Administrator", "Supply Chain Manager"},
    "approve": {"Administrator", "Supply Chain Manager"},
    "upload": {"Administrator", "Warehouse Manager"},
    "manage_users": {"Administrator"},
    "reset_demo": {"Administrator"},
}


def can(role: str | None, action: str) -> bool:
    return role in PERMS.get(action, set())


def hash_password(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER)
    return f"pbkdf2_sha256${ITER}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, it, salt, dk = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


def password_policy(pw: str) -> str | None:
    if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must be at least 8 characters and contain letters and digits."
    return None


def audit(session, user: str, action: str, entity: str, entity_id="", details: str = ""):
    session.add(AuditLog(user=user, action=action, entity=entity, entity_id=str(entity_id), details=details[:2000], ts=datetime.now()))


def create_user(session, username: str, full_name: str, password: str, role: str) -> User:
    username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{3,30}", username):
        raise ValueError("Username must be 3-30 chars: letters, digits, . _ -")
    if (err := password_policy(password)):
        raise ValueError(err)
    if session.query(User).filter_by(username=username).first():
        raise ValueError("Username already exists")
    u = User(username=username, full_name=full_name.strip()[:80], password_hash=hash_password(password), role=role)
    session.add(u); session.flush()
    return u


def authenticate(session, username: str, password: str) -> User | None:
    u = session.query(User).filter_by(username=(username or "").strip().lower(), active=True).first()
    ok = bool(u) and verify_password(password or "", u.password_hash)
    audit(session, (username or "?")[:40], "LOGIN_OK" if ok else "LOGIN_FAILED", "user", u.id if u else "")
    session.commit()
    return u if ok else None
