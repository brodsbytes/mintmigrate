"""Browser-related paths and user-facing notes (Firefox, Chrome, Edge)."""

from __future__ import annotations

# Paths relative to home; used for warnings and documentation strings.
FIREFOX_PROFILE_ROOT = ".mozilla"
THUNDERBIRD_PROFILE_ROOT = ".thunderbird"
CHROME_CONFIG = ".config/google-chrome"
EDGE_CONFIG = ".config/microsoft-edge"

BROWSER_NOTES = (
    "Firefox and Thunderbird profiles are copied verbatim; close those apps before export.\n"
    "Chrome and Edge profiles are under ~/.config; Google/Microsoft account sync is an alternative."
)
