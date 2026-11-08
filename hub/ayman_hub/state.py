"""Runtime state kept outside the repo: client keys, the audit log, the kill switch.

Layout under AYMAN_HUB_HOME (default ~/.ayman-hub), all owner-only:
    clients.json   one entry per agent app: sha256 of its key, never the key
    audit.jsonl    one line per tool call: who, spoke, tool, decision; never content
    OFF            present = kill switch on
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

KEY_PREFIX = "ahk_"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class ClientStore:
    """Per-app hub keys. Only hashes are stored; a key is shown once, when made."""

    def __init__(self, home: Path):
        self.path = _private_dir(home) / "clients.json"

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def add(self, name: str) -> str:
        data = self._load()
        if name in data and not data[name].get("revoked"):
            raise ValueError(f"client '{name}' already exists; revoke it first to issue a new key")
        key = KEY_PREFIX + secrets.token_urlsafe(32)
        data[name] = {"sha256": _hash(key), "created": _now(), "revoked": None}
        self._save(data)
        return key

    def revoke(self, name: str) -> None:
        data = self._load()
        if name not in data:
            raise ValueError(f"no client '{name}'")
        data[name]["revoked"] = _now()
        self._save(data)

    def list(self) -> dict:
        return {
            name: {"created": entry["created"], "revoked": entry.get("revoked")}
            for name, entry in self._load().items()
        }

    def verify(self, key: str | None) -> str | None:
        """Return the client name for a valid, unrevoked key; otherwise None."""
        if not key or not key.startswith(KEY_PREFIX):
            return None
        digest = _hash(key)
        found = None
        for name, entry in self._load().items():
            # Compare against every entry so timing doesn't reveal which one matched.
            if hmac.compare_digest(digest, entry["sha256"]) and not entry.get("revoked"):
                found = name
        return found


class KillSwitch:
    def __init__(self, home: Path):
        self.path = _private_dir(home) / "OFF"

    def is_off(self) -> bool:
        return self.path.exists()

    def set_off(self, off: bool) -> None:
        if off:
            self.path.write_text(_now() + "\n")
            os.chmod(self.path, 0o600)
        elif self.path.exists():
            self.path.unlink()


class AuditLog:
    """Append-only JSON lines. Records who did what; never arguments or results."""

    def __init__(self, home: Path):
        self.path = _private_dir(home) / "audit.jsonl"

    def write(self, *, client: str, spoke: str, tool: str, allowed: bool, reason: str,
              started: float | None = None, error: str | None = None) -> None:
        line = {
            "ts": _now(),
            "client": client,
            "spoke": spoke,
            "tool": tool,
            "decision": "allowed" if allowed else "blocked",
            "reason": reason,
        }
        if started is not None:
            line["ms"] = round((time.monotonic() - started) * 1000)
        if error:
            line["error"] = error[:200]
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(line) + "\n")
