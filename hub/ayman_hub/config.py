"""Load and validate spokes.toml.

A spoke is one upstream service (Linear, Notion, Gmail...). The config says how
to reach it and what agents may do there. Real keys never live in this file:
`auth_env` and `header_env` name environment variables that hold them.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

VALID_TRANSPORTS = {"http", "stdio"}
VALID_MODES = {"read-only", "read-write"}
VALID_AUTH = {"none", "bearer", "oauth"}
VALID_TOKEN_AUTH = {"client_secret_post", "client_secret_basic"}
DEFAULT_REDIRECT = "http://127.0.0.1:8743/callback"
# Lowercase words joined by single underscores; "__" is reserved as the
# separator between spoke and tool in the names agents see.
SPOKE_NAME = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class ConfigError(ValueError):
    """The config file is invalid. The message says what to fix."""


@dataclass(frozen=True)
class Spoke:
    name: str
    enabled: bool
    transport: str
    url: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    auth_env: str | None = None
    header_env: dict[str, str] = field(default_factory=dict)
    env_passthrough: tuple[str, ...] = ()
    mode: str = "read-only"
    allow_tools: tuple[str, ...] = ()
    deny_tools: tuple[str, ...] = ()
    allow_destructive: tuple[str, ...] = ()
    clients: tuple[str, ...] = ()
    description: str = ""
    # auth: "bearer" sends Authorization: Bearer $auth_env; "oauth" uses the one-time
    # `ayman-hub login <spoke>` sign-in, stored in the hub home and refreshed automatically.
    auth: str = "none"
    oauth_scope: str | None = None
    oauth_client_id_env: str | None = None  # pre-registered app (e.g. Slack); else DCR
    oauth_client_secret_env: str | None = None
    oauth_token_auth: str = "client_secret_post"
    oauth_redirect_uri: str = DEFAULT_REDIRECT
    # Argument checks (policy.decide_call): menu tools' allowed `action` values, and
    # confirm-type arguments only some clients may set.
    allow_actions: dict[str, tuple[str, ...]] = field(default_factory=dict)
    confirm_args: tuple[str, ...] = ()
    confirm_clients: tuple[str, ...] = ()

    def secret_env_names(self) -> list[str]:
        names = list(self.header_env.values()) + list(self.env_passthrough)
        if self.auth_env:
            names.insert(0, self.auth_env)
        for name in (self.oauth_client_id_env, self.oauth_client_secret_env):
            if name:
                names.append(name)
        return names


@dataclass(frozen=True)
class HubConfig:
    name: str
    spokes: dict[str, Spoke]
    allowed_hosts: tuple[str, ...] = ()

    def enabled_spokes(self) -> list[Spoke]:
        return [s for s in self.spokes.values() if s.enabled]


def hub_home() -> Path:
    """Runtime folder for client keys, the audit log and the kill switch. Never in the repo."""
    return Path(os.environ.get("AYMAN_HUB_HOME", "~/.ayman-hub")).expanduser()


def _tuple(value: object, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{where} must be a list of strings")
    return tuple(value)


def _spoke(name: str, raw: dict) -> Spoke:
    where = f"[spokes.{name}]"
    if not SPOKE_NAME.match(name):
        raise ConfigError(f"{where}: name must be lowercase words joined by single underscores")
    known = {
        "enabled", "transport", "url", "command", "args", "auth_env", "header_env",
        "env_passthrough", "mode", "allow_tools", "deny_tools", "allow_destructive",
        "clients", "description", "auth", "oauth_scope", "oauth_client_id_env",
        "oauth_client_secret_env", "oauth_token_auth", "oauth_redirect_uri",
        "allow_actions", "confirm_args", "confirm_clients",
    }
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")

    transport = raw.get("transport", "http")
    if transport not in VALID_TRANSPORTS:
        raise ConfigError(f"{where}: transport must be one of {sorted(VALID_TRANSPORTS)}")
    mode = raw.get("mode", "read-only")
    if mode not in VALID_MODES:
        raise ConfigError(f"{where}: mode must be one of {sorted(VALID_MODES)}")
    url = raw.get("url")
    command = raw.get("command")
    enabled = bool(raw.get("enabled", False))
    # A switched-off spoke may be a placeholder; a switched-on one must be reachable.
    if enabled and transport == "http":
        u = urlparse(url) if isinstance(url, str) else None
        if not u or not (u.scheme == "https" or (u.scheme == "http" and u.hostname in {"127.0.0.1", "localhost"})):
            raise ConfigError(f"{where}: http spokes need a url starting with https:// (plain http only on this machine)")
    if enabled and transport == "stdio" and not isinstance(command, str):
        raise ConfigError(f"{where}: stdio spokes need a command")
    auth = raw.get("auth", "bearer" if raw.get("auth_env") else "none")
    if auth not in VALID_AUTH:
        raise ConfigError(f"{where}: auth must be one of {sorted(VALID_AUTH)}")
    if auth == "bearer" and not raw.get("auth_env"):
        raise ConfigError(f"{where}: auth = \"bearer\" needs auth_env")
    if auth == "oauth":
        if raw.get("auth_env"):
            raise ConfigError(f"{where}: use auth_env or auth = \"oauth\", not both")
        if transport != "http":
            raise ConfigError(f"{where}: auth = \"oauth\" only works on http spokes")
    elif any(k.startswith("oauth_") for k in raw):
        raise ConfigError(f"{where}: oauth_* keys need auth = \"oauth\"")
    if bool(raw.get("oauth_client_id_env")) != bool(raw.get("oauth_client_secret_env")):
        raise ConfigError(f"{where}: set both oauth_client_id_env and oauth_client_secret_env, or neither")
    token_auth = raw.get("oauth_token_auth", "client_secret_post")
    if token_auth not in VALID_TOKEN_AUTH:
        raise ConfigError(f"{where}: oauth_token_auth must be one of {sorted(VALID_TOKEN_AUTH)}")
    redirect = raw.get("oauth_redirect_uri", DEFAULT_REDIRECT)
    parsed = urlparse(redirect) if isinstance(redirect, str) else None
    if not parsed or not (
        parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"})
    ):
        raise ConfigError(f"{where}: oauth_redirect_uri must be https:// or a loopback http:// address")
    allow_actions = raw.get("allow_actions", {})
    if not isinstance(allow_actions, dict) or not all(
        isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v)
        for k, v in allow_actions.items()
    ):
        raise ConfigError(f"{where}: allow_actions must map tool names to lists of action patterns")
    header_env = raw.get("header_env", {})
    if not isinstance(header_env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in header_env.items()
    ):
        raise ConfigError(f"{where}: header_env must map header names to environment variable names")

    return Spoke(
        name=name,
        enabled=enabled,
        transport=transport,
        url=url,
        command=command,
        args=_tuple(raw.get("args"), f"{where}.args"),
        auth_env=raw.get("auth_env"),
        header_env=dict(header_env),
        env_passthrough=_tuple(raw.get("env_passthrough"), f"{where}.env_passthrough"),
        mode=mode,
        allow_tools=_tuple(raw.get("allow_tools"), f"{where}.allow_tools"),
        deny_tools=_tuple(raw.get("deny_tools"), f"{where}.deny_tools"),
        allow_destructive=_tuple(raw.get("allow_destructive"), f"{where}.allow_destructive"),
        clients=_tuple(raw.get("clients"), f"{where}.clients"),
        description=str(raw.get("description", "")),
        auth=auth,
        oauth_scope=raw.get("oauth_scope"),
        oauth_client_id_env=raw.get("oauth_client_id_env"),
        oauth_client_secret_env=raw.get("oauth_client_secret_env"),
        oauth_token_auth=token_auth,
        oauth_redirect_uri=redirect,
        allow_actions={k: tuple(v) for k, v in allow_actions.items()},
        confirm_args=_tuple(raw.get("confirm_args"), f"{where}.confirm_args"),
        confirm_clients=_tuple(raw.get("confirm_clients"), f"{where}.confirm_clients"),
    )


def load_config(path: str | Path) -> HubConfig:
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text())
    except FileNotFoundError as e:
        raise ConfigError(f"config not found: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e

    hub = raw.get("hub", {})
    spokes_raw = raw.get("spokes", {})
    if not isinstance(spokes_raw, dict):
        raise ConfigError("[spokes] must be a table of spokes")
    spokes = {name: _spoke(name, body) for name, body in spokes_raw.items()}
    return HubConfig(
        name=str(hub.get("name", "ayman-hub")),
        spokes=spokes,
        allowed_hosts=_tuple(hub.get("allowed_hosts"), "[hub].allowed_hosts"),
    )
