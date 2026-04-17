"""Read/write manifest.toml (TOML)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _dq(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _str_list(items: list[str]) -> str:
    if not items:
        return "[]"
    inner = ",\n  ".join(_dq(x) for x in items)
    return "[\n  " + inner + ",\n]"


def _ml(s: str) -> str:
    """Multiline TOML string (basic)."""
    safe = s.replace("\r\n", "\n")
    if '"""' in safe:
        safe = safe.replace('"""', "'''")
    return '"""\n' + safe + '\n"""'


def render_manifest(data: dict[str, Any]) -> str:
    """Emit TOML for the mintmigrate manifest shape (no generic serializer)."""
    lines: list[str] = []
    meta = data["meta"]
    lines.append("[meta]")
    lines.append(f"schema_version = {int(meta['schema_version'])}")
    lines.append(f"created_at = {_dq(meta['created_at'])}")
    lines.append(f"source_hostname = {_dq(meta['source_hostname'])}")
    lines.append(f"source_user = {_dq(meta['source_user'])}")
    lines.append(f"source_uid = {int(meta['source_uid'])}")
    lines.append(f"source_gid = {int(meta['source_gid'])}")
    lines.append("")

    pkgs = (data.get("packages") or {}).get("manual") or []
    lines.append("[packages]")
    lines.append(f"manual = {_str_list(list(pkgs))}")
    lines.append("")

    apt = data.get("apt_sources") or {}
    lines.append("[apt_sources]")
    lines.append(f"sources_list = {_ml(str(apt.get('sources_list', '')))}")
    fn = apt.get("sources_list_d_filenames") or []
    lines.append(f"sources_list_d_filenames = {_str_list(list(fn))}")
    lines.append("")

    flat = (data.get("flatpak") or {}).get("inventory") or ""
    lines.append("[flatpak]")
    lines.append(f"inventory = {_ml(str(flat))}")
    lines.append("")

    paths = (data.get("paths") or {}).get("include") or []
    lines.append("[paths]")
    lines.append(f"include = {_str_list([str(x) for x in paths])}")
    lines.append("")

    eo = data.get("export_options") or {}

    def _tf(key: str) -> str:
        return "true" if bool(eo.get(key)) else "false"

    lines.append("[export_options]")
    lines.append(f"include_bash_history = {_tf('include_bash_history')}")
    lines.append(f"include_citrix = {_tf('include_citrix')}")
    lines.append(f"include_steam = {_tf('include_steam')}")
    lines.append(f"include_evolution = {_tf('include_evolution')}")
    lines.append(f"include_ice = {_tf('include_ice')}")
    lines.append("")
    return "\n".join(lines)


def load_manifest(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return tomllib.loads(raw.decode("utf-8"))


def save_manifest(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_manifest(data), encoding="utf-8")
