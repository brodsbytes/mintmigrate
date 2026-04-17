"""Fix permissions for sensitive directories after migration (GnuPG)."""

from __future__ import annotations

import grp
import os
import pwd
import subprocess
from pathlib import Path

def fix_gnupg_permissions(home: Path) -> None:
    gnupg = home / ".gnupg"
    if not gnupg.is_dir():
        return
    try:
        gnupg.chmod(0o700)
    except OSError:
        pass


def fix_sensitive_permissions(home: Path | None = None) -> None:
    home = home or Path.home()
    home = home.expanduser().resolve()
    fix_gnupg_permissions(home)


def recursive_chown_to_current_user(home: Path | None = None) -> int:
    """sudo chown -R current_user:current_group home — for UID mismatches after copy."""
    home = (home or Path.home()).expanduser().resolve()
    uid = os.getuid()
    gid = os.getgid()
    user = pwd.getpwuid(uid).pw_name
    group = grp.getgrgid(gid).gr_name
    target = f"{user}:{group}"
    cmd = ["sudo", "chown", "-R", target, str(home)]
    print(f"\nRunning: {' '.join(cmd)}")
    return subprocess.run(cmd, check=False).returncode
