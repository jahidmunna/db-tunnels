"""
Tests for tunnel_model.py — data model, serialisation, command building.
No subprocesses, no GUI, no filesystem side-effects (patched).
"""

import json
import os
import uuid
import pytest

from db_tunnels.tunnel_model import (
    ForwardRule,
    Tunnel,
    load_tunnels,
    save_tunnels,
    _default_tunnels,
)


# ── ForwardRule ──────────────────────────────────────────────────────────────

class TestForwardRule:
    def test_to_ssh_flag_ipv4(self):
        rule = ForwardRule(local_port=5432, remote_host="db.internal", remote_port=5432)
        assert rule.to_ssh_flag() == "5432:db.internal:5432"

    def test_to_ssh_flag_ipv6(self):
        rule = ForwardRule(8125, "2001:db8::1", 8124)
        assert rule.to_ssh_flag() == "8125:[2001:db8::1]:8124"

    def test_to_ssh_flag_different_ports(self):
        rule = ForwardRule(local_port=8125, remote_host="host", remote_port=8124)
        assert rule.to_ssh_flag() == "8125:host:8124"


# ── Tunnel.build_command ─────────────────────────────────────────────────────

class TestTunnelBuildCommand:
    def _make_tunnel(self, forwards) -> Tunnel:
        return Tunnel(
            id=str(uuid.uuid4()),
            name="Test",
            jump_host="user@localhost",
            jump_port=22,
            forwards=forwards,
        )

    def test_starts_with_autossh(self):
        t = self._make_tunnel([ForwardRule(5432, "db", 5432)])
        cmd = t.build_command()
        assert cmd[0] == "autossh"

    def test_monitor_port_disabled(self):
        t = self._make_tunnel([ForwardRule(5432, "db", 5432)])
        cmd = t.build_command()
        idx = cmd.index("-M")
        assert cmd[idx + 1] == "0"

    def test_no_shell_flag(self):
        t = self._make_tunnel([ForwardRule(5432, "db", 5432)])
        assert "-N" in t.build_command()

    def test_jump_host_and_port(self):
        t = self._make_tunnel([ForwardRule(5432, "db", 5432)])
        cmd = t.build_command()
        assert "user@localhost" in cmd
        assert "-p" in cmd
        assert "22" in cmd

    def test_single_forward_rule(self):
        t = self._make_tunnel([ForwardRule(18123, "db-host-1.internal", 18123)])
        cmd = t.build_command()
        assert "-L" in cmd
        idx = cmd.index("-L")
        assert cmd[idx + 1] == "18123:db-host-1.internal:18123"

    def test_multiple_forward_rules(self):
        t = self._make_tunnel([
            ForwardRule(18123, "host1", 18123),
            ForwardRule(19000, "host1", 19000),
        ])
        cmd = t.build_command()
        l_flags = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-L"]
        assert "18123:host1:18123" in l_flags
        assert "19000:host1:19000" in l_flags

    def test_keepalive_options_present(self):
        t = self._make_tunnel([ForwardRule(5432, "db", 5432)])
        t.keepalive_interval = 45
        t.keepalive_count_max = 5
        cmd = " ".join(t.build_command())
        assert "ServerAliveInterval 45" in cmd
        assert "ServerAliveCountMax 5" in cmd


# ── Tunnel serialisation ─────────────────────────────────────────────────────

class TestTunnelSerialisation:
    def _sample(self) -> Tunnel:
        return Tunnel(
            id="abc-123",
            name="My DB",
            jump_host="user@jump",
            jump_port=2222,
            forwards=[ForwardRule(5432, "db.internal", 5432)],
            keepalive_interval=30,
            keepalive_count_max=3,
            enabled=True,
            notes="test note",
        )

    def test_round_trip(self):
        t = self._sample()
        d = t.to_dict()
        t2 = Tunnel.from_dict(d)
        assert t2.id == t.id
        assert t2.name == t.name
        assert t2.jump_host == t.jump_host
        assert t2.jump_port == t.jump_port
        assert len(t2.forwards) == 1
        assert t2.forwards[0].local_port == 5432
        assert t2.forwards[0].remote_host == "db.internal"

    def test_from_dict_defaults(self):
        d = {
            "id": "x", "name": "n", "jump_host": "h", "jump_port": 22,
            "forwards": [],
        }
        t = Tunnel.from_dict(d)
        assert t.keepalive_interval == 30
        assert t.keepalive_count_max == 3
        assert t.enabled is True
        assert t.notes == ""

    def test_new_generates_uuid(self):
        t = Tunnel.new("n", "h", 22, [])
        assert len(t.id) == 36   # uuid4 string length

    def test_multiple_forwards_serialise(self):
        t = self._sample()
        t.forwards.append(ForwardRule(5433, "db2", 5433))
        d = t.to_dict()
        t2 = Tunnel.from_dict(d)
        assert len(t2.forwards) == 2


# ── Persistence (patched filesystem) ─────────────────────────────────────────

class TestPersistence:
    def test_save_and_load(self, tmp_path, monkeypatch):
        config = tmp_path / "tunnels.json"
        monkeypatch.setattr("db_tunnels.tunnel_model.CONFIG_PATH", str(config))

        tunnels = [
            Tunnel.new("T1", "user@host", 22, [ForwardRule(5432, "db", 5432)]),
            Tunnel.new("T2", "user@host", 22, [ForwardRule(8080, "web", 80)]),
        ]
        save_tunnels(tunnels)
        assert config.exists()

        loaded = load_tunnels()
        assert len(loaded) == 2
        assert loaded[0].name == "T1"
        assert loaded[1].name == "T2"

    def test_load_missing_file_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "db_tunnels.tunnel_model.CONFIG_PATH",
            str(tmp_path / "nonexistent.json"),
        )
        tunnels = load_tunnels()
        assert len(tunnels) == 3   # the 3 pre-configured tunnels

    def test_load_corrupt_file_returns_defaults(self, tmp_path, monkeypatch):
        config = tmp_path / "bad.json"
        config.write_text("not json {{{{")
        monkeypatch.setattr("db_tunnels.tunnel_model.CONFIG_PATH", str(config))
        tunnels = load_tunnels()
        assert len(tunnels) == 3

    def test_save_creates_parent_dirs(self, tmp_path, monkeypatch):
        config = tmp_path / "deep" / "nested" / "tunnels.json"
        monkeypatch.setattr("db_tunnels.tunnel_model.CONFIG_PATH", str(config))
        save_tunnels([])
        assert config.exists()

    def test_saved_json_is_valid(self, tmp_path, monkeypatch):
        config = tmp_path / "tunnels.json"
        monkeypatch.setattr("db_tunnels.tunnel_model.CONFIG_PATH", str(config))
        save_tunnels(_default_tunnels())
        data = json.loads(config.read_text())
        assert isinstance(data, list)
        assert all("id" in t and "name" in t for t in data)


# ── Default tunnels ──────────────────────────────────────────────────────────

class TestDefaultTunnels:
    def test_three_defaults(self):
        tunnels = _default_tunnels()
        assert len(tunnels) == 3

    def test_all_have_unique_ids(self):
        tunnels = _default_tunnels()
        ids = [t.id for t in tunnels]
        assert len(set(ids)) == 3

    def test_clickhouse_has_two_forwards(self):
        tunnels = _default_tunnels()
        # first default tunnel is ClickHouse with two port forwards
        ch = tunnels[0]
        assert len(ch.forwards) == 2

    def test_all_use_same_jump_host(self):
        tunnels = _default_tunnels()
        hosts = {t.jump_host for t in tunnels}
        assert len(hosts) == 1   # all share one jump host

    def test_all_use_same_jump_port(self):
        tunnels = _default_tunnels()
        ports = {t.jump_port for t in tunnels}
        assert len(ports) == 1   # all share one jump port
