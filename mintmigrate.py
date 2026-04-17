#!/usr/bin/env python3
"""mintmigrate — Linux Mint one-time migration CLI (export / import)."""

from __future__ import annotations

import argparse
import getpass
import os
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_LOG_PATH = Path(__file__).resolve().parent / "mintmigrate.log"


class _LogTee:
    """Write to both the original stream and a log file so output is never lost."""

    def __init__(self, stream, log_file):
        self._s = stream
        self._f = log_file

    def write(self, data: str) -> int:
        try:
            self._s.write(data)
        except Exception:
            pass
        self._f.write(data)
        self._f.flush()
        return len(data)

    def flush(self) -> None:
        try:
            self._s.flush()
        except Exception:
            pass
        self._f.flush()

    def fileno(self) -> int:
        # Needed so subprocesses can inherit the underlying fd (e.g. ssh host-key prompts)
        return self._s.fileno()


def _setup_log() -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)  # no-op; parent is the project dir
    lf = open(_LOG_PATH, "w", buffering=1, encoding="utf-8", errors="replace")
    sys.stdout = _LogTee(sys.stdout, lf)
    sys.stderr = _LogTee(sys.stderr, lf)

from modules.browser import BROWSER_NOTES
from modules.crontab import export_crontab, import_crontab
from modules.dotfiles import (
    ExportOptions,
    labeled_candidates,
    scan_paths,
    validate_custom_path,
    warnings_for_included_paths,
)
from modules.files import (
    rsync_ssh_push_path,
    rsync_ssh_push_project,
    run_ssh_copy_id,
    run_ssh_copy_id_with_password,
    ssh_connection_ok,
    ssh_mkdir_p,
)
from modules.manifest_io import load_manifest, save_manifest
from modules.packages import (
    collect_flatpak_inventory,
    list_sources_list_d,
    list_user_requested_packages,
    read_sources_list,
    run_apt_install,
    user_installable_packages,
)
from modules.permissions import fix_sensitive_permissions, recursive_chown_to_current_user
from modules.ui import (
    interactive_path_checklist,
    interactive_select_packages,
    pick_folder,
    prompt_choice,
    prompt_if_interfering,
    prompt_line,
    prompt_optional_features,
    prompt_yes_no,
    show_error,
    show_info,
    show_text_scroll,
    show_warning,
    working_pulse,
)


_OPTIONAL_FEATURES: list[tuple[str, str]] = [
    ("bash_history", "Shell history (.bash_history)"),
    ("steam", "Steam folders (can be large)"),
]


@dataclass
class ExportParams:
    manifest_dir: Path   # where to save manifest.toml locally (default: ~/.mintmigrate/)
    opts: ExportOptions
    include_paths: list[str]
    remote: str          # user@host or empty string
    dry_run: bool


@dataclass
class ImportParams:
    """Directory containing manifest.toml (default: ~/.mintmigrate/). Files already live in $HOME."""

    bundle: Path
    dry_run: bool
    non_interactive: bool
    fix_ownership: bool
    force_identity: bool = False


def _prompt_yes_no(question: str, default: bool = False) -> bool:
    return prompt_yes_no(question, default)


def run_export(params: ExportParams) -> int:
    manifest_dir = params.manifest_dir.expanduser().resolve()
    manifest_dir.mkdir(parents=True, exist_ok=True)
    home = Path.home()

    scan = scan_paths(home, params.opts)
    for s in scan.skipped_logged[:20]:
        print(f"(policy skip on source) {s}")
    if len(scan.skipped_logged) > 20:
        print(f"... and {len(scan.skipped_logged) - 20} more under ~/.config")

    if (home / ".Private").exists():
        print(
            "\n*** Note: ~/.Private (ecryptfs) is present. Encrypted home data is not copied; handle that separately."
        )

    for w in warnings_for_included_paths(params.include_paths):
        print(f"*** Warning: {w}")

    pkgs = list_user_requested_packages()
    apt_main = read_sources_list()
    apt_d = list_sources_list_d()
    flatpak_txt = collect_flatpak_inventory()

    meta = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_hostname": socket.gethostname(),
        "source_user": getpass.getuser(),
        "source_uid": os.getuid(),
        "source_gid": os.getgid(),
    }
    crontab_content = export_crontab()
    if crontab_content:
        print("Crontab exported.")
    manifest: dict = {
        "meta": meta,
        "packages": {"manual": pkgs},
        "apt_sources": {
            "sources_list": apt_main,
            "sources_list_d_filenames": apt_d,
        },
        "flatpak": {"inventory": flatpak_txt},
        "paths": {"include": [p.replace("\\", "/") for p in params.include_paths]},
        "export_options": {
            "include_bash_history": params.opts.include_bash_history,
            "include_steam": params.opts.include_steam,
        },
        "crontab": {"user_crontab": crontab_content or ""},
    }

    mpath = manifest_dir / "manifest.toml"
    save_manifest(mpath, manifest)
    print(f"\nSaved migration record: {mpath}")
    print(f"Paths to transfer: {len(params.include_paths)} items")

    if params.dry_run:
        print("\n[dry-run] skipping file transfer.")
        return 0

    code = 0
    if params.remote.strip():
        remote = params.remote.strip()
        print(f"\nSending files directly to {remote} …")

        # Create .mintmigrate/ on remote to receive the manifest
        rc = ssh_mkdir_p(remote, [".mintmigrate"], dry_run=False)
        if rc != 0:
            print(f"Warning: mkdir exit {rc} on remote")

        # Rsync each selected path directly to its home-relative location on remote.
        # rsync_ssh_push_path uses --mkpath so nested dirs (.config/foo) are created automatically.
        with working_pulse("mintmigrate", "Sending files to the new computer (network)…"):
            for rel in params.include_paths:
                local_path = home / rel
                rc = rsync_ssh_push_path(local_path, remote, rel, dry_run=False)
                if rc != 0:
                    code = rc
                    print(f"Warning: rsync exit {rc} for {rel}")

        # Rsync manifest to remote ~/.mintmigrate/
        rc = rsync_ssh_push_path(mpath, remote, ".mintmigrate/manifest.toml", dry_run=False)
        if rc != 0:
            code = rc
            print(f"Warning: rsync exit {rc} for manifest")

        # Always send the mintmigrate project itself so the new PC can run the setup step
        # without any manual installation.
        project_dir = Path(__file__).resolve().parent
        print("\nSending mintmigrate tool to the new computer…")
        rc = rsync_ssh_push_project(project_dir, remote, dry_run=False)
        if rc != 0:
            code = rc
            print(f"Warning: could not send mintmigrate project ({rc})")
    else:
        print(f"\nNo remote specified — migration record saved at {mpath}.")

    return code


def run_import(params: ImportParams) -> int:
    bundle = params.bundle.expanduser().resolve()
    mf = bundle / "manifest.toml"
    if not mf.is_file():
        show_error(
            "Migration record not found",
            f"No manifest.toml found at:\n{mf}\n\nMake sure you ran this tool on your old PC first and sent your files over the network.",
            width=560,
        )
        return 1

    data = load_manifest(mf)
    meta = data.get("meta") or {}
    src_user = (meta.get("source_user") or "").strip()
    cur_user = getpass.getuser()

    print("\n--- Migration record ---")
    print(f"Created: {meta.get('created_at', '?')}")
    print(f"From computer: {meta.get('source_hostname', '?')}")
    print(f"Original user: {src_user or '?'} (uid {meta.get('source_uid', '?')})")
    print(f"This login: {cur_user} (uid {os.getuid()})")

    if src_user and src_user != cur_user and not params.force_identity:
        show_error(
            "Wrong user account",
            (
                f"This migration was made for user '{src_user}', but you are logged in as '{cur_user}'.\n\n"
                "Create or switch to that account on this PC (same username as on the old computer), then run setup again.\n\n"
                "(Advanced: mintmigrate import --force-identity — not recommended.)"
            ),
            width=560,
        )
        return 1

    suid = meta.get("source_uid")
    uid_mismatch = suid is not None and int(suid) != os.getuid()
    if uid_mismatch:
        print(
            f"\n*** User ID differs: source uid {suid} vs your uid {os.getuid()}.\n"
            "Files may show wrong ownership until fixed (see below)."
        )

    all_pkgs = (data.get("packages") or {}).get("manual") or []
    # Old manifests contain the full apt-mark showmanual list (~1000 packages).
    # Filter to user-installed apps only; new manifests are already pre-filtered.
    pkgs = user_installable_packages(all_pkgs) or all_pkgs

    print(f"\nPackages to install: {len(pkgs)}" + (
        f"  (filtered from {len(all_pkgs)} in manifest)" if len(pkgs) < len(all_pkgs) else ""
    ))
    print(f"\nFiles were sent directly to: {Path.home()}")

    if not params.non_interactive:
        if not _prompt_yes_no("Proceed with package selection and final setup?", default=False):
            show_info("Cancelled", "Setup was cancelled.")
            return 0

    if params.non_interactive:
        selected = list(pkgs)
    else:
        selected = interactive_select_packages(pkgs)
    print(f"\nWill install {len(selected)} packages via apt.")

    fix_own = params.fix_ownership
    if uid_mismatch and not params.dry_run and not fix_own and not params.non_interactive:
        fix_own = _prompt_yes_no(
            "\nFix ownership of all files in your home folder with sudo? (only if user IDs differ)",
            default=False,
        )

    if params.dry_run:
        print("[dry-run] skipping apt and permission fixes.")
        run_apt_install(selected, dry_run=True)
        return 0

    if selected:
        with working_pulse("mintmigrate", "Installing packages (apt). This can take a while…"):
            n_failed = run_apt_install(selected, dry_run=False)
        if n_failed:
            print(f"\n{n_failed} package(s) failed to install — see log for details.")

    if fix_own:
        recursive_chown_to_current_user(Path.home())
    elif uid_mismatch:
        print("\nIf files have wrong ownership, run:")
        print('  sudo chown -R "$USER:$GROUP" "$HOME"')
        print("Or: mintmigrate import --fix-ownership …")

    fix_sensitive_permissions(Path.home())

    crontab_content = (data.get("crontab") or {}).get("user_crontab", "").strip()
    if crontab_content:
        if params.dry_run:
            print("[dry-run] would restore crontab.")
        elif params.non_interactive or _prompt_yes_no("Restore crontab from old PC?", default=True):
            rc_cron = import_crontab(crontab_content)
            if rc_cron == 0:
                print("Crontab restored.")
            else:
                print("Warning: failed to restore crontab — check that 'crontab' is installed.")

    after = """After migration — checklist:

• Remove SSH server (no longer needed):
    sudo apt remove --purge openssh-server
• Re-authenticate rclone: rclone config reconnect <remote>:
• Cloud sync: let folders re-sync on the new machine
• Steam: reinstall as needed
• GPG: chmod 700 ~/.gnupg
• Firefox / Thunderbird: open and check
• Online accounts / cloud services: sign in again if needed
• ecryptfs: handle separately if you use it
• Note: if the mintmigrate launcher failed on this PC, first run:
    sudo apt install python3-venv"""
    if params.non_interactive:
        print("\n--- After migration ---")
        for line in after.splitlines():
            print(line)
    else:
        show_text_scroll("After migration", after)
    return 0


def _wizard_custom_paths(home: Path, include_paths: list[str]) -> list[str]:
    seen = set(include_paths)
    out = list(include_paths)
    while prompt_yes_no("Add another folder from your home to include?", default=False):
        raw = prompt_line("Path under your home (example: Projects/Code)")
        rel, err = validate_custom_path(home, raw)
        if err:
            show_warning("Cannot add that path", err, width=480)
            continue
        assert rel is not None
        if rel in seen:
            show_info("Already included", f"That folder is already in the list:\n~/{rel}")
            continue
        seen.add(rel)
        out.append(rel)
        show_info("Added", f"~/{rel}")
    return out


def wizard_export() -> int:
    show_info(
        "Old computer — send your files",
        "Use the same Wi‑Fi as the new PC. On the new machine, enable remote login (SSH) if you send over the network.\n\n"
        + BROWSER_NOTES,
        width=560,
    )

    selected_opts = prompt_optional_features(_OPTIONAL_FEATURES)
    opts = ExportOptions(
        include_bash_history="bash_history" in selected_opts,
        include_steam="steam" in selected_opts,
    )

    home = Path.home()
    candidates = labeled_candidates(home, opts)
    if not candidates:
        show_error(
            "Nothing to copy",
            "No eligible folders were found (nothing matched the migration rules).",
            width=480,
        )
        return 1

    chosen = interactive_path_checklist(candidates)
    if not chosen:
        show_info("Cancelled", "Nothing was selected to copy.")
        return 1

    include_paths = _wizard_custom_paths(home, chosen)

    if not prompt_if_interfering():
        return 1

    show_info(
        "New computer address",
        "On the new PC, find its address: Settings → Network, or run hostname -I in a terminal.\n\n"
        f"Format: username@address   Example: {getpass.getuser()}@192.168.1.50",
        width=560,
    )
    remote = prompt_line("Username @ address for the new computer").strip()
    if not remote:
        show_info(
            "No address entered",
            "Nothing will be transferred. Enter the new computer's address to proceed.",
            width=480,
        )
        return 1

    ok, msg = ssh_connection_ok(remote)
    if not ok:
        lower_msg = msg.lower()
        if "permission denied" in lower_msg or "publickey" in lower_msg:
            # Server is reachable but key auth isn't set up — normal on a fresh install.
            from modules import dialog_gui as dg
            from modules.ui import use_gui
            if use_gui():
                password = dg.password_entry(
                    "Set up key login",
                    f"The new PC is reachable but key login isn't set up yet — this is normal on a fresh install.\n\n"
                    f"Enter the password for {remote}:\n(You'll only need to do this once.)",
                )
                if password:
                    rc_key, key_err = run_ssh_copy_id_with_password(remote, password)
                    if rc_key != 0:
                        show_error(
                            "Key setup failed",
                            f"Could not copy your SSH key to {remote}.\n\n"
                            f"{key_err or 'Unknown error — check the terminal for details.'}\n\n"
                            "Try running mintmigrate again and re-enter the password.",
                            width=560,
                        )
                        return 1
                else:
                    show_info("Cancelled", "Key setup skipped. Fix the connection and run mintmigrate again.")
                    return 1
            else:
                print(
                    "\nKey-based login not set up. Enter the new PC's password when prompted.\n"
                )
                run_ssh_copy_id(remote)
            ok, msg = ssh_connection_ok(remote)

        if not ok:
            show_warning(
                "Could not connect via SSH",
                f"{msg}\n\n"
                "Checklist:\n"
                "• New PC is on and on the same Wi‑Fi\n"
                "• Install OpenSSH server on the new PC: sudo apt install openssh-server\n"
                f"• From this PC, try: ssh {remote}\n"
                "• Accept the host key the first time if asked\n\n"
                "Fix the connection issue and run mintmigrate again.",
                width=620,
            )
            return 1

    params = ExportParams(
        manifest_dir=Path.home() / ".mintmigrate",
        opts=opts,
        include_paths=include_paths,
        remote=remote,
        dry_run=False,
    )
    rc = run_export(params)
    if rc == 0:
        show_info(
            "Transfer complete",
            f"Your files have been sent to {remote}.\n\n"
            "On the new computer:\n"
            "  1. Open a terminal\n"
            f"  2. Run:  ~/mintmigrate/launch_mintmigrate.sh\n"
            "  3. Choose 'This is my NEW computer'\n\n"
            "If the launcher fails, first install the required package:\n"
            "  sudo apt install python3-venv",
            width=520,
        )
    else:
        show_error(
            "Transfer finished with errors",
            f"Some files could not be sent.\n\n"
            f"Full log saved to:\n{_LOG_PATH}\n\n"
            "Partial transfers are safe to re-run — rsync will skip files already sent.",
            width=560,
        )
    return rc


def wizard_import() -> int:
    default_bundle = str(Path.home() / ".mintmigrate")
    show_info(
        "New computer — complete your setup",
        "Your files should have already been sent from your old PC directly into your home folder.\n\n"
        "This step will install your packages and apply the finishing touches.\n\n"
        "Use the same username as on your old PC.",
        width=560,
    )

    # Auto-detect manifest; let user override if not found
    default_manifest = Path.home() / ".mintmigrate" / "manifest.toml"
    if not default_manifest.is_file():
        show_warning(
            "Migration record not found",
            f"No migration record found at {default_manifest}.\n\n"
            "If you haven't sent files yet, go back to your old PC and run mintmigrate there first.\n\n"
            "If the record is somewhere else, you can select its folder below.",
            width=560,
        )
        b = pick_folder("Select the folder containing manifest.toml", default_bundle)
    else:
        b = default_bundle

    bundle = Path(b).expanduser().resolve()

    params = ImportParams(
        bundle=bundle,
        dry_run=False,
        non_interactive=False,
        fix_ownership=False,
        force_identity=False,
    )
    return run_import(params)


def interactive_main() -> int:
    key = prompt_choice(
        "mintmigrate — which computer is this?",
        [
            ("1", "This is my OLD computer (send my files)"),
            ("2", "This is my NEW computer (receive my files)"),
        ],
    )
    if key == "1":
        return wizard_export()
    return wizard_import()


def cmd_export(args: argparse.Namespace) -> int:
    home = Path.home()
    if getattr(args, "non_interactive", False):
        opts = ExportOptions()
    else:
        selected_opts = prompt_optional_features(_OPTIONAL_FEATURES)
        opts = ExportOptions(
            include_bash_history="bash_history" in selected_opts,
            include_steam="steam" in selected_opts,
        )

    if not args.skip_preflight and not prompt_if_interfering():
        return 1

    include_paths = scan_paths(home, opts).include

    params = ExportParams(
        manifest_dir=Path(args.manifest_dir).expanduser().resolve(),
        opts=opts,
        include_paths=include_paths,
        remote=(args.remote or "").strip(),
        dry_run=args.dry_run,
    )
    return run_export(params)


def cmd_import(args: argparse.Namespace) -> int:
    params = ImportParams(
        bundle=Path(args.bundle).expanduser().resolve(),
        dry_run=args.dry_run,
        non_interactive=args.non_interactive,
        fix_ownership=args.fix_ownership,
        force_identity=getattr(args, "force_identity", False),
    )
    return run_import(params)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mintmigrate",
        description="Linux Mint profile migration. Run with no arguments for the guided wizard.",
    )
    sub = p.add_subparsers(dest="command", required=False)

    e = sub.add_parser("export", help="Advanced: export from command line (see also: mintmigrate with no args)")
    e.add_argument(
        "--manifest-dir",
        "-o",
        default=str(Path.home() / ".mintmigrate"),
        help="Directory to save manifest.toml locally (default: ~/.mintmigrate/)",
    )
    e.add_argument(
        "--remote",
        "-r",
        default="",
        help="user@host to rsync files to (e.g. user@192.168.1.50); files go directly into remote ~/",
    )
    e.add_argument("--dry-run", action="store_true", help="Write manifest only; no file copy or push")
    e.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Do not check for running Firefox/Thunderbird/Chromium (not recommended)",
    )
    e.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip optional prompts (Steam, bash history, etc. — all off)",
    )

    i = sub.add_parser("import", help="Advanced: import from command line")
    i.add_argument(
        "--bundle",
        "-b",
        default=str(Path.home() / ".mintmigrate"),
        help="Directory containing manifest.toml (default: ~/.mintmigrate/)",
    )
    i.add_argument(
        "--fix-ownership",
        action="store_true",
        help="Run sudo chown -R $USER:$GROUP $HOME after merge (use if UIDs differ)",
    )
    i.add_argument("--dry-run", action="store_true", help="Show apt and rsync commands only")
    i.add_argument(
        "--non-interactive",
        action="store_true",
        help="Install all listed packages without interactive toggles; skip confirmation",
    )
    i.add_argument(
        "--force-identity",
        action="store_true",
        help="Allow import even if login name differs from the backup (dangerous — wrong ownership risk)",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    _setup_log()
    print(f"mintmigrate starting — log: {_LOG_PATH}")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return interactive_main()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    if args.command == "export":
        return cmd_export(args)
    if args.command == "import":
        return cmd_import(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
