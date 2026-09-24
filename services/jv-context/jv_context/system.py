"""1 Hz system snapshot. Probes are seams: real ones shell out to
wpctl/nvidia-smi on the machine; stubs serve dev and CI."""

from __future__ import annotations

import dataclasses
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


class GpuProbe:
    """Free VRAM, or an honest silence.

    `gpu_vram_free_mb` is OPTIONAL in schemas/context.system.json, and
    that optionality has a specific meaning — "free VRAM IF A GPU IS
    PRESENT". It does not mean "absent whenever the reading did not work
    out", so this seam has three answers rather than two:

      None              there is no GPU here. Not a fault; the field is
                        simply absent, which is what the schema says a
                        GPU-less machine looks like.
      float             a measurement.
      ProbeUnavailable  there IS a GPU and it stopped answering.
                        Invariant 6 calls 6 GB of VRAM a scheduling
                        problem; a scheduler flying blind is a
                        degradation somebody should hear about, and it
                        must not be indistinguishable from a machine
                        that never had a card.
    """

    def vram_free_mb(self) -> Optional[float]:  # pragma: no cover - interface
        raise NotImplementedError


def parse_nvidia_smi_vram(text: str) -> float:
    """`nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits`
    stdout -> free MiB.

    One line per GPU; ares has one, and the first line is it. `[N/A]` and
    `[Not Supported]` are what nvidia-smi prints when a device cannot
    answer the query, and NVML's own initialisation errors arrive on
    stdout the way wpctl's do. None of those is a number — and neither is
    `nan`, which float() accepts happily and which would reach the bus as
    a value that compares false to its own schema minimum.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        raise ProbeUnavailable("nvidia-smi printed nothing")
    try:
        mb = float(lines[0])
    except ValueError as exc:
        raise ProbeUnavailable(f"nvidia-smi said {lines[0]!r}") from exc
    if not math.isfinite(mb) or mb < 0:
        raise ProbeUnavailable(f"nvidia-smi VRAM {mb!r} is out of range")
    return mb


class NvidiaSmiProbe(GpuProbe):
    """Reads the first GPU through the driver's own CLI.

    `nvidia-smi` ships in the NVIDIA driver's `bin` output, not in this
    service's closure — and until modules/jarvis-services.nix named it on
    the unit path, not on the unit's PATH either, so this field had never
    once been on the bus on the machine whose whole VRAM ladder depends
    on it.

    A missing binary LATCHES the probe off. That PATH is a store path
    fixed when the unit started, so "there is no driver here" cannot stop
    being true while this process lives, and asking again once a second
    is ~86k processes a day spent re-learning it (backlog 14). Every
    other failure is a fault, because the binary being there means this
    machine has a driver and the silence is new.
    """

    def __init__(self) -> None:
        self._absent = False

    def vram_free_mb(self) -> Optional[float]:
        if self._absent:
            return None
        try:
            out = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            self._absent = True
            return None
        except (OSError, subprocess.SubprocessError) as exc:
            raise ProbeUnavailable(f"nvidia-smi did not run: {exc}") from exc
        if out.returncode != 0:
            raise ProbeUnavailable(f"nvidia-smi exited {out.returncode}")
        return parse_nvidia_smi_vram(out.stdout)


class StubGpuProbe(GpuProbe):
    """`answer` is what the card says: a number, None for no card, or an
    exception instance to raise."""

    def __init__(self, answer: object = None) -> None:
        self.answer = answer

    def vram_free_mb(self) -> Optional[float]:
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer  # type: ignore[return-value]


@dataclasses.dataclass(frozen=True)
class Snapshot:
    """One frame, plus why it is missing an optional field when that
    absence needs saying. The note travels WITH the body because the
    caller publishes both — the frame on context.system and the note on
    sys.health — and the two must describe the same tick."""

    body: dict
    gpu_note: Optional[str] = None


def snapshot(audio: AudioProbe, gpu: Optional[GpuProbe] = None) -> Snapshot:
    """One context.system frame, or ProbeUnavailable.

    Optional fields degrade to ABSENT (no GPU, no battery — the schema
    allows both). Required ones cannot: if the mixer will not answer
    there is no frame to publish, and the caller publishes nothing.

    So the GPU's failure costs exactly one field and never the other
    four. It does not cost the truth either: an unreadable card leaves a
    note for the heartbeat rather than looking like a machine that never
    had one.
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
    gpu_note: Optional[str] = None
    if gpu is not None:
        try:
            if (vram := gpu.vram_free_mb()) is not None:
                body["gpu_vram_free_mb"] = float(vram)
        except ProbeUnavailable as exc:
            gpu_note = f"context.system without gpu_vram_free_mb: {exc}"
    batt = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    if batt is not None:
        body["battery_pct"] = float(batt.percent)
    return Snapshot(body, gpu_note)
