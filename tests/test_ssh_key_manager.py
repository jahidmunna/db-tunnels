"""
Tests for ssh_key_manager.py — key discovery, generation, copy-to-server.
No real ssh-keygen or ssh-copy-id calls; all subprocesses are mocked.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from db_tunnels.ssh_key_manager import (
    SSHKey,
    discover_keys,
    generate_key,
    copy_key_to_server,
    default_key_path,
    _detect_key_type,
    _get_comment,
    KEY_TYPES,
    SSH_DIR,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def write_keypair(tmp_path: Path, name: str, key_type: str = "ed25519") -> tuple[Path, Path]:
    priv = tmp_path / name
    pub  = tmp_path / f"{name}.pub"
    priv.write_text("PRIVATE KEY DATA")
    pub.write_text(f"ssh-{key_type} AAAA...base64== user@host")
    return priv, pub


# ── SSHKey dataclass ─────────────────────────────────────────────────────────

class TestSSHKey:
    def test_name_returns_filename(self, tmp_path):
        priv, pub = write_keypair(tmp_path, "id_ed25519")
        key = SSHKey(priv, pub, "ed25519")
        assert key.name == "id_ed25519"

    def test_pub_content_reads_file(self, tmp_path):
        priv, pub = write_keypair(tmp_path, "id_ed25519")
        key = SSHKey(priv, pub, "ed25519")
        assert "ssh-ed25519" in key.pub_content

    def test_pub_content_missing_file(self, tmp_path):
        priv = tmp_path / "id_ed25519"
        priv.write_text("PRIVATE")
        pub = tmp_path / "id_ed25519.pub"   # does NOT exist
        key = SSHKey(priv, pub, "ed25519")
        assert key.pub_content == ""


# ── Key discovery ────────────────────────────────────────────────────────────

class TestDiscoverKeys:
    def test_finds_keypairs(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db_tunnels.ssh_key_manager.SSH_DIR", tmp_path)
        write_keypair(tmp_path, "id_ed25519", "ed25519")
        write_keypair(tmp_path, "id_rsa", "rsa")

        with patch("db_tunnels.ssh_key_manager._get_fingerprint", return_value="SHA256:abc"):
            keys = discover_keys()

        names = {k.name for k in keys}
        assert "id_ed25519" in names
        assert "id_rsa" in names

    def test_ignores_files_without_pub(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db_tunnels.ssh_key_manager.SSH_DIR", tmp_path)
        (tmp_path / "orphan_key").write_text("PRIVATE")   # no .pub

        keys = discover_keys()
        assert len(keys) == 0

    def test_ignores_pub_only_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db_tunnels.ssh_key_manager.SSH_DIR", tmp_path)
        (tmp_path / "id_ed25519.pub").write_text("ssh-ed25519 AAA user@h")

        keys = discover_keys()
        assert len(keys) == 0

    def test_empty_ssh_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db_tunnels.ssh_key_manager.SSH_DIR", tmp_path)
        keys = discover_keys()
        assert keys == []

    def test_missing_ssh_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db_tunnels.ssh_key_manager.SSH_DIR", tmp_path / "nonexistent")
        keys = discover_keys()
        assert keys == []

    def test_key_type_detected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("db_tunnels.ssh_key_manager.SSH_DIR", tmp_path)
        write_keypair(tmp_path, "id_rsa", "rsa")

        with patch("db_tunnels.ssh_key_manager._get_fingerprint", return_value=""):
            keys = discover_keys()

        assert keys[0].key_type == "rsa"


# ── _detect_key_type ─────────────────────────────────────────────────────────

class TestDetectKeyType:
    def test_ed25519(self, tmp_path):
        p = tmp_path / "id.pub"
        p.write_text("ssh-ed25519 AAAA user@host")
        assert _detect_key_type(p) == "ed25519"

    def test_rsa(self, tmp_path):
        p = tmp_path / "id.pub"
        p.write_text("ssh-rsa AAAA user@host")
        assert _detect_key_type(p) == "rsa"

    def test_ecdsa(self, tmp_path):
        p = tmp_path / "id.pub"
        p.write_text("ecdsa-sha2-nistp256 AAAA user@host")
        assert _detect_key_type(p) == "ecdsa"

    def test_unknown(self, tmp_path):
        p = tmp_path / "id.pub"
        p.write_text("ssh-unknown AAAA user@host")
        assert _detect_key_type(p) == "unknown"

    def test_missing_file(self, tmp_path):
        p = tmp_path / "missing.pub"
        assert _detect_key_type(p) == "unknown"


# ── _get_comment ─────────────────────────────────────────────────────────────

class TestGetComment:
    def test_extracts_comment(self, tmp_path):
        p = tmp_path / "id.pub"
        p.write_text("ssh-ed25519 AAAA user@myhost")
        assert _get_comment(p) == "user@myhost"

    def test_no_comment(self, tmp_path):
        p = tmp_path / "id.pub"
        p.write_text("ssh-ed25519 AAAA")
        assert _get_comment(p) == ""

    def test_missing_file(self, tmp_path):
        assert _get_comment(tmp_path / "nope.pub") == ""


# ── default_key_path ─────────────────────────────────────────────────────────

class TestDefaultKeyPath:
    def test_ed25519(self):
        p = default_key_path("ed25519")
        assert p.name == "id_ed25519"
        assert p.parent == SSH_DIR

    def test_rsa(self):
        assert default_key_path("rsa").name == "id_rsa"

    def test_ecdsa(self):
        assert default_key_path("ecdsa").name == "id_ecdsa"

    def test_unknown_type_fallback(self):
        p = default_key_path("dsa")
        assert p.name == "id_dsa"


# ── generate_key ─────────────────────────────────────────────────────────────

class TestGenerateKey:
    def _run(self, returncode, stdout="", stderr=""):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        results = []

        with patch("db_tunnels.ssh_key_manager.subprocess.run", return_value=result):
            generate_key(
                "ed25519",
                Path("/tmp/test_id"),
                "user@host",
                "",
                lambda ok, msg: results.append((ok, msg)),
            )
            time.sleep(0.1)
        return results

    def test_success(self):
        results = self._run(0)
        assert results[0][0] is True
        assert "test_id" in results[0][1]

    def test_failure_returns_stderr(self):
        results = self._run(1, stderr="file already exists")
        assert results[0][0] is False
        assert "file already exists" in results[0][1]

    def test_ssh_keygen_not_found(self):
        results = []
        with patch("db_tunnels.ssh_key_manager.subprocess.run", side_effect=FileNotFoundError):
            generate_key("ed25519", Path("/tmp/k"), "", "", lambda ok, m: results.append((ok, m)))
            time.sleep(0.1)
        assert results[0][0] is False
        assert "ssh-keygen" in results[0][1]

    def test_timeout(self):
        import subprocess
        results = []
        with patch("db_tunnels.ssh_key_manager.subprocess.run", side_effect=subprocess.TimeoutExpired("ssh-keygen", 30)):
            generate_key("ed25519", Path("/tmp/k"), "", "", lambda ok, m: results.append((ok, m)))
            time.sleep(0.1)
        assert results[0][0] is False
        assert "timed out" in results[0][1]

    def test_ed25519_no_bits_flag(self):
        called_cmds = []
        result = MagicMock(); result.returncode = 0; result.stderr = ""
        with patch("db_tunnels.ssh_key_manager.subprocess.run",
                   side_effect=lambda cmd, **kw: called_cmds.append(cmd) or result):
            generate_key("ed25519", Path("/tmp/k"), "", "", lambda *a: None)
            time.sleep(0.1)
        cmd = called_cmds[0]
        assert "-b" not in cmd   # ed25519 must NOT have -b flag

    def test_rsa_includes_bits_flag(self):
        called_cmds = []
        result = MagicMock(); result.returncode = 0; result.stderr = ""
        with patch("db_tunnels.ssh_key_manager.subprocess.run",
                   side_effect=lambda cmd, **kw: called_cmds.append(cmd) or result):
            generate_key("rsa", Path("/tmp/k"), "", "", lambda *a: None)
            time.sleep(0.1)
        cmd = called_cmds[0]
        assert "-b" in cmd


# ── copy_key_to_server ───────────────────────────────────────────────────────

class TestCopyKeyToServer:
    def _run(self, returncode, lines=None, side_effect=None):
        progress = []
        done = []

        mock_proc = MagicMock()
        mock_proc.stdout = iter(lines or [])
        mock_proc.wait.return_value = None
        mock_proc.returncode = returncode

        def fake_popen(cmd, **kw):
            if side_effect:
                raise side_effect
            return mock_proc

        with patch("db_tunnels.ssh_key_manager.subprocess.Popen", side_effect=fake_popen):
            copy_key_to_server(
                Path("/home/user/.ssh/id_ed25519"),
                "user", "host.internal", 22, None,
                lambda l: progress.append(l),
                lambda ok, m: done.append((ok, m)),
            )
            time.sleep(0.15)
        return progress, done

    def test_success(self):
        _, done = self._run(0, ["Now try logging into the machine"])
        assert done[0][0] is True

    def test_failure_nonzero_exit(self):
        _, done = self._run(1)
        assert done[0][0] is False
        assert "code 1" in done[0][1]

    def test_progress_lines_streamed(self):
        progress, _ = self._run(0, ["line one\n", "line two\n"])
        assert any("line one" in l for l in progress)
        assert any("line two" in l for l in progress)

    def test_command_logged_to_progress(self):
        progress, _ = self._run(0)
        assert any("ssh-copy-id" in l for l in progress)

    def test_ssh_copy_id_not_found(self):
        _, done = self._run(0, side_effect=FileNotFoundError("ssh-copy-id"))
        assert done[0][0] is False
        assert "ssh-copy-id" in done[0][1]

    def test_sshpass_used_when_password_given(self):
        cmds = []
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.returncode = 0

        with patch("db_tunnels.ssh_key_manager.subprocess.Popen",
                   side_effect=lambda cmd, **kw: cmds.append(cmd) or mock_proc):
            copy_key_to_server(
                Path("/tmp/id"), "u", "h", 22, "s3cr3t",
                lambda l: None, lambda ok, m: None,
            )
            time.sleep(0.1)
        assert cmds[0][0] == "sshpass"

    def test_no_password_uses_ssh_copy_id_directly(self):
        cmds = []
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.returncode = 0

        with patch("db_tunnels.ssh_key_manager.subprocess.Popen",
                   side_effect=lambda cmd, **kw: cmds.append(cmd) or mock_proc):
            copy_key_to_server(
                Path("/tmp/id"), "u", "h", 22, None,
                lambda l: None, lambda ok, m: None,
            )
            time.sleep(0.1)
        assert cmds[0][0] == "ssh-copy-id"
