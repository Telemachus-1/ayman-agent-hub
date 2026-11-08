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

VALID_TRANSPORTS = {"http", "stdio"}
VALID_MODES = {"read-only", "read-write"}
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

    def secret_env_names(self) -> list[str]:
        names = list(self.header_env.values()) + list(self.env_passthrough)
        if self.auth_env:
            names.insert(0, self.auth_env)
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
        "clients", "description",
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
    if enabled and transport == "http" and not (isinstance(url, str) and url.startswith(("https://", "http://"))):
        raise ConfigError(f"{where}: http spokes need a url starting with https://")
    if enabled and transport == "stdio" and not isinstance(command, str):
        raise ConfigError(f"{where}: stdio spokes need a command")
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
