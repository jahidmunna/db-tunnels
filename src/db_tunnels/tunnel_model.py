"""
tunnel_model.py — Tunnel data model + JSON config persistence.

Config stored at: ~/Library/Application Support/DBTunnels/tunnels.json
"""

import json
import uuid
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional

CONFIG_PATH = os.path.expanduser(
    "~/Library/Application Support/DBTunnels/tunnels.json"
)


@dataclass
class ForwardRule:
    local_port: int
    remote_host: str
    remote_port: int

    def to_ssh_flag(self) -> str:
        # IPv6 addresses must be wrapped in brackets in SSH -L syntax
        host = f"[{self.remote_host}]" if ":" in self.remote_host else self.remote_host
        return f"{self.local_port}:{host}:{self.remote_port}"


@dataclass
class Tunnel:
    id: str
    name: str
    jump_host: str          # e.g. user@jump.example.com
    jump_port: int          # e.g. 22
    forwards: List[ForwardRule]
    keepalive_interval: int = 30
    keepalive_count_max: int = 3
    enabled: bool = True
    notes: str = ""

    @staticmethod
    def new(name: str, jump_host: str, jump_port: int,
            forwards: List[ForwardRule]) -> "Tunnel":
        return Tunnel(
            id=str(uuid.uuid4()),
            name=name,
            jump_host=jump_host,
            jump_port=jump_port,
            forwards=forwards,
        )

    def build_command(self) -> List[str]:
        cmd = [
            "autossh", "-M", "0",
            "-o", f"ServerAliveInterval {self.keepalive_interval}",
            "-o", f"ServerAliveCountMax {self.keepalive_count_max}",
            "-N",
        ]
        for fwd in self.forwards:
            cmd += ["-L", fwd.to_ssh_flag()]
        cmd += [self.jump_host, "-p", str(self.jump_port)]
        return cmd

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Tunnel":
        forwards = [ForwardRule(**f) for f in d.get("forwards", [])]
        return Tunnel(
            id=d["id"],
            name=d["name"],
            jump_host=d["jump_host"],
            jump_port=d["jump_port"],
            forwards=forwards,
            keepalive_interval=d.get("keepalive_interval", 30),
            keepalive_count_max=d.get("keepalive_count_max", 3),
            enabled=d.get("enabled", True),
            notes=d.get("notes", ""),
        )


def load_tunnels() -> List[Tunnel]:
    if not os.path.exists(CONFIG_PATH):
        return _default_tunnels()
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        return [Tunnel.from_dict(t) for t in data]
    except Exception:
        return _default_tunnels()


def save_tunnels(tunnels: List[Tunnel]) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump([t.to_dict() for t in tunnels], f, indent=2)


def _default_tunnels() -> List[Tunnel]:
    """Example tunnels shown on first launch. Replace with your own configuration."""
    return [
        Tunnel(
            id=str(uuid.uuid4()),
            name="ClickHouse (example-host-1)",
            jump_host="user@jump.example.com",
            jump_port=22,
            forwards=[
                ForwardRule(18123, "db-host-1.internal", 18123),
                ForwardRule(19000, "db-host-1.internal", 19000),
            ],
            notes="ClickHouse HTTP :18123, native :19000",
        ),
        Tunnel(
            id=str(uuid.uuid4()),
            name="IPv6 Service (8125→8124)",
            jump_host="user@jump.example.com",
            jump_port=22,
            forwards=[
                ForwardRule(8125, "2001:db8::1", 8124),
            ],
            notes="IPv6 target — note port remapping 8125→8124",
        ),
        Tunnel(
            id=str(uuid.uuid4()),
            name="Postgres (example-host-2)",
            jump_host="user@jump.example.com",
            jump_port=22,
            forwards=[
                ForwardRule(5432, "db-host-2.internal", 5432),
            ],
            notes="Postgres",
        ),
    ]
