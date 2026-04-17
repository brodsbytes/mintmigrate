"""Crontab export and import for mintmigrate."""

from __future__ import annotations

import subprocess


def export_crontab() -> str | None:
    """Return the current user's crontab as a string, or None if empty/unavailable."""
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
        return None
    except FileNotFoundError:
        return None


def import_crontab(content: str) -> int:
    """Install crontab from a content string. Returns the exit code."""
    try:
        r = subprocess.run(
            ["crontab", "-"],
            input=content,
            text=True,
            capture_output=True,
            check=False,
        )
        return r.returncode
    except FileNotFoundError:
        return 1
