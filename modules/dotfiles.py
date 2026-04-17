"""Home path rules and discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExportOptions:
    include_bash_history: bool = False
    include_steam: bool = False


# Home-relative paths to copy when present (allowlist).
HOME_COPY: tuple[str, ...] = (
    "Documents",
    "Downloads",
    "Pictures",
    "Music",
    "Videos",
    "Desktop",
    "Apps",
    "bin",
    ".bashrc",
    ".bash_aliases",
    ".bash_logout",
    ".profile",
    ".gitconfig",
    ".gtkrc-2.0",
    ".gtkrc-xfce",
    ".gnupg",
    ".mozilla",
    ".thunderbird",
    ".icons",
    ".linuxmint",
    ".pki",
    ".dmrc",
    ".selected_editor",
    ".xinputrc",
)

# Always skipped (never copied) unless explicitly overridden by optional flags where noted.
HOME_SKIP: frozenset[str] = frozenset(
    {
        ".npm",
        ".gradle",
        ".expo",
        ".steam",
        ".steampath",
        ".steampid",
        ".var",
        ".ssh",
        ".app-store",
        ".GA_ClientID",
        ".emulator_console_auth_token",
        ".wget-hsts",
        ".dbus",
        ".Xauthority",
        ".xsession-errors",
        ".xsession-errors.old",
        ".cache",
        ".lesshst",
        ".Private",
        ".sudo_as_admin_successful",
    }
)

CONFIG_COPY: tuple[str, ...] = (
    "autostart",
    "calibre",
    "cinnamon",
    "cinnamon-session",
    "GIMP",
    "google-chrome",
    "microsoft-edge",
    "libreoffice",
    "qBittorrent",
    "rclone",
    "gtk-3.0",
    "celluloid",
    "caja",
    "nemo",
    "xed",
    "xreader",
    "xviewer",
    "pix",
    "QtProject.conf",
    "X-Cinnamon-xdg-terminals.list",
    "xdg-terminals.list",
    "user-dirs.dirs",
    "user-dirs.locale",
    "dconf",
    "ibus",
    "enchant",
    "menus",
    "configstore",
)

CONFIG_SKIP: frozenset[str] = frozenset(
    {
        "google-chrome-for-testing",
        "spotify",
        "cni",
        "goa-1.0",
        "procps",
        "pulse",
        "cinnamon-monitors.xml",
    }
)

LOCAL_SHARE_COPY: tuple[str, ...] = (
    "applications",
    "calibre-ebook.com",
    "cinnamon",
    "nemo",
    "qBittorrent",
    "xreader",
    "icons",
    "keyrings",
    "nano",
    "data",
)

LOCAL_SHARE_SKIP: frozenset[str] = frozenset(
    {
        "icc",
        "vulkan",
        "Steam",
        "flatpak",
        "containers",
        "kotlin",
        "locale",
        "man",
        "inxi",
        "logs",
        "Trash",
        "gvfs-metadata",
        "recently-used.xbel",
        "gegl-0.4",
        "session_migration-cinnamon",
    }
)

SENSITIVE_FLAGS: tuple[tuple[str, str], ...] = (
    (".config/rclone", "rclone remote credentials — treat as sensitive"),
)

# Human-readable labels for checklist (fallback: path itself).
PATH_LABELS: dict[str, str] = {
    "Documents": "Documents",
    "Downloads": "Downloads",
    "Pictures": "Pictures",
    "Music": "Music",
    "Videos": "Videos",
    "Desktop": "Desktop",
    "Apps": "Apps",
    "bin": "bin (personal scripts)",
    ".bashrc": ".bashrc",
    ".bash_aliases": ".bash_aliases (shell aliases)",
    ".bash_logout": ".bash_logout",
    ".profile": ".profile",
    ".bash_history": ".bash_history (shell history)",
    ".gitconfig": ".gitconfig",
    ".gtkrc-2.0": ".gtkrc-2.0",
    ".gtkrc-xfce": ".gtkrc-xfce",
    ".gnupg": "GnuPG (.gnupg/)",
    ".mozilla": "Firefox profiles (.mozilla/)",
    ".thunderbird": "Thunderbird (.thunderbird/)",
    ".icons": "Icons (.icons/)",
    ".linuxmint": "Linux Mint settings (.linuxmint/)",
    ".pki": ".pki (certificates)",
    ".dmrc": ".dmrc",
    ".selected_editor": ".selected_editor",
    ".xinputrc": ".xinputrc",
    ".steam": "Steam (.steam/)",
    ".steampath": "Steam (.steampath)",
    ".steampid": "Steam (.steampid)",
    ".config/autostart": "Autostart apps",
    ".config/calibre": "Calibre",
    ".config/cinnamon": "Cinnamon desktop & shortcuts",
    ".config/cinnamon-session": "Cinnamon session",
    ".config/GIMP": "GIMP",
    ".config/google-chrome": "Google Chrome",
    ".config/microsoft-edge": "Microsoft Edge",
    ".config/libreoffice": "LibreOffice",
    ".config/qBittorrent": "qBittorrent",
    ".config/rclone": "rclone (sensitive credentials)",
    ".config/gtk-3.0": "GTK3 theme/fonts",
    ".config/celluloid": "Celluloid player",
    ".config/caja": "Caja file manager",
    ".config/nemo": "Nemo file manager",
    ".config/xed": "Xed editor",
    ".config/xreader": "Xreader PDF",
    ".config/xviewer": "Xviewer images",
    ".config/pix": "Pix photos",
    ".config/QtProject.conf": "Qt settings",
    ".config/X-Cinnamon-xdg-terminals.list": "Default terminal (Cinnamon)",
    ".config/xdg-terminals.list": "Default terminal",
    ".config/user-dirs.dirs": "XDG user folders",
    ".config/user-dirs.locale": "XDG locale",
    ".config/dconf": "dconf (includes keybindings)",
    ".config/ibus": "IBus input",
    ".config/enchant": "Spell-check dictionaries",
    ".config/menus": "Application menus",
    ".config/configstore": "Node CLI configs",
    ".local/share/applications": "Custom .desktop launchers",
    ".local/share/calibre-ebook.com": "Calibre metadata",
    ".local/share/cinnamon": "Cinnamon applets/extensions",
    ".local/share/nemo": "Nemo data",
    ".local/share/qBittorrent": "qBittorrent data",
    ".local/share/xreader": "Xreader data",
    ".local/share/icons": "User icons",
    ".local/share/keyrings": "GNOME keyrings",
    ".local/share/nano": "nano",
    ".local/share/data": ".local/share/data",
    ".local/share/Steam": "Steam user data (large)",
}


def label_for_rel(rel: str) -> str:
    return PATH_LABELS.get(rel, rel)


def normalize_home_rel(raw: str) -> str | None:
    """Return POSIX relative path from home, or None if invalid (path traversal)."""
    s = raw.strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    parts: list[str] = []
    for p in s.split("/"):
        if p == "" or p == ".":
            continue
        if p == "..":
            return None
        parts.append(p)
    return "/".join(parts)


def is_forbidden_home_rel(rel: str) -> bool:
    """
    True if this home-relative path must never be migrated (brief excludes / unsafe).
    Used to filter custom path entry — excluded paths are never offered as checklist rows.
    """
    r = normalize_home_rel(rel)
    if r is None or r == "":
        return True

    if r == ".Private" or r.startswith(".Private/"):
        return True

    top = r.split("/")[0]
    if top in HOME_SKIP:
        return True

    if r.startswith(".config/"):
        rest = r[len(".config/") :]
        sub = rest.split("/")[0] if rest else ""
        if sub in CONFIG_SKIP:
            return True

    if r.startswith(".local/share/"):
        rest = r[len(".local/share/") :]
        sub = rest.split("/")[0] if rest else ""
        if sub in LOCAL_SHARE_SKIP:
            return True

    # Broad blocks from brief (caches, flatpak app data, etc.)
    blocked_prefixes = (
        ".cache",
        ".dbus",
        ".var",
        ".npm",
        ".gradle",
        ".expo",
        ".app-store",
        ".GA_ClientID",
        ".emulator_console_auth_token",
        ".wget-hsts",
        ".xsession-errors",
        ".lesshst",
    )
    for pref in blocked_prefixes:
        if r == pref or r.startswith(pref + "/"):
            return True

    return False


def validate_custom_path(home: Path, raw: str) -> tuple[str | None, str]:
    """
    Validate user-entered path relative to home. Returns (normalized_rel, "") on success
    or (None, error_message).
    """
    r = normalize_home_rel(raw)
    if r is None:
        return None, "Invalid path (no '..' allowed)."
    if is_forbidden_home_rel(r):
        return None, "That path is not allowed to migrate (excluded for safety)."
    p = home / r
    try:
        if not p.exists():
            return None, f"Path does not exist: ~/{r}"
    except OSError as e:
        return None, str(e)
    return r, ""


def labeled_candidates(home: Path | None, options: ExportOptions) -> list[tuple[str, str]]:
    """Eligible (rel, label) rows for interactive checklist — same policy as scan_paths."""
    scan = scan_paths(home, options)
    return [(rel, label_for_rel(rel)) for rel in scan.include]


def warnings_for_included_paths(include: list[str]) -> list[str]:
    """Sensitive warnings for an arbitrary include list."""
    out: list[str] = []
    for rel, note in SENSITIVE_FLAGS:
        if rel in include or any(i == rel or i.startswith(rel + "/") for i in include):
            out.append(f"{rel}: {note}")
    return out


@dataclass
class PathScanResult:
    """Relative POSIX paths from the user's home directory."""

    include: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_logged: list[str] = field(default_factory=list)


def _exists_rel(home: Path, rel: str) -> bool:
    p = home / rel
    try:
        return p.exists()
    except OSError:
        return False


def scan_paths(home: Path | None, options: ExportOptions) -> PathScanResult:
    """Build the list of home-relative paths to include in the migration bundle."""
    home = home.expanduser().resolve() if home else Path.home()
    out = PathScanResult()

    # ecryptfs sentinel
    private = home / ".Private"
    if private.exists():
        out.warnings.append(
            "Found ~/.Private (ecryptfs). It cannot be copied meaningfully; handle encrypted home separately."
        )

    # Standard home copies (allowlist)
    for rel in HOME_COPY:
        if _exists_rel(home, rel):
            out.include.append(rel)

    if options.include_bash_history and _exists_rel(home, ".bash_history"):
        out.include.append(".bash_history")

    if options.include_steam:
        for rel in (".steam", ".steampath", ".steampid"):
            if _exists_rel(home, rel):
                out.include.append(rel)

    # .config subset
    cfg = home / ".config"
    if cfg.is_dir():
        for name in CONFIG_COPY:
            if name in CONFIG_SKIP:
                continue
            rel = f".config/{name}"
            if _exists_rel(home, rel):
                out.include.append(rel)
        # Log skipped known entries that exist but are excluded by policy
        try:
            for child in cfg.iterdir():
                rel = f".config/{child.name}"
                if child.name in CONFIG_SKIP and child.exists():
                    out.skipped_logged.append(f"{rel} (policy skip)")
        except OSError:
            pass

    # ~/.local/share subset
    lshare = home / ".local/share"
    if lshare.is_dir():
        for name in LOCAL_SHARE_COPY:
            if name in LOCAL_SHARE_SKIP:
                continue
            rel = f".local/share/{name}"
            if _exists_rel(home, rel):
                out.include.append(rel)
        if options.include_steam:
            rel = ".local/share/Steam"
            if _exists_rel(home, rel):
                out.include.append(rel)

    # Sensitive / prominent warnings when included
    for rel, note in SENSITIVE_FLAGS:
        if rel in out.include or any(i == rel or i.startswith(rel + "/") for i in out.include):
            out.warnings.append(f"{rel}: {note}")

    # De-duplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for p in out.include:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    out.include = deduped

    return out
