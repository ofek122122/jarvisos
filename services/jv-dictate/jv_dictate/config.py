"""jv-dictate configuration. Deliberately small: this service borrows
jv-ears' model directory (JARVIS_MODELS_DIR, invariant 7 — one episodic
store, one model store, both on the WD Green) rather than fetching a
second copy of the same weights, and everything else is a handful of
literal constants a human can read in one place."""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path


def default_models_dir() -> Path:
    if env := os.environ.get("JARVIS_MODELS_DIR"):
        return Path(env)
    if sys.platform != "win32":
        return Path("/var/lib/jarvis/models")
    # Windows dev: repo-local cache (models/fetch.sh default), same
    # fallback services/jv-ears/jv_ears/config.py uses.
    return Path(__file__).resolve().parents[3] / "models-cache"


@dataclasses.dataclass
class DictateConfig:
    models_dir: Path = dataclasses.field(default_factory=default_models_dir)

    sample_rate: int = 16_000
    asr_beam_size: int = 1

    # The physical key this service listens for, by evdev keycode name.
    # PAUSE: not bound anywhere in modules/niri/config-base.kdl (checked by
    # grep before picking it), and it is a dedicated key on every keyboard
    # this machine has rather than a modifier already carrying meaning —
    # unlike Super (the app-menu tap, modules/super-menu.nix) or Ctrl/Alt
    # (held by half of niri's own binds). Overridable so a test rig with a
    # different keyboard is not stuck with this one's choice.
    trigger_key: str = "KEY_PAUSE"

    # Hard cap on one recording, mirroring dialog.listen's own
    # `window_s <= 60`: the same argument applies here — a key that never
    # comes back up (a stuck switch, a dropped USB event) must not become
    # an open mic. Enforced in ptt.py, not merely documented here.
    max_recording_s: float = 60.0

    health_period_s: float = 5.0

    @property
    def whisper_dir(self) -> Path:
        return self.models_dir / "whisper" / "faster-distil-small.en"
