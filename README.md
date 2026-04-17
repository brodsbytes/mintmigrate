# mintmigrate

**One-time Linux Mint migration helper.** Copy your profile to a new PC over SSH, reinstall selected packages, restore your crontab, fix GPG permissions, and get a post-migration checklist — all through a guided GUI wizard.

## Before you start

Two things to set up on your **new PC** before running the tool:

**1. Install OpenSSH server** so the old PC can connect:
```bash
sudo apt install openssh-server
```

**2. Create the same username** as your old PC. The tool refuses to run the new-PC setup step if you are logged in as a different user. If the numeric user ID (UID) differs, the tool warns you and can optionally run a `chown` to fix permissions.

## Running the tool

Run the launcher on each PC — it sets up the virtual environment automatically on first run:

```bash
./launch_mintmigrate.sh
```

**On your old PC:**
1. Choose **"This is my OLD computer"**.
2. Choose any optional items to include (shell history, Steam, etc.) from a checklist.
3. Pick which folders to copy (caches and large/excluded paths are never listed). You can also add custom folders.
4. Enter your new PC's `username@address` (e.g. `alice@192.168.1.50`).
5. The tool tests the SSH connection, then sends your files **directly into `~/`** on the new PC over the network.
6. A migration record (`manifest.toml`) is saved to `~/.mintmigrate/` on both computers.

**On your new PC:**
1. Choose **"This is my NEW computer"**.
2. The tool finds the migration record automatically at `~/.mintmigrate/manifest.toml`.
3. Select which packages to reinstall (everything is pre-selected; untick what you don't want).
4. Packages are installed via `apt`, your crontab is restored, and GPG permissions are fixed automatically.
5. A post-migration checklist is shown.

> This second step is optional — skip it if you only want to transfer files.

If the SSH connection test fails, a checklist of common causes is shown (same network, host key accepted, etc.). Fix the issue and run mintmigrate again.

## What gets migrated

The checklist is built from your home directory at runtime — only paths that actually exist are shown.

**Always included (if present):**
- Standard user folders: `Documents`, `Downloads`, `Pictures`, `Music`, `Videos`, `Desktop`
- Shell config: `.bashrc`, `.bash_aliases`, `.bash_logout`, `.profile`
- Git, GTK, and editor settings
- Firefox (`.mozilla/`), Thunderbird (`.thunderbird/`), Chrome, Edge
- GnuPG keys (`.gnupg/` — permissions fixed automatically)
- Cinnamon desktop, keybindings, applets, dconf settings
- LibreOffice, GIMP, qBittorrent, and other common app configs
- Custom `.desktop` launchers, icon themes, GNOME keyrings
- rclone credentials (flagged as sensitive)
- Crontab (exported automatically; you choose whether to restore it)

**Optional (unchecked by default):**
- Shell history (`.bash_history`)
- Steam game data (large — Steam re-downloads itself)

**Always skipped:** caches, Flatpak data, dev build caches (`.npm`/`.gradle`), and session-specific files.

## Safety

- Close **Firefox**, **Thunderbird**, and **Chrome/Edge** before running on the old PC — the wizard will warn you if they are still open.
- **rclone** credentials are flagged during selection — treat them like backup media.
- Edit **`~/.mintmigrate/manifest.toml`** before running the new-PC setup step if you want to drop packages.

## Requirements

- Python **3.10+** (standard on Linux Mint 21+).
- **`python3-venv`** — if missing, the launcher installs it automatically (requires `sudo`).
- `rsync` 3.2.3+, `ssh`, `apt-mark` / `apt-get`, `sudo` — all standard on Linux Mint 21+.
- **Zenity** — drives the GUI wizard (included on typical Cinnamon installs). Falls back to terminal prompts if absent. Set `MINTMIGRATE_USE_CLI=1` to force terminal mode.

## Advanced: subcommands

For scripted or repeat runs:

```bash
mintmigrate export -r user@NEW_IP
mintmigrate import
```

- **`export`:** `--remote user@host`, `--manifest-dir DIR`, `--dry-run`, `--non-interactive`, `--skip-preflight`.
- **`import`:** `--bundle DIR`, `--fix-ownership`, `--dry-run`, `--non-interactive`, `--force-identity` (override username check — risky).

`mintmigrate --help` and `mintmigrate export|import --help` list all options.

## Project layout

```
mintmigrate.py          # CLI entry point
launch_mintmigrate.sh   # One-click launcher (sets up venv automatically)
modules/                # packages, files, dotfiles, crontab, manifest I/O, permissions, ui
```
