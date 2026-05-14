"""
Tests for tunnel_manager.py — process lifecycle, status transitions, log routing.
autossh is mocked; no real processes are spawned.
"""

import time
import uuid
import pytest
from unittest.mock import MagicMock, patch, call

from db_tunnels.tunnel_model import Tunnel, ForwardRule
from db_tunnels.tunnel_manager import TunnelManager, TunnelProcess, TunnelStatus


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_tunnel(**kwargs) -> Tunnel:
    defaults = dict(
        id=str(uuid.uuid4()),
        name="Test Tunnel",
        jump_host="user@localhost",
        jump_port=22,
        forwards=[ForwardRule(5432, "db.internal", 5432)],
        keepalive_interval=30,
        keepalive_count_max=3,
        enabled=True,
        notes="",
    )
    defaults.update(kwargs)
    return Tunnel(**defaults)


def make_manager():
    logs = {}
    statuses = {}

    def on_log(tid, line):
        logs.setdefault(tid, []).append(line)

    def on_status(tid, st):
        statuses[tid] = st

    mgr = TunnelManager(on_log=on_log, on_status=on_status)
    return mgr, logs, statuses


# ── TunnelProcess ────────────────────────────────────────────────────────────

class TestTunnelProcess:
    def test_initial_status_stopped(self):
        t = make_tunnel()
        tp = TunnelProcess(t, lambda *a: None, lambda *a: None)
        assert tp.status == TunnelStatus.STOPPED

    def test_is_running_false_before_start(self):
        t = make_tunnel()
        tp = TunnelProcess(t, lambda *a: None, lambda *a: None)
        assert tp.is_running() is False

    def test_pid_none_before_start(self):
        t = make_tunnel()
        tp = TunnelProcess(t, lambda *a: None, lambda *a: None)
        assert tp.pid is None

    def test_start_transitions_to_connected(self):
        t = make_tunnel()
        statuses = []
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.poll.return_value = None
        mock_proc.pid = 12345

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc):
            tp = TunnelProcess(t, lambda *a: None, lambda tid, s: statuses.append(s))
            tp.start()
            time.sleep(0.05)

        assert TunnelStatus.STARTING in statuses
        assert TunnelStatus.CONNECTED in statuses

    def test_start_logs_command(self):
        t = make_tunnel()
        logs = []
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.poll.return_value = None

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc):
            tp = TunnelProcess(t, lambda tid, l: logs.append(l), lambda *a: None)
            tp.start()

        assert any(l.startswith("$ autossh") for l in logs)

    def test_stop_sets_status_stopped(self):
        t = make_tunnel()
        statuses = []
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.poll.return_value = None

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc):
            tp = TunnelProcess(t, lambda *a: None, lambda tid, s: statuses.append(s))
            tp.start()
            tp.stop()

        assert statuses[-1] == TunnelStatus.STOPPED

    def test_stop_on_unstarted_process_safe(self):
        t = make_tunnel()
        tp = TunnelProcess(t, lambda *a: None, lambda *a: None)
        tp.stop()   # must not raise
        assert tp.status == TunnelStatus.STOPPED

    def test_start_sets_error_on_popen_failure(self):
        t = make_tunnel()
        statuses = []

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", side_effect=FileNotFoundError("autossh not found")):
            tp = TunnelProcess(t, lambda *a: None, lambda tid, s: statuses.append(s))
            tp.start()

        assert TunnelStatus.ERROR in statuses

    def test_start_logs_error_on_popen_failure(self):
        t = make_tunnel()
        logs = []

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", side_effect=FileNotFoundError("autossh not found")):
            tp = TunnelProcess(t, lambda tid, l: logs.append(l), lambda *a: None)
            tp.start()

        assert any("ERROR" in l for l in logs)

    def test_double_start_does_not_spawn_second_process(self):
        import queue
        t = make_tunnel()
        mock_proc = MagicMock()
        q = queue.Queue()
        mock_proc.stdout = iter(q.get, None)   # blocks — keeps log thread alive
        mock_proc.poll.return_value = None

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc) as mock_popen:
            tp = TunnelProcess(t, lambda *a: None, lambda *a: None)
            tp.start()
            tp.start()   # second call must be a no-op while process is running
            assert mock_popen.call_count == 1
            q.put(None)  # unblock log thread


# ── TunnelManager ────────────────────────────────────────────────────────────

class TestTunnelManager:
    def test_status_unknown_returns_stopped(self):
        mgr, _, _ = make_manager()
        assert mgr.status("nonexistent-id") == TunnelStatus.STOPPED

    def test_pid_unknown_returns_none(self):
        mgr, _, _ = make_manager()
        assert mgr.pid("nonexistent-id") is None

    def test_is_running_unknown_returns_false(self):
        mgr, _, _ = make_manager()
        assert mgr.is_running("nonexistent-id") is False

    def test_start_creates_process(self):
        mgr, logs, _ = make_manager()
        t = make_tunnel()

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.poll.return_value = None

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc):
            mgr.start(t)
            assert t.id in mgr._processes

    def test_stop_all_stops_all_running(self):
        mgr, _, statuses = make_manager()
        t1, t2 = make_tunnel(name="A"), make_tunnel(name="B")

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.poll.return_value = None

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc):
            mgr.start(t1)
            mgr.start(t2)

        mgr.stop_all()
        assert statuses.get(t1.id) == TunnelStatus.STOPPED
        assert statuses.get(t2.id) == TunnelStatus.STOPPED

    def test_start_all_skips_disabled(self):
        import queue
        mgr, _, _ = make_manager()
        t_on  = make_tunnel(name="enabled",  enabled=True)
        t_off = make_tunnel(name="disabled", enabled=False)

        q = queue.Queue()
        mock_proc = MagicMock()
        mock_proc.stdout = iter(q.get, None)  # blocks until None sentinel
        mock_proc.poll.return_value = None

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("db_tunnels.tunnel_manager.subprocess.run"):
            mgr.start_all([t_on, t_off])
            # only t_on should have triggered Popen
            assert mock_popen.call_count == 1
            q.put(None)  # unblock log thread

    def test_remove_stops_and_cleans_up(self):
        mgr, _, _ = make_manager()
        t = make_tunnel()

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.poll.return_value = None

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc):
            mgr.start(t)

        mgr.remove(t.id)
        assert t.id not in mgr._processes

    def test_logs_routed_to_callback(self):
        mgr, logs, _ = make_manager()
        t = make_tunnel()

        mock_proc = MagicMock()
        mock_proc.stdout = iter(["line from autossh\n"])
        mock_proc.poll.return_value = None

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc):
            mgr.start(t)
            time.sleep(0.1)   # let log thread flush

        all_logs = logs.get(t.id, [])
        assert any("autossh" in l or "line from" in l for l in all_logs)

    def test_status_callbacks_fired(self):
        mgr, _, _ = make_manager()
        all_statuses = []
        t = make_tunnel()

        mock_proc = MagicMock()
        # keep stdout open so log thread doesn't exit and flip to ERROR
        import queue
        q = queue.Queue()
        mock_proc.stdout = iter(q.get, None)   # blocks until sentinel pushed
        mock_proc.poll.return_value = None

        with patch("db_tunnels.tunnel_manager.subprocess.Popen", return_value=mock_proc):
            mgr2 = TunnelManager(
                on_log=lambda *a: None,
                on_status=lambda tid, s: all_statuses.append(s),
            )
            mgr2.start(t)
            time.sleep(0.05)
            assert TunnelStatus.STARTING in all_statuses
            assert TunnelStatus.CONNECTED in all_statuses
            q.put(None)   # unblock log thread
            mgr2.stop(t.id)
