"""ayman-hub command line.

    ayman-hub serve   [--config spokes.toml] [--host 127.0.0.1] [--port 8742]
    ayman-hub doctor  [--config spokes.toml]   checks setup; never prints secret values
    ayman-hub off | on                         kill switch: refuse every tool call / undo
    ayman-hub status                           kill switch, clients, last audit lines
    ayman-hub client add <name>                prints a new hub key ONCE
    ayman-hub client revoke <name>
    ayman-hub client list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ayman_hub.config import ConfigError, hub_home, load_config
from ayman_hub.state import AuditLog, ClientStore, KillSwitch

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "spokes.toml"


def _doctor(config_path: Path) -> int:
    problems = 0
    home = hub_home()
    print(f"hub home: {home}")
    try:
        config = load_config(config_path)
        print(f"config:   {config_path} ok ({len(config.spokes)} spokes, {len(config.enabled_spokes())} switched on)")
    except ConfigError as e:
        print(f"config:   PROBLEM: {e}")
        return 1
    for spoke in config.spokes.values():
        state = "on " if spoke.enabled else "off"
        print(f"  [{state}] {spoke.name:10} {spoke.transport:5} {spoke.mode:10} {spoke.description}")
        if not spoke.enabled:
            continue
        for name in spoke.secret_env_names():
            if os.environ.get(name):
                print(f"         {name}: set")
            else:
                print(f"         {name}: MISSING")
                problems += 1
    clients = ClientStore(home).list()
    active = [n for n, c in clients.items() if not c["revoked"]]
    print(f"clients:  {', '.join(active) if active else 'none yet (ayman-hub client add <name>)'}")
    print(f"switch:   {'OFF (refusing every call)' if KillSwitch(home).is_off() else 'on'}")
    if not config.allowed_hosts:
        print("hosts:    no [hub].allowed_hosts set: fine on localhost, set it before going public")
    print("result:   " + ("ok" if problems == 0 else f"{problems} problem(s)"))
    return 0 if problems == 0 else 1


def _status() -> int:
    home = hub_home()
    print(f"switch:  {'OFF' if KillSwitch(home).is_off() else 'on'}")
    print("clients: " + json.dumps(ClientStore(home).list(), indent=2))
    path = AuditLog(home).path
    lines = path.read_text().splitlines()[-10:] if path.exists() else []
    print(f"last {len(lines)} audit lines:")
    for line in lines:
        print("  " + line)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ayman-hub")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8742)
    d = sub.add_parser("doctor")
    d.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub.add_parser("off")
    sub.add_parser("on")
    sub.add_parser("status")
    c = sub.add_parser("client")
    csub = c.add_subparsers(dest="action", required=True)
    ca = csub.add_parser("add")
    ca.add_argument("name")
    cr = csub.add_parser("revoke")
    cr.add_argument("name")
    csub.add_parser("list")
    args = p.parse_args(argv)
    home = hub_home()

    if args.cmd == "serve":
        import logging

        import uvicorn

        from ayman_hub.app import create_app

        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        app = create_app(load_config(args.config))
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        return 0
    if args.cmd == "doctor":
        return _doctor(args.config)
    if args.cmd == "off":
        KillSwitch(home).set_off(True)
        print("hub is OFF: every tool call is refused until `ayman-hub on`")
        return 0
    if args.cmd == "on":
        KillSwitch(home).set_off(False)
        print("hub is on")
        return 0
    if args.cmd == "status":
        return _status()
    if args.cmd == "client":
        store = ClientStore(home)
        if args.action == "add":
            key = store.add(args.name)
            print(f"hub key for '{args.name}' (shown once; store it in the app's connector settings or 1Password):")
            print(key)
        elif args.action == "revoke":
            store.revoke(args.name)
            print(f"revoked '{args.name}'")
        else:
            print(json.dumps(store.list(), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
