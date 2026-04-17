"""APT package discovery, apt source hints, and flatpak inventory."""

from __future__ import annotations

import gzip
import re
import shutil
import subprocess
from pathlib import Path

# Name patterns that identify system infrastructure packages the user almost
# certainly didn't install directly (pulled in as deps or part of base install).
_SYSTEM_PREFIXES: tuple[str, ...] = (
    "lib",        # shared libraries
    "gir1.2-",    # GObject introspection data
    "linux-",     # kernel images, headers, modules
    "firmware-",  # hardware firmware
    "fonts-",     # font packages
    "python3-",   # Python bindings — almost always installed as deps
)
_SYSTEM_SUFFIXES: tuple[str, ...] = (
    ":i386",   # 32-bit compat packages
    "-dbg",    # debug symbols
    "-dev",    # development headers
)


def _is_user_package(name: str) -> bool:
    return (
        not any(name.startswith(p) for p in _SYSTEM_PREFIXES)
        and not any(name.endswith(s) for s in _SYSTEM_SUFFIXES)
    )


def _pkgs_from_apt_history() -> set[str]:
    """Extract packages from apt history entries that have Requested-By (human-initiated).

    Reads /var/log/apt/history.log and rotated/gzipped versions.
    Only includes packages in the Install: line that are NOT marked automatic
    (i.e., the packages the user directly asked for, not pulled-in dependencies).
    """
    history_dir = Path("/var/log/apt")
    if not history_dir.is_dir():
        return set()
    packages: set[str] = set()
    for log_path in sorted(history_dir.glob("history.log*")):
        try:
            if log_path.suffix == ".gz":
                with gzip.open(log_path, "rt", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            else:
                content = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for entry in content.split("\n\n"):
            # Automated installs (Update Manager, unattended-upgrades) lack Requested-By
            if "Requested-By:" not in entry:
                continue
            m = re.search(r"^Install: (.+)$", entry, re.MULTILINE)
            if not m:
                continue
            # Format: name:arch (version[, automatic])  — skip automatic (dep) packages
            for pkg_m in re.finditer(
                r"([a-z0-9][a-z0-9.+\-]*):(?:amd64|i386|all|arm64|armhf)\s+\(([^)]+)\)",
                m.group(1),
            ):
                if ", automatic" not in pkg_m.group(2):
                    packages.add(pkg_m.group(1))
    return packages


def _initial_install_packages() -> set[str]:
    """Return package names present at OS installation time.

    Reads /var/log/installer/initial-status.gz, which the Ubiquity/Calamares
    installer writes with the package state of the live environment.
    Subtracting this set from apt-mark showmanual gives post-install additions.
    """
    p = Path("/var/log/installer/initial-status.gz")
    if not p.is_file():
        return set()
    try:
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return set()
    return set(re.findall(r"^Package: (\S+)", content, re.MULTILINE))


def user_installable_packages(pkgs: list[str]) -> list[str]:
    """Filter a package list to keep only likely user-installed apps.

    Used on the import side to trim down old manifests that were generated before
    the smarter list_user_requested_packages() was in use.  New manifests are
    already pre-filtered, so this is a no-op for them.
    """
    return [p for p in pkgs if _is_user_package(p)]


def list_user_requested_packages() -> list[str]:
    """Packages installed by the user after initial OS setup.

    Priority order:
    1. apt-mark showmanual minus initial-status.gz, then pattern-filtered
       (most accurate — exact post-install delta, cleaned of automated infra)
    2. apt history Requested-By entries + name-pattern filter
       (fallback when no initial-status.gz is available)
    3. Name-pattern filter alone (last resort)
    """
    manual = set(list_manual_packages())
    if not manual:
        return []

    # Best: subtract base OS from manual set to get post-install additions.
    # Strip :arch suffix (e.g. libc6:i386 → libc6) before comparing so multiarch
    # packages already present at install time aren't falsely included.
    initial = _initial_install_packages()
    if initial:
        user_added = {p for p in manual if p.split(":")[0] not in initial}
        # Also filter automated system packages installed post-setup (kernel headers,
        # system libs pulled in by kernel updates, etc.) — they're not user apps.
        result = [p for p in user_added if _is_user_package(p)]
        if result:
            return sorted(result)

    # Fallback 1: history-based (precise but limited to log rotation window)
    from_history = {p for p in _pkgs_from_apt_history() & manual if _is_user_package(p)}
    # Fallback 2: name-pattern heuristic (catches old installs not in history)
    by_pattern = {p for p in manual if _is_user_package(p)}
    combined = from_history | by_pattern
    return sorted(combined) if combined else sorted(p for p in manual if _is_user_package(p))


def list_manual_packages() -> list[str]:
    """Packages marked manual via apt-mark (user-installed set)."""
    try:
        r = subprocess.run(
            ["apt-mark", "showmanual"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    if r.returncode != 0:
        return []
    out = [line.strip() for line in (r.stdout or "").splitlines() if line.strip()]
    # Filter obvious meta / virtual noise
    skip = {"linux-image-generic", "linux-headers-generic"}
    return [p for p in out if p not in skip]


def read_sources_list() -> str:
    p = Path("/etc/apt/sources.list")
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def list_sources_list_d() -> list[str]:
    d = Path("/etc/apt/sources.list.d")
    if not d.is_dir():
        return []
    names = sorted(f.name for f in d.iterdir() if f.is_file())
    return names


def collect_flatpak_inventory() -> str:
    if not shutil.which("flatpak"):
        return ""
    try:
        r = subprocess.run(
            ["flatpak", "list", "--app"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if r.returncode != 0:
        return (r.stderr or "").strip()
    return (r.stdout or "").strip()


def run_apt_install(packages: list[str], dry_run: bool = False) -> int:
    """Install packages with apt; requires appropriate privileges.

    Runs apt-get update first, then installs all packages as a batch.
    If the batch fails, retries each package individually so the log
    shows exactly which ones couldn't be found.  Returns the number of
    packages that failed (0 = all good).
    """
    if not packages:
        return 0
    if dry_run:
        print(f"[dry-run] would run: apt-get install -y {' '.join(packages)}")
        return 0

    import os

    def _elevate(cmd: list[str]) -> list[str]:
        if os.geteuid() == 0:
            return cmd
        # GUI session: polkit caches auth so subsequent calls don't re-prompt.
        if os.environ.get("DISPLAY") and shutil.which("pkexec"):
            return ["pkexec"] + cmd
        return ["sudo", "-E"] + cmd

    print("\nRunning: apt-get update …")
    subprocess.run(_elevate(["apt-get", "update", "-q"]), check=False)

    # apt-get exits 100 immediately if any single package isn't in the index,
    # installing nothing. Pre-filter with apt-cache (no root needed) so we only
    # pass packages that are actually known to the local package database.
    available: list[str] = []
    unavailable: list[str] = []
    for pkg in packages:
        r = subprocess.run(
            ["apt-cache", "show", "--no-all-versions", pkg],
            capture_output=True, check=False,
        )
        (available if r.returncode == 0 else unavailable).append(pkg)

    if unavailable:
        print(f"\n{len(unavailable)} package(s) not in any configured repo (PPA needed?):")
        for p in unavailable:
            print(f"  {p}")

    if not available:
        return len(unavailable)

    print(f"\nRunning: apt-get install -y ({len(available)} packages) …")
    rc = subprocess.run(
        _elevate(["apt-get", "install", "-y"] + available),
        check=False,
    ).returncode
    if rc != 0:
        print(f"apt-get install exited {rc}")
    return len(unavailable) + (1 if rc != 0 else 0)
