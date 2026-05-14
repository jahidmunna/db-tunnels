"""
ssh_key_manager.py — SSH key discovery, generation, and ssh-copy-id operations.

All subprocess calls are non-blocking (run in threads); results delivered via callbacks.
"""

import os
import subprocess
import threading

# Ensure Homebrew tools are findable in .app bundle (minimal PATH environment)
_BREW_PATHS = ["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin", "/usr/local/sbin"]
os.environ["PATH"] = ":".join(
    _BREW_PATHS + [p for p in os.environ.get("PATH", "").split(":") if p not in _BREW_PATHS]
)
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

SSH_DIR = Path.home() / ".ssh"

KEY_TYPES = ["ed25519", "rsa", "ecdsa"]
DEFAULT_KEY_TYPE = "ed25519"
DEFAULT_BITS = {
    "ed25519": None,   # no -b flag for ed25519
    "rsa": 4096,
    "ecdsa": 521,
}


@dataclass
class SSHKey:
    private_path: Path
    public_path: Path
    key_type: str      # from filename suffix or keygen -l output
    comment: str = ""
    fingerprint: str = ""

    @property
    def name(self) -> str:
        return self.private_path.name

    @property
    def pub_content(self) -> str:
        try:
            return self.public_path.read_text().strip()
        except Exception:
            return ""


def discover_keys() -> List[SSHKey]:
    """Return all SSH key pairs found in ~/.ssh."""
    keys = []
    if not SSH_DIR.exists():
        return keys
    for path in sorted(SSH_DIR.iterdir()):
        pub = path.with_suffix(".pub") if not path.suffix == ".pub" else None
        if path.suffix == ".pub" or not path.is_file():
            continue
        pub_path = Path(str(path) + ".pub")
        if not pub_path.exists():
            continue
        key_type = _detect_key_type(pub_path)
        fingerprint = _get_fingerprint(path)
        comment = _get_comment(pub_path)
        keys.append(SSHKey(
            private_path=path,
            public_path=pub_path,
            key_type=key_type,
            comment=comment,
            fingerprint=fingerprint,
        ))
    return keys


def generate_key(
    key_type: str,
    key_path: Path,
    comment: str,
    passphrase: str,
    on_done: Callable[[bool, str], None],
) -> None:
    """Generate SSH key pair in a background thread.

    on_done(success: bool, message: str)
    """
    def _run():
        SSH_DIR.mkdir(mode=0o700, exist_ok=True)
        cmd = ["ssh-keygen", "-t", key_type, "-f", str(key_path), "-C", comment]
        bits = DEFAULT_BITS.get(key_type)
        if bits:
            cmd += ["-b", str(bits)]
        # passphrase: empty string = no passphrase
        cmd += ["-N", passphrase]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                on_done(True, f"Key generated: {key_path}")
            else:
                on_done(False, result.stderr.strip() or "ssh-keygen failed")
        except FileNotFoundError:
            on_done(False, "ssh-keygen not found — is OpenSSH installed?")
        except subprocess.TimeoutExpired:
            on_done(False, "ssh-keygen timed out")
        except Exception as e:
            on_done(False, str(e))

    threading.Thread(target=_run, daemon=True).start()


def copy_key_to_server(
    key_path: Path,
    user: str,
    host: str,
    port: int,
    password: Optional[str],
    on_progress: Callable[[str], None],
    on_done: Callable[[bool, str], None],
) -> None:
    """Run ssh-copy-id in background thread.

    Tries ssh-copy-id first (password via sshpass if provided).
    on_progress(line) — streamed output
    on_done(success, message)
    """
    def _run():
        # Build command — use sshpass if password provided
        ssh_opts = f"-o StrictHostKeyChecking=accept-new -p {port}"
        if password:
            # sshpass must be installed: brew install sshpass
            cmd = [
                "sshpass", "-p", password,
                "ssh-copy-id",
                "-i", str(key_path) + ".pub",
                "-o", "StrictHostKeyChecking=accept-new",
                "-p", str(port),
                f"{user}@{host}",
            ]
        else:
            cmd = [
                "ssh-copy-id",
                "-i", str(key_path) + ".pub",
                "-o", "StrictHostKeyChecking=accept-new",
                "-p", str(port),
                f"{user}@{host}",
            ]

        on_progress(f"$ {' '.join(cmd)}")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=os.environ,
            )
            for line in proc.stdout:
                on_progress(line.rstrip())
            proc.wait(timeout=60)
            if proc.returncode == 0:
                on_done(True, "Public key copied successfully.")
            else:
                on_done(False, f"ssh-copy-id exited with code {proc.returncode}")
        except FileNotFoundError as e:
            tool = "sshpass" if password and "sshpass" in str(e) else "ssh-copy-id"
            msg = f"{tool} not found."
            if tool == "sshpass":
                msg += " Install: brew install sshpass"
            on_done(False, msg)
        except subprocess.TimeoutExpired:
            on_done(False, "ssh-copy-id timed out after 60s")
        except Exception as e:
            on_done(False, str(e))

    threading.Thread(target=_run, daemon=True).start()


def default_key_path(key_type: str) -> Path:
    name = {"ed25519": "id_ed25519", "rsa": "id_rsa", "ecdsa": "id_ecdsa"}.get(
        key_type, f"id_{key_type}"
    )
    return SSH_DIR / name


def _detect_key_type(pub_path: Path) -> str:
    try:
        content = pub_path.read_text()
        if "ed25519" in content:  return "ed25519"
        if "ecdsa"   in content:  return "ecdsa"
        if "rsa"     in content:  return "rsa"
    except Exception:
        pass
    return "unknown"


def _get_fingerprint(key_path: Path) -> str:
    try:
        result = subprocess.run(
            ["ssh-keygen", "-l", "-f", str(key_path)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _get_comment(pub_path: Path) -> str:
    try:
        parts = pub_path.read_text().strip().split()
        return parts[2] if len(parts) >= 3 else ""
    except Exception:
        return ""
