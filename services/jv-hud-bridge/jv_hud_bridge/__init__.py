"""jv-hud-bridge — the HUD's read-only bus client.

Started as a child of the HUD, never as a unit of its own: when the HUD
goes, so does its window onto the bus. See bridge.py for the line protocol.
"""

from . import bridge  # noqa: F401
