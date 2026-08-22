"""1 Hz system snapshot. Probes are seams: real ones shell out to
wpctl/nvidia-smi on the machine; stubs serve dev and CI."""

from __future__ import annotations

import subprocess
from typing import Optional

import psutil


class AudioProbe:
    def volume(self) -> tuple[float, bool]:  # pragma: no cover - interface
        raise NotImplementedError


class WpctlProbe(AudioProbe):
    """Parses `wpctl get-volume @DEFAULT_AUDIO_SINK@` → (volume, muted).
    TODO(machine): PipeWire only exists on ares."""

    def volume(self) -> tuple[float, bool]:
        out = subprocess.run(
            ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # "Volume: 0.45 [MUTED]"
        parts = out.stdout.split()
        vol = float(parts[1]) if len(parts) >= 2 else 0.0
        return vol, "[MUTED]" in out.stdout


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
    """One context.system body."""
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
