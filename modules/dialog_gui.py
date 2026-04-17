"""Zenity and optional yad dialogs for the migration wizard (no shell interpolation)."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Literal

Backend = Literal["zenity", "yad"]


def _backend() -> Backend | None:
    """Prefer zenity (standard on Linux Mint); yad is an optional enhancement."""
    if shutil.which("zenity"):
        return "zenity"
    if shutil.which("yad"):
        return "yad"
    return None


def available() -> bool:
    return _backend() is not None and bool(os.environ.get("DISPLAY", ""))


def _run(argv: list[str]) -> tuple[int, str]:
    r = subprocess.run(argv, capture_output=True, text=True, check=False)
    out = (r.stdout or "").strip()
    return r.returncode, out


def show_message(kind: Literal["info", "warning", "error"], title: str, text: str, width: int = 520) -> None:
    b = _backend()
    if b == "zenity":
        flag = {"info": "--info", "warning": "--warning", "error": "--error"}[kind]
        _run(["zenity", flag, "--title", title, "--width", str(width), "--text", text])
        return
    if b == "yad":
        img = {"info": "dialog-information", "warning": "dialog-warning", "error": "dialog-error"}[kind]
        _run(
            [
                "yad",
                "--title",
                title,
                "--text",
                text,
                "--image",
                img,
                "--width",
                str(width),
                "--center",
                "--button=OK:0",
            ]
        )
        return
    print(f"\n{title}\n{text}\n")


def show_text_scroll(title: str, body: str, width: int = 560, height: int = 420) -> None:
    b = _backend()
    if b == "zenity":
        subprocess.run(
            ["zenity", "--text-info", "--title", title, "--width", str(width), "--height", str(height)],
            input=body,
            text=True,
            check=False,
        )
        return
    if b == "yad":
        p = subprocess.Popen(
            ["yad", "--text-info", "--title", title, "--width", str(width), "--height", str(height), "--wrap"],
            stdin=subprocess.PIPE,
            text=True,
        )
        if p.stdin:
            p.stdin.write(body)
            p.stdin.close()
        p.wait()
        return
    print(f"\n{title}\n{body}\n")


def question(title: str, text: str, default: bool = False) -> bool | None:
    """
    OK/Yes → True, Cancel/No → False.
    Returns None if no GUI backend (caller uses CLI).
    """
    b = _backend()
    if b == "zenity":
        argv = ["zenity", "--question", "--title", title, "--text", text, "--width=480"]
        if not default:
            argv.append("--default-cancel")
        code, _ = _run(argv)
        if code == 0:
            return True
        if code == 1:
            return False
        return None
    if b == "yad":
        argv = [
            "yad",
            "--question",
            "--title",
            title,
            "--text",
            text,
            "--center",
            "--button=Yes:0",
            "--button=No:1",
        ]
        code, _ = _run(argv)
        if code == 0:
            return True
        if code in (1, 252):
            return False
        return None
    return None


def password_entry(title: str, text: str) -> str | None:
    """Show a password-masked entry dialog. Returns the entered password or None if cancelled."""
    b = _backend()
    if b == "zenity":
        code, out = _run(
            ["zenity", "--entry", "--hide-text", "--title", title, "--text", text, "--width=480"]
        )
        if code != 0:
            return None
        return out
    if b == "yad":
        code, out = _run(
            ["yad", "--entry", "--hide-text", "--title", title, "--text", text, "--width=480"]
        )
        if code != 0:
            return None
        return out
    return None


def entry(title: str, text: str, default: str = "") -> str | None:
    b = _backend()
    if b == "zenity":
        code, out = _run(
            ["zenity", "--entry", "--title", title, "--text", text, "--entry-text", default, "--width=560"]
        )
        if code != 0:
            return None
        return out
    if b == "yad":
        code, out = _run(
            [
                "yad",
                "--entry",
                "--title",
                title,
                "--text",
                text,
                "--entry-text",
                default,
                "--width=560",
            ]
        )
        if code != 0:
            return None
        return out
    return None


def pick_directory(title: str, default_path: str | None = None) -> str | None:
    b = _backend()
    if b == "zenity":
        argv = ["zenity", "--file-selection", "--directory", "--title", title, "--width=720", "--height=520"]
        if default_path:
            argv.extend(["--filename", default_path])
        code, out = _run(argv)
        if code != 0:
            return None
        return out.strip() or None
    if b == "yad":
        argv = ["yad", "--file", "--directory", "--title", title, "--width=720", "--height=520"]
        if default_path:
            argv.extend(["--filename", default_path])
        code, out = _run(argv)
        if code != 0:
            return None
        return out.strip() or None
    return None


def radiolist_choice(title: str, options: list[tuple[str, str]], column_label: str = "Choice") -> str | None:
    """
    options: (return_key, visible_label). First option is selected by default.
    Returns chosen key or None on cancel.
    """
    if not options:
        return None
    b = _backend()
    if b == "zenity":
        argv = [
            "zenity",
            "--list",
            "--radiolist",
            "--title",
            title,
            "--width=600",
            "--height=360",
            "--column",
            "",
            "--column",
            column_label,
        ]
        for i, (_k, desc) in enumerate(options):
            argv.append("TRUE" if i == 0 else "FALSE")
            argv.append(desc)
        code, out = _run(argv)
        if code != 0 or not out:
            return None
        line = out.split("\n", 1)[0].strip()
        for k, desc in options:
            if desc == line:
                return k
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if desc in parts:
                    return k
        return None
    if b == "yad":
        argv = ["yad", "--list", "--radiolist", "--title", title, "--column", column_label, "--width=600", "--height=360"]
        for i, (_k, desc) in enumerate(options):
            argv.append("TRUE" if i == 0 else "FALSE")
            argv.append(desc)
        code, out = _run(argv)
        if code != 0 or not out:
            return None
        line = out.split("\n", 1)[0].strip()
        for k, desc in options:
            if desc == line or line.endswith(desc):
                return k
        return options[0][0]
    return None


def checklist_paths(title: str, candidates: list[tuple[str, str]]) -> list[str] | None:
    """
    candidates: (rel_path, human_label). All checked by default.
    Returns list of rel paths, [] if none checked, None if dialog cancelled.
    """
    if not candidates:
        return []
    b = _backend()
    if b == "zenity":
        argv = [
            "zenity",
            "--list",
            "--checklist",
            "--title",
            title,
            "--width=720",
            "--height=520",
            "--hide-column=2",
            "--print-column=2",
            "--column",
            "",
            "--column",
            "Path",
            "--column",
            "Folder",
        ]
        for rel, lab in candidates:
            argv.extend(["TRUE", rel, lab])
        code, out = _run(argv)
        if code != 0:
            return None
        if not out.strip():
            return []
        # zenity --print-column joins selected rows with | on a single line
        return [item.strip() for item in out.split("|") if item.strip()]
    if b == "yad":
        argv = [
            "yad",
            "--list",
            "--checklist",
            "--separator=|",
            "--title",
            title,
            "--width=720",
            "--height=520",
            "--column",
            "Pick",
            "--column",
            "Path:HD",
            "--column",
            "Folder",
        ]
        for rel, lab in candidates:
            argv.extend(["TRUE", rel.replace("|", "\\|"), lab.replace("|", "\\|")])
        code, out = _run(argv)
        if code != 0:
            return None
        if not out.strip():
            return []
        selected: list[str] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                selected.append(parts[1].strip().replace("\\|", "|"))
            else:
                selected.append(line)
        return selected
    return None


def checklist_strings(title: str, items: list[str], subtitle: str = "") -> list[str] | None:
    """Multiselect (e.g. package names). All checked by default."""
    if not items:
        return []
    full_title = title if not subtitle else f"{title}\n{subtitle}"
    b = _backend()
    if b == "zenity":
        argv = [
            "zenity",
            "--list",
            "--checklist",
            "--title",
            full_title[:200],
            "--width=640",
            "--height=560",
            "--column",
            "",
            "--column",
            "Package",
        ]
        for p in items:
            argv.extend(["TRUE", p])
        code, out = _run(argv)
        if code != 0:
            return None
        if not out.strip():
            return []
        # zenity --checklist joins all selected values with | on a single line
        return [item.strip() for item in out.split("|") if item.strip()]
    if b == "yad":
        argv = [
            "yad",
            "--list",
            "--checklist",
            "--separator=|",
            "--title",
            full_title[:120],
            "--width=640",
            "--height=560",
            "--column",
            "Pick",
            "--column",
            "Package",
        ]
        for p in items:
            argv.extend(["TRUE", p.replace("|", "\\|")])
        code, out = _run(argv)
        if code != 0:
            return None
        if not out.strip():
            return []
        rows: list[str] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                rows.append(line.split("|", 1)[-1].strip().replace("\\|", "|"))
            else:
                rows.append(line)
        return rows
    return None


def checklist_optional_features(title: str, features: list[tuple[str, str]]) -> list[str] | None:
    """
    features: (key, human_label), all unchecked by default.
    Returns list of selected keys, [] if none selected, None if cancelled.
    """
    if not features:
        return []
    b = _backend()
    if b == "zenity":
        argv = [
            "zenity",
            "--list",
            "--checklist",
            "--title",
            title,
            "--width=640",
            "--height=400",
            "--hide-column=2",
            "--print-column=2",
            "--column",
            "",
            "--column",
            "Key",
            "--column",
            "Option",
        ]
        for key, label in features:
            argv.extend(["FALSE", key, label])
        code, out = _run(argv)
        if code != 0:
            return None
        if not out.strip():
            return []
        return [item.strip() for item in out.split("|") if item.strip()]
    if b == "yad":
        argv = [
            "yad",
            "--list",
            "--checklist",
            "--separator=|",
            "--title",
            title,
            "--width=640",
            "--height=400",
            "--column",
            "Pick",
            "--column",
            "Key:HD",
            "--column",
            "Option",
        ]
        for key, label in features:
            argv.extend(["FALSE", key.replace("|", "\\|"), label.replace("|", "\\|")])
        code, out = _run(argv)
        if code != 0:
            return None
        if not out.strip():
            return []
        selected: list[str] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                selected.append(parts[1].strip().replace("\\|", "|"))
        return selected
    return None


def working_pulsate(title: str, text: str) -> subprocess.Popen | None:
    """Indeterminate progress; caller must call stop_working() when finished.
    Write '# message\\n' to proc.stdin to update the label.
    """
    b = _backend()
    if b == "zenity":
        return subprocess.Popen(
            ["zenity", "--progress", "--pulsate", "--auto-kill", "--title", title, "--text", text, "--no-cancel"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    if b == "yad":
        return subprocess.Popen(
            [
                "yad",
                "--progress",
                "--pulsate",
                "--auto-kill",
                "--title",
                title,
                "--text",
                text,
                "--no-buttons",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    return None


def update_progress_text(proc: subprocess.Popen | None, message: str) -> None:
    """Update the label in a running pulsate progress dialog."""
    if proc is None or proc.stdin is None:
        return
    try:
        proc.stdin.write(f"# {message}\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError):
        pass


def stop_working(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
