"""1 Hz system snapshot. Probes are seams: real ones shell out to
wpctl/nvidia-smi on the machine; stubs serve dev and CI."""

from __future__ import annotations

import math
import subprocess
from typing import Optional

import psutil


class ProbeUnavailable(Exception):
    """A probe could not read the machine.

    Raised, never returned as a default. Every field a probe feeds is
    REQUIRED by schemas/context.system.json, so a half-read machine has
    no legal frame at all — and a substituted number would be worse than
    a missing one, because it is indistinguishable from a measurement.

    `audio_volume: 0.0` in particular is not a harmless placeholder. The
    HUD's `core/OutputState.qml` reads `audio_volume <= 0` during an
    utterance as "Jarvis is speaking and you cannot hear a word of it"
    and puts a plate on screen about it. A mixer nobody managed to read
    would have lit that plate — a fakeable sensor indicator, which is
    exactly what invariant 10 forbids.
    """


class AudioProbe:
    def volume(self) -> tuple[float, bool]:  # pragma: no cover - interface
        raise NotImplementedError


def parse_wpctl_volume(text: str) -> tuple[float, bool]:
    """`wpctl get-volume @DEFAULT_AUDIO_SINK@` stdout -> (volume, muted).

    The line is "Volume: 0.45", with " [MUTED]" appended when muted.
    Anything else — an empty string, wpctl's own error text (it prints
    those on stdout and still may exit 0), a number that is not one
    (`nan` parses as a float and is not a reading), a value below the
    schema's own minimum, or a future wpctl wording it differently — is
    ProbeUnavailable. There is no fallback value that would be true.
    """
    parts = text.split()
    if len(parts) < 2 or not parts[0].lower().startswith("volume"):
        raise ProbeUnavailable(f"wpctl said {text.strip()!r}")
    try:
        vol = float(parts[1])
    except ValueError as exc:
        raise ProbeUnavailable(f"wpctl volume {parts[1]!r} is not a number") from exc
    if not math.isfinite(vol) or vol < 0:
        raise ProbeUnavailable(f"wpctl volume {vol!r} is out of range")
    return vol, "[MUTED]" in text


class WpctlProbe(AudioProbe):
    """Reads the default sink through wireplumber's CLI.
    TODO(machine): PipeWire only exists on ares."""

    def volume(self) -> tuple[float, bool]:
        try:
            out = subprocess.run(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            # wpctl ships in wireplumber and is not in this service's own
            # closure; it is also the one part of the snapshot that can
            # hang, since it talks to another daemon.
            raise ProbeUnavailable(f"wpctl did not run: {exc}") from exc
        if out.returncode != 0:
            raise ProbeUnavailable(f"wpctl exited {out.returncode}")
        return parse_wpctl_volume(out.stdout)


class StubAudioProbe(AudioProbe):
    def __init__(self, vol: float = 1.0, muted: bool = False) -> None:
        self._v, self._m = vol, muted

    def volume(self) -> tuple[float, bool]:
        return self._v, self._m


def gpu_vram_free_mb() -> Optional[float]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return float(out.stdout.strip().splitlines()[0])
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        pass
    return None


def snapshot(audio: AudioProbe) -> dict:
    """One context.system body, or ProbeUnavailable.

    Optional fields degrade to ABSENT (no GPU, no battery — the schema
    allows both). Required ones cannot: if the mixer will not answer
    there is no frame to publish, and the caller publishes nothing.
    """
    try:
        load1 = psutil.getloadavg()[0]
    except (OSError, AttributeError):
        load1 = 0.0
    vol, muted = audio.volume()
    body = {
        # any non-loopback interface up — no packets sent (privacy)
        "net_online": any(
            st.isup for name, st in psutil.net_if_stats().items() if name != "lo"
        ),
        "load1": float(load1),
        "mem_used_pct": float(psutil.virtual_memory().percent),
        "audio_volume": float(vol),
        "audio_muted": bool(muted),
    }
    if (vram := gpu_vram_free_mb()) is not None:
        body["gpu_vram_free_mb"] = vram
    batt = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    if batt is not None:
        body["battery_pct"] = float(batt.percent)
    return body
