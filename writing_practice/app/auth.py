"""User authentication backed by data/user/*.json."""

from __future__ import annotations

import json
from pathlib import Path

from flask import session
from werkzeug.security import check_password_hash

from .config import PROJECT_ROOT

USERS_DIR = PROJECT_ROOT / "data" / "user"


def _user_files() -> list[Path]:
    if not USERS_DIR.exists():
        return []
    return list(USERS_DIR.glob("*.json"))


def load_users() -> dict[str, dict]:
    users: dict[str, dict] = {}
    for path in _user_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            username = data.get("username", path.stem)
            users[username] = data
        except (json.JSONDecodeError, OSError):
            continue
    return users


def verify_user(username: str, password: str) -> bool:
    user = load_users().get(username)
    if not user:
        return False
    password_hash = user.get("password_hash")
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def is_logged_in() -> bool:
    return session.get("user") is not None


def login_user(username: str) -> None:
    session["user"] = username


def logout_user() -> None:
    session.pop("user", None)
