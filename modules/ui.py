"""Interactive UI: Zenity/yad when available and DISPLAY is set; otherwise terminal prompts."""

from __future__ import annotations

import os
from contextlib import contextmanager

from modules import dialog_gui as dg


def use_gui() -> bool:
    if os.environ.get("MINTMIGRATE_USE_CLI", "").strip().lower() in ("1", "true", "yes", "y"):
        return False
    return dg.available()


def _cli_prompt_yes_no(question: str, default: bool = False) -> bool:
    yn = "Y/n" if default else "y/N"
    try:
        s = input(f"{question} [{yn}] ").strip().lower()
    except EOFError:
        return default
    if not s:
        return default
    return s in ("y", "yes")


def _cli_prompt_line(question: str, default: str = "") -> str:
    try:
        if default:
            s = input(f"{question} [{default}] ").strip()
        else:
            s = input(f"{question} ").strip()
    except EOFError:
        return default
    return s if s else default


def _cli_prompt_choice(title: str, options: list[tuple[str, str]]) -> str:
    print()
    print(title)
    for key, desc in options:
        print(f"  {key}) {desc}")
    while True:
        try:
            c = input("\nEnter choice: ").strip()
        except EOFError:
            return options[0][0]
        for key, _ in options:
            if c == key:
                return key
        print(f"Please enter one of: {', '.join(k for k, _ in options)}")


def _cli_optional_features(features: list[tuple[str, str]]) -> set[str]:
    """Multi-select checklist with all items unchecked by default."""
    if not features:
        return set()
    keys = [k for k, _ in features]
    labels = {k: lab for k, lab in features}
    selected: dict[str, bool] = {k: False for k in keys}

    def show() -> None:
        print("\n--- Optional items to include (all unchecked by default) ---")
        for i, k in enumerate(keys, start=1):
            mark = "[x]" if selected[k] else "[ ]"
            print(f"  {i:3} {mark} {labels[k]}")

    show()
    print("  Commands: number toggles | a = all | n = none | Enter = done")
    while True:
        try:
            line = input("\n> ").strip()
        except EOFError:
            break
        if not line:
            break
        low = line.lower()
        if low == "a":
            for k in keys:
                selected[k] = True
        elif low == "n":
            for k in keys:
                selected[k] = False
        elif low.isdigit():
            idx = int(low)
            if 1 <= idx <= len(keys):
                selected[keys[idx - 1]] = not selected[keys[idx - 1]]
        show()

    return {k for k in keys if selected[k]}


def _cli_path_checklist(candidates: list[tuple[str, str]]) -> list[str]:
    if not candidates:
        return []

    rels = [r for r, _ in candidates]
    labels = {r: lab for r, lab in candidates}
    selected: dict[str, bool] = {r: True for r in rels}

    def show() -> None:
        print("\n--- What to copy (all selected by default; toggle with a number) ---")
        for i, r in enumerate(rels, start=1):
            mark = "[x]" if selected[r] else "[ ]"
            print(f"  {i:3} {mark} {labels[r]}")

    show()
    print("  Commands: number toggles | a = all | n = none | Enter = done")
    while True:
        try:
            line = input("\n> ").strip()
        except EOFError:
            break
        if not line:
            break
        low = line.lower()
        if low == "a":
            for r in rels:
                selected[r] = True
        elif low == "n":
            for r in rels:
                selected[r] = False
        elif low.isdigit():
            idx = int(low)
            if 1 <= idx <= len(rels):
                r = rels[idx - 1]
                selected[r] = not selected[r]
        show()

    return [r for r in rels if selected[r]]


def _cli_package_checklist(packages: list[str]) -> list[str]:
    if not packages:
        return []

    state = {p: True for p in packages}
    print("\nPackages from the source machine (all selected by default).")
    print("Toggle with number + Enter, 'a' all, 'n' none, empty line when done.\n")

    def show() -> None:
        for i, p in enumerate(packages, start=1):
            mark = "[x]" if state[p] else "[ ]"
            print(f"  {i:4} {mark} {p}")

    show()
    while True:
        try:
            line = input("\n> ").strip()
        except EOFError:
            break
        if not line:
            break
        lower = line.lower()
        if lower == "a":
            for p in packages:
                state[p] = True
        elif lower == "n":
            for p in packages:
                state[p] = False
        elif lower.isdigit():
            idx = int(lower)
            if 1 <= idx <= len(packages):
                p = packages[idx - 1]
                state[p] = not state[p]
        show()

    return [p for p in packages if state[p]]


def prompt_yes_no(question: str, default: bool = False) -> bool:
    if use_gui():
        r = dg.question("mintmigrate", question, default)
        if r is not None:
            return r
    return _cli_prompt_yes_no(question, default)


def prompt_line(question: str, default: str = "") -> str:
    if use_gui():
        r = dg.entry("mintmigrate", question, default)
        if r is not None:
            return r
    return _cli_prompt_line(question, default)


def prompt_choice(title: str, options: list[tuple[str, str]]) -> str:
    if use_gui():
        r = dg.radiolist_choice(title, options)
        if r is not None:
            return r
    return _cli_prompt_choice(title, options)


def interactive_path_checklist(candidates: list[tuple[str, str]]) -> list[str]:
    if use_gui():
        r = dg.checklist_paths("What to include in the backup", candidates)
        if r is not None:
            return r
    return _cli_path_checklist(candidates)


def interactive_select_packages(packages: list[str]) -> list[str]:
    if use_gui():
        r = dg.checklist_strings(
            "Packages to install",
            packages,
            "From your old PC (toggle off anything you do not want).",
        )
        if r is not None:
            return r
    return _cli_package_checklist(packages)


def prompt_if_interfering() -> bool:
    """Warn if Firefox/Thunderbird/Chromium are running; ask before continuing."""
    from modules.files import find_interfering_processes

    running = find_interfering_processes()
    if not running:
        return True

    labels = [lab for _, lab in running]
    body = (
        "These applications appear to be running:\n\n"
        + "\n".join(f"• {x}" for x in labels)
        + "\n\nCopying while they run can produce inconsistent browser or email profiles.\n"
        "Close them first, then continue."
    )
    if use_gui():
        dg.show_message("warning", "Close apps before copying", body, width=560)
        r = dg.question(
            "Continue anyway?",
            "Only choose Yes if you have closed the apps listed above.",
            default=False,
        )
        if r is not None:
            if r:
                return True
            dg.show_message("info", "Export cancelled", "Close the apps and run mintmigrate again.")
            return False

    print("\n*** The following applications appear to be RUNNING ***")
    for _, label in running:
        print(f"  - {label}")
    print(
        "\nCopying while these run can produce inconsistent browser/email profiles.\n"
        "Close them, then continue."
    )
    choice = input("Type YES if you closed them and want to continue anyway: ").strip()
    if choice == "YES":
        return True
    print("Aborted. Close the apps and re-run export.")
    return False


def prompt_optional_features(features: list[tuple[str, str]]) -> set[str]:
    """
    Show a single checklist for optional export items (all unchecked by default).
    features: list of (key, human_label). Returns set of selected keys.
    """
    if use_gui():
        r = dg.checklist_optional_features("Optional items to include", features)
        if r is not None:
            return set(r)
    return _cli_optional_features(features)


def show_info(title: str, text: str, width: int = 560) -> None:
    if use_gui():
        dg.show_message("info", title, text, width=width)
    else:
        print(f"\n=== {title} ===\n{text}\n")


def show_warning(title: str, text: str, width: int = 560) -> None:
    if use_gui():
        dg.show_message("warning", title, text, width=width)
    else:
        print(f"\n*** {title} ***\n{text}\n")


def show_error(title: str, text: str, width: int = 560) -> None:
    if use_gui():
        dg.show_message("error", title, text, width=width)
    else:
        print(f"\nERROR: {title}\n{text}\n")


def show_text_scroll(title: str, body: str) -> None:
    if use_gui():
        dg.show_text_scroll(title, body)
    else:
        print(f"\n{title}\n{body}\n")


def pick_folder(title: str, default_path: str) -> str:
    """Folder picker or typed path."""
    if use_gui():
        r = dg.pick_directory(title, default_path)
        if r is not None:
            return r
    return _cli_prompt_line("Folder path", default_path)


@contextmanager
def working_pulse(title: str, text: str):
    """Show an indeterminate progress window during long work (GUI mode only)."""
    proc = dg.working_pulsate(title, text) if use_gui() else None
    try:
        yield
    finally:
        dg.stop_working(proc)
