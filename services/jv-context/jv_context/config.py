"""jv-context configuration — including the title-privacy blocklist.

Ofek (2026-08-22): the blocklist ships PRE-SEEDED, not empty — password
managers and private surfaces are redacted from day one, before anyone
gets burned once.
"""

from __future__ import annotations

import dataclasses


# app_id patterns (fnmatch, case-insensitive) whose titles are never
# published. Extend freely; removing entries is a deliberate act.
DEFAULT_APP_BLOCKLIST: tuple[str, ...] = (
    "*keepass*",  # KeePass, KeePassXC
    "*bitwarden*",
    "*1password*",
    "*private*",  # anything that self-describes as private
)

# Title substrings that mark private browser surfaces where the
# compositor exposes them (the app_id alone doesn't).
DEFAULT_TITLE_MARKERS: tuple[str, ...] = (
    "(private browsing)",  # Firefox
    "- incognito",  # Chromium family
    "[inprivate]",  # Edge
)


@dataclasses.dataclass
class ContextConfig:
    app_blocklist: tuple[str, ...] = DEFAULT_APP_BLOCKLIST
    title_markers: tuple[str, ...] = DEFAULT_TITLE_MARKERS
    system_period_s: float = 1.0
    health_period_s: float = 5.0
