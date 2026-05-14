"""
tunnel_manager.py — Runs autossh processes, streams logs, tracks status.
"""

import shutil
import socket
import subprocess
import threading
from enum import Enum
from typing import Dict, Optional, Callable
from .tunnel_model import Tunnel


def _diagnose_connection(tunnel: Tunnel) -> tuple[str, list[str]]:
    """Return (problem_summary, [fix_step, ...]) after a tunnel fails.

    Runs a quick port check then an SSH BatchMode probe.
    All results are plain strings suitable for display in the UI.
    """
    host = tunnel.jump_host.split("@")[-1]
    port = tunnel.jump_port
    user = tunnel.jump_host if "@" in tunnel.jump_host else f"user@{host}"

    # ── 1. Can we reach the port at all? ─────────────────────────────────────
    try:
        with socket.create_connection((host, port), timeout=5):
            pass   # port open → continue to auth check
    except socket.timeout:
        return (
            f"Jump host unreachable — {host}:{port} timed out",
            [
                f"Check VPN / network connection",
                f"Ensure jump host is running and port {port} is open",
                f"Test in Terminal:  nc -zv {host} {port}",
                f"Or:  ssh -p {port} {user}",
            ],
        )
    except OSError as e:
        return (
            f"Jump host port {port} refused — {e.strerror}",
            [
                f"SSH server may not be listening on port {port}",
                f"Test in Terminal:  nc -zv {host} {port}",
                f"Contact server admin to confirm port {port} is open",
            ],
        )

    # ── 2. autossh binary present? ────────────────────────────────────────────
    if not shutil.which("autossh"):
        return (
            "autossh not found — cannot start tunnels",
            [
                "Install via Homebrew:  brew install autossh",
                "Then click Retry",
            ],
        )

    # ── 3. SSH auth probe (no password prompt, no side-effects) ──────────────
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=accept-new",
             "-o", "ConnectTimeout=5",
             "-p", str(port), user, "exit"],
            capture_output=True, text=True, timeout=8,
        )
        stderr = result.stderr.strip()

        if result.returncode == 0:
            # Auth works — likely port forward target unreachable
            fwd_hosts = ", ".join(f.remote_host for f in tunnel.forwards)
            return (
                f"SSH auth OK but tunnel still fails — remote target unreachable",
                [
                    f"Verify remote host(s) are reachable from jump host: {fwd_hosts}",
                    f"Ask server admin to check internal routing",
                ],
            )
        if "Permission denied" in stderr or "publickey" in stderr:
            return (
                f"SSH authentication failed for {user}",
                [
                    "Load your SSH key:  ssh-add ~/.ssh/id_ed25519",
                    "Or generate + copy a key via 🔑 SSH Key Manager (sidebar)",
                    f"Or copy manually:  ssh-copy-id -p {port} {user}",
                ],
            )
        if "Host key" in stderr or "IDENTIFICATION HAS CHANGED" in stderr:
            return (
                f"Host key mismatch for {host} — possible MITM or server rebuilt",
                [
                    f"Remove old key:  ssh-keygen -R [{host}]:{port}",
                    "Then retry — you will be prompted to accept the new key",
                ],
            )
        if stderr:
            return (f"SSH error: {stderr[:120]}", ["Check ssh config and try manually"])

    except subprocess.TimeoutExpired:
        return (
            f"SSH handshake timed out — port open but SSH not responding",
            [
                f"Port {port} is reachable but SSH is hanging",
                "Check if sshd is running on jump host",
            ],
        )
    except FileNotFoundError:
        return (
            "ssh binary not found",
            ["Install Xcode Command Line Tools:  xcode-select --install"],
        )

    return ("Unknown connection error", ["Check the Log tab for raw autossh output"])


class TunnelStatus(Enum):
    STOPPED  = "stopped"
    STARTING = "starting"
    CONNECTED = "connected"
    ERROR    = "error"


class TunnelProcess:
    def __init__(self, tunnel: Tunnel,
                 on_log: Callable[[str, str], None],
                 on_status: Callable[[str, TunnelStatus], None],
                 on_diagnosis: Callable[[str, str, list], None] = None):
        self.tunnel = tunnel
        self.on_log = on_log              # (tunnel_id, line)
        self.on_status = on_status        # (tunnel_id, status)
        self.on_diagnosis = on_diagnosis  # (tunnel_id, problem, fixes)
        self._proc: Optional[subprocess.Popen] = None
        self._log_thread: Optional[threading.Thread] = None
        self.status = TunnelStatus.STOPPED
        self._stopping = False

    def start(self):
        if self._proc and self._proc.poll() is None:
            return
        self._stopping = False
        self.status = TunnelStatus.STARTING
        self.on_status(self.tunnel.id, self.status)

        cmd = self.tunnel.build_command()
        self.on_log(self.tunnel.id, f"$ {' '.join(cmd)}")
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self.status = TunnelStatus.CONNECTED
            self.on_status(self.tunnel.id, self.status)
            self._log_thread = threading.Thread(
                target=self._read_output, daemon=True
            )
            self._log_thread.start()
        except Exception as e:
            self.status = TunnelStatus.ERROR
            self.on_log(self.tunnel.id, f"ERROR: {e}")
            self.on_status(self.tunnel.id, self.status)
            threading.Thread(target=self._run_diagnosis, daemon=True).start()

    def stop(self):
        self._stopping = True
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        self.status = TunnelStatus.STOPPED
        self.on_status(self.tunnel.id, self.status)
        self.on_log(self.tunnel.id, "--- tunnel stopped ---")

    def _read_output(self):
        try:
            for line in self._proc.stdout:
                line = line.rstrip()
                if line:
                    self.on_log(self.tunnel.id, line)
            # process ended
            if not self._stopping:
                self.status = TunnelStatus.ERROR
                self.on_status(self.tunnel.id, self.status)
                self.on_log(self.tunnel.id, "--- process exited unexpectedly ---")
                # run diagnosis in a sub-thread so we don't block the log thread
                threading.Thread(
                    target=self._run_diagnosis, daemon=True
                ).start()
        except Exception as e:
            self.on_log(self.tunnel.id, f"Log read error: {e}")

    def _run_diagnosis(self):
        problem, fixes = _diagnose_connection(self.tunnel)
        # always emit to log for posterity
        self.on_log(self.tunnel.id, f"DIAGNOSIS: {problem}")
        for fix in fixes:
            self.on_log(self.tunnel.id, f"  → {fix}")
        # emit structured diagnosis for UI card
        if self.on_diagnosis:
            self.on_diagnosis(self.tunnel.id, problem, fixes)

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


class TunnelManager:
    def __init__(self,
                 on_log: Callable[[str, str], None],
                 on_status: Callable[[str, TunnelStatus], None],
                 on_diagnosis: Callable[[str, str, list], None] = None):
        self._processes: Dict[str, TunnelProcess] = {}
        self._on_log = on_log
        self._on_status = on_status
        self._on_diagnosis = on_diagnosis

    def start(self, tunnel: Tunnel):
        if tunnel.id not in self._processes:
            self._processes[tunnel.id] = TunnelProcess(
                tunnel, self._on_log, self._on_status, self._on_diagnosis
            )
        self._processes[tunnel.id].tunnel = tunnel
        self._processes[tunnel.id].on_diagnosis = self._on_diagnosis
        self._processes[tunnel.id].start()

    def stop(self, tunnel_id: str):
        if tunnel_id in self._processes:
            self._processes[tunnel_id].stop()

    def stop_all(self):
        for tp in self._processes.values():
            tp.stop()

    def start_all(self, tunnels):
        for t in tunnels:
            if t.enabled:
                self.start(t)

    def status(self, tunnel_id: str) -> TunnelStatus:
        tp = self._processes.get(tunnel_id)
        return tp.status if tp else TunnelStatus.STOPPED

    def pid(self, tunnel_id: str) -> Optional[int]:
        tp = self._processes.get(tunnel_id)
        return tp.pid if tp else None

    def is_running(self, tunnel_id: str) -> bool:
        tp = self._processes.get(tunnel_id)
        return tp.is_running() if tp else False

    def remove(self, tunnel_id: str):
        self.stop(tunnel_id)
        self._processes.pop(tunnel_id, None)
