"""Preflight process checks and rsync helpers (network transfer only)."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from pathlib import Path


# (process name for pgrep -x, human label)
_INTERFERING: tuple[tuple[str, str], ...] = (
    ("firefox", "Firefox"),
    ("thunderbird", "Thunderbird"),
    ("chrome", "Google Chrome / Chromium (chrome)"),
    ("chromium", "Chromium"),
    ("chromium-browser", "Chromium (chromium-browser)"),
    ("google-chrome-stable", "Google Chrome (stable)"),
    ("msedge", "Microsoft Edge"),
    ("brave-browser", "Brave"),
    ("cursor", "Cursor"),
)


def _pgrep_x(name: str) -> bool:
    try:
        r = subprocess.run(
            ["pgrep", "-x", name],
            check=False,
            capture_output=True,
        )
    except OSError:
        return False
    return r.returncode == 0


def find_interfering_processes() -> list[tuple[str, str]]:
    """Return list of (binary_name, label) for running profile-heavy apps."""
    running: list[tuple[str, str]] = []
    for binary, label in _INTERFERING:
        if _pgrep_x(binary):
            running.append((binary, label))
    return running


def ssh_connection_ok(remote_spec: str, timeout_s: int = 12) -> tuple[bool, str]:
    """
    Test SSH to user@host without password prompt (BatchMode).
    First-time host keys: uses StrictHostKeyChecking=accept-new when supported.
    """
    remote_spec = remote_spec.strip()
    if not remote_spec:
        return False, "Empty SSH target."
    try:
        r = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                f"ConnectTimeout={timeout_s}",
                "-o",
                "StrictHostKeyChecking=accept-new",
                remote_spec,
                "true",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s + 8,
        )
    except subprocess.TimeoutExpired:
        return False, "SSH connection timed out."
    except FileNotFoundError:
        return False, "ssh command not found."
    except OSError as e:
        return False, str(e)
    if r.returncode == 0:
        return True, ""
    err = (r.stderr or r.stdout or "").strip() or f"exit code {r.returncode}"
    return False, err


def ssh_mkdir_p(remote_spec: str, remote_paths: list[str], dry_run: bool = False) -> int:
    """Create one or more directories on remote via SSH (mkdir -p)."""
    if not remote_paths:
        return 0
    cmd = ["ssh", remote_spec, "mkdir", "-p"] + list(remote_paths)
    if dry_run:
        print(f"[dry-run] {' '.join(cmd)}")
        return 0
    return subprocess.run(cmd, check=False).returncode


def run_ssh_copy_id(remote_spec: str) -> int:
    """Copy the local SSH public key to remote so subsequent connections don't need a password.

    Generates an ed25519 key pair if the user has no SSH keys yet.
    Interactive — prompts for the remote password in the terminal.
    """
    ssh_dir = Path.home() / ".ssh"
    has_key = ssh_dir.is_dir() and any(ssh_dir.glob("id_*"))
    if not has_key:
        print("\nGenerating an SSH key pair (ed25519)…")
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(ssh_dir / "id_ed25519")],
            check=False,
        )
    print(f"\nRunning: ssh-copy-id {remote_spec}")
    print("Enter the new PC's password when prompted.\n")
    return subprocess.run(["ssh-copy-id", remote_spec], check=False).returncode


def run_ssh_copy_id_with_password(remote_spec: str, password: str) -> tuple[int, str]:
    """Copy the local SSH public key to remote using the supplied password via SSH_ASKPASS.

    Generates an ed25519 key pair if the user has no SSH keys yet.
    Fully non-interactive — no terminal password prompt; suitable for GUI mode.
    Returns (returncode, error_message).
    Requires OpenSSH 8.4+ (SSH_ASKPASS_REQUIRE=force), standard on Linux Mint 21+.
    """
    ssh_dir = Path.home() / ".ssh"
    has_key = ssh_dir.is_dir() and any(ssh_dir.glob("id_*"))
    if not has_key:
        print("\nGenerating an SSH key pair (ed25519)…")
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(ssh_dir / "id_ed25519")],
            check=False,
        )

    # Write a tiny Python askpass helper so password quoting is never an issue
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(f"#!/usr/bin/env python3\nimport sys\nsys.stdout.write({repr(password)})\n")
        askpass = f.name
    os.chmod(askpass, stat.S_IRWXU)

    try:
        env = os.environ.copy()
        env["SSH_ASKPASS"] = askpass
        env["SSH_ASKPASS_REQUIRE"] = "force"  # OpenSSH 8.4+ — don't fall back to tty
        r = subprocess.run(
            ["ssh-copy-id", remote_spec],
            env=env,
            start_new_session=True,  # detach from controlling tty so SSH uses SSH_ASKPASS
            capture_output=True,
            text=True,
        )
        err = (r.stderr or r.stdout or "").strip()
        print(f"ssh-copy-id exit {r.returncode}: {err}")
        return r.returncode, err
    finally:
        try:
            os.unlink(askpass)
        except OSError:
            pass


def rsync_ssh_push_project(project_dir: Path, remote_spec: str, dry_run: bool = False) -> int:
    """Rsync the mintmigrate project to ~/mintmigrate/ on remote, skipping runtime artifacts.

    This ensures the new PC has the tool ready to run without any manual setup.
    """
    src = str(project_dir).rstrip("/") + "/"
    dest = f"{remote_spec}:mintmigrate/"
    cmd = [
        "rsync", "-a", "--mkpath", "-z",
        "--exclude=.venv/",
        "--exclude=*.egg-info/",
        "--exclude=__pycache__/",
        "--exclude=.git/",
        "-e", "ssh",
        src, dest,
    ]
    if dry_run:
        cmd.insert(1, "--dry-run")
        print(f"[dry-run] {' '.join(cmd)}")
        return 0
    print(f"\nRunning: {' '.join(cmd)}\n")
    r = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="")
    return r.returncode


def rsync_ssh_push_path(local_path: Path, remote_spec: str, remote_path: str, dry_run: bool = False) -> int:
    """Push a single local path directly to its destination on remote via rsync over SSH.

    Directories are sent with a trailing slash so rsync merges contents rather than
    nesting the directory name inside the destination. --mkpath creates any missing
    parent directories on the remote automatically (requires rsync 3.2.3+, standard
    on Ubuntu 22.04 / Linux Mint 21+).
    """
    if local_path.is_dir():
        src = str(local_path).rstrip("/") + "/"
        rdest = remote_path.rstrip("/") + "/"
    else:
        src = str(local_path)
        rdest = remote_path
    dest = f"{remote_spec}:{rdest}"
    cmd = ["rsync", "-a", "--mkpath", "-z", "-e", "ssh", src, dest]
    if dry_run:
        cmd.insert(1, "--dry-run")
        print(f"[dry-run] {' '.join(cmd)}")
        return 0
    print(f"rsync {src} -> {dest}")
    r = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="")
    return r.returncode
