"""
preflight.py — Dependency and connectivity checks run once at startup.

Checks:
  1. autossh       — required to run tunnels
  2. ssh / ssh-keygen / ssh-copy-id — required for key management
  3. sshpass       — optional, needed only for password-based ssh-copy-id
  4. Jump-host port reachability — checks each unique host:port from saved tunnels

Results delivered as a list of CheckResult objects; each has a status, fix
instruction, and optional auto-fix command.
"""

import os
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from .tunnel_model import load_tunnels

# Homebrew installs to /opt/homebrew/bin (Apple Silicon) or /usr/local/bin (Intel).
# The .app bundle inherits a minimal PATH — augment it so shutil.which finds tools.
_BREW_PATHS = ["/opt/homebrew/bin", "/opt/homebrew/sbin",
               "/usr/local/bin", "/usr/local/sbin", "/usr/bin", "/usr/sbin", "/bin", "/sbin"]
os.environ["PATH"] = ":".join(
    _BREW_PATHS + [p for p in os.environ.get("PATH", "").split(":") if p not in _BREW_PATHS]
)

# Resolve brew binary explicitly (needed for Popen auto_fix_cmd)
BREW_BIN = shutil.which("brew") or "/opt/homebrew/bin/brew"


class Severity(Enum):
    OK       = "ok"
    WARNING  = "warning"   # app works but degraded
    ERROR    = "error"     # app cannot function without fix


@dataclass
class CheckResult:
    name: str
    severity: Severity
    message: str
    fix: str = ""                      # human-readable fix instruction
    auto_fix_cmd: Optional[List[str]] = field(default=None)  # run to auto-fix


# ── Individual checks ────────────────────────────────────────────────────────

def check_autossh() -> CheckResult:
    if shutil.which("autossh"):
        return CheckResult("autossh", Severity.OK, "autossh found")
    return CheckResult(
        name="autossh",
        severity=Severity.ERROR,
        message="autossh not found — tunnels cannot start without it.",
        fix="Install via Homebrew: brew install autossh",
        auto_fix_cmd=[BREW_BIN, "install", "autossh"],
    )


def check_ssh() -> CheckResult:
    if shutil.which("ssh"):
        return CheckResult("ssh", Severity.OK, "ssh found")
    return CheckResult(
        name="ssh",
        severity=Severity.ERROR,
        message="ssh not found — required for all tunnel connections.",
        fix="Install Xcode Command Line Tools: xcode-select --install",
        auto_fix_cmd=["xcode-select", "--install"],
    )


def check_ssh_keygen() -> CheckResult:
    if shutil.which("ssh-keygen"):
        return CheckResult("ssh-keygen", Severity.OK, "ssh-keygen found")
    return CheckResult(
        name="ssh-keygen",
        severity=Severity.ERROR,
        message="ssh-keygen not found — cannot generate SSH keys.",
        fix="Install Xcode Command Line Tools: xcode-select --install",
        auto_fix_cmd=["xcode-select", "--install"],
    )


def check_ssh_copy_id() -> CheckResult:
    if shutil.which("ssh-copy-id"):
        return CheckResult("ssh-copy-id", Severity.OK, "ssh-copy-id found")
    return CheckResult(
        name="ssh-copy-id",
        severity=Severity.WARNING,
        message="ssh-copy-id not found — 'Copy to Server' feature unavailable.",
        fix="Install Homebrew openssh: brew install openssh",
        auto_fix_cmd=[BREW_BIN, "install", "openssh"],
    )


def check_sshpass() -> CheckResult:
    if shutil.which("sshpass"):
        return CheckResult("sshpass", Severity.OK, "sshpass found")
    return CheckResult(
        name="sshpass",
        severity=Severity.WARNING,
        message="sshpass not found — SSH Key Manager 'Copy to Server' tab requires it when using password auth. Tunnels and key-based SSH work fine without it.",
        fix="Install via Homebrew: brew install sshpass  (only needed if you copy SSH keys using a password)",
        auto_fix_cmd=[BREW_BIN, "install", "sshpass"],
    )


def check_brew() -> CheckResult:
    if shutil.which("brew"):
        return CheckResult("Homebrew", Severity.OK, "Homebrew found")
    return CheckResult(
        name="Homebrew",
        severity=Severity.WARNING,
        message="Homebrew not found — auto-install buttons will not work.",
        fix='Install Homebrew: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
        auto_fix_cmd=None,   # too complex to auto-run
    )


def check_port(host: str, port: int, timeout: float = 3.0) -> CheckResult:
    name = f"Port {host}:{port}"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return CheckResult(name, Severity.OK, f"{host}:{port} is reachable")
    except socket.timeout:
        return CheckResult(
            name=name,
            severity=Severity.WARNING,
            message=f"Connection to {host}:{port} timed out.",
            fix=(
                f"Check that the jump host is running and port {port} is open.\n"
                f"Try: ssh -p {port} <user>@{host}"
            ),
        )
    except OSError as e:
        return CheckResult(
            name=name,
            severity=Severity.WARNING,
            message=f"Cannot reach {host}:{port} — {e.strerror}.",
            fix=(
                f"Ensure network access and that {host}:{port} is reachable.\n"
                f"Try: nc -zv {host} {port}"
            ),
        )


def check_jump_hosts() -> List[CheckResult]:
    """Check reachability of every unique jump host:port from saved tunnels."""
    tunnels = load_tunnels()
    seen = set()
    results = []
    for t in tunnels:
        key = (t.jump_host, t.jump_port)
        if key in seen:
            continue
        seen.add(key)
        # strip user@ prefix to get bare hostname
        host = t.jump_host.split("@")[-1]
        results.append(check_port(host, t.jump_port))
    return results


# ── Run all checks ───────────────────────────────────────────────────────────

def run_all_checks() -> List[CheckResult]:
    results = [
        check_brew(),
        check_autossh(),
        check_ssh(),
        check_ssh_keygen(),
        check_ssh_copy_id(),
        check_sshpass(),
    ]
    results.extend(check_jump_hosts())
    return results


def run_auto_fix(result: CheckResult, on_line: Callable[[str], None],
                 on_done: Callable[[bool, str], None]) -> None:
    """Run result.auto_fix_cmd in background thread, stream output."""
    import threading

    def _run():
        if not result.auto_fix_cmd:
            on_done(False, "No auto-fix available.")
            return
        on_line(f"$ {' '.join(result.auto_fix_cmd)}")
        try:
            proc = subprocess.Popen(
                result.auto_fix_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=os.environ,   # pass enriched PATH so brew finds its deps
            )
            for line in proc.stdout:
                on_line(line.rstrip())
            proc.wait(timeout=300)
            if proc.returncode == 0:
                on_done(True, "Done.")
            else:
                on_done(False, f"Exited with code {proc.returncode}")
        except FileNotFoundError:
            on_done(False, f"Command not found: {result.auto_fix_cmd[0]}")
        except Exception as e:
            on_done(False, str(e))

    threading.Thread(target=_run, daemon=True).start()
