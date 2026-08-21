# jarvis-doctor — Phase 0 exit-checklist verifier (BRIEF-phase0 task 3).
#
# Checks, each printing PASS/FAIL:
#   1. nvidia-smi sees the GTX 1660 SUPER
#   2. CUDA executes a trivial kernel (cuda-smoke)
#   3. Lenovo 510 FHD enumerates RGB *and* IR nodes; a frame captures from each
#   4. PipeWire sees the microphone and records audio
#   5. All three monitors run at native resolution+refresh under Wayland
#   6. Windows NVMe is NOT mounted and NOT in the bootloader
#   7. The 2 TB data disk is untouched (Phase 0: /tank deferred)
#
# Exit code = number of failures. Run as your normal user inside a niri
# session (check 5 talks to the compositor; check 3 needs `video` group).
#
# Invoked via writeShellApplication: set -euo pipefail is active and
# $CUDA_SMOKE is provided by the wrapper.

FAILURES=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() {
  printf 'FAIL  %s\n' "$*"
  FAILURES=$((FAILURES + 1))
}
section() { printf -- '\n--- %s\n' "$*"; }

# ---------------------------------------------------------------- 1. GPU
section "GPU"
gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || true)
if [ -z "$gpu_name" ]; then
  fail "nvidia-smi did not run — driver not loaded?"
elif grep -q "1660 SUPER" <<<"$gpu_name"; then
  pass "nvidia-smi sees: $gpu_name"
else
  fail "nvidia-smi reports '$gpu_name' — expected GTX 1660 SUPER"
fi

# --------------------------------------------------------------- 2. CUDA
section "CUDA"
if "$CUDA_SMOKE"; then
  pass "CUDA kernel executed and verified"
else
  fail "cuda-smoke failed — CUDA toolchain or driver problem"
fi

# ------------------------------------------------- 3. Camera (RGB + IR)
section "Camera (Lenovo 510 FHD: RGB + IR)"
rgb_ok=0
ir_ok=0
shopt -s nullglob
for dev in /dev/video*; do
  card=$(v4l2-ctl -d "$dev" --info 2>/dev/null | awk -F': ' '/Card type/ {print $2; exit}' || true)
  case "$card" in
    *Lenovo* | *510*) ;;
    *) continue ;;
  esac
  fmts=$(v4l2-ctl -d "$dev" --list-formats 2>/dev/null || true)
  frame=$(mktemp)
  if grep -qE "'(MJPG|YUYV|NV12)'" <<<"$fmts"; then
    if v4l2-ctl -d "$dev" --stream-mmap --stream-count=1 --stream-to="$frame" >/dev/null 2>&1 \
      && [ -s "$frame" ]; then
      rgb_ok=1
      printf '      RGB frame captured from %s (%s)\n' "$dev" "$card"
    fi
  fi
  if grep -q "'GREY'" <<<"$fmts"; then
    if v4l2-ctl -d "$dev" --set-fmt-video=pixelformat=GREY >/dev/null 2>&1 \
      && v4l2-ctl -d "$dev" --stream-mmap --stream-count=1 --stream-to="$frame" >/dev/null 2>&1 \
      && [ -s "$frame" ]; then
      ir_ok=1
      printf '      IR frame captured from %s (%s)\n' "$dev" "$card"
    fi
  fi
  rm -f "$frame"
done
if [ "$rgb_ok" = 1 ]; then pass "RGB stream captures"; else fail "no RGB frame from the Lenovo 510"; fi
if [ "$ir_ok" = 1 ]; then pass "IR stream captures"; else fail "no IR (GREY) frame from the Lenovo 510 — check it is the IR model's node"; fi

# --------------------------------------------------------- 4. Microphone
section "Microphone (PipeWire)"
if wpctl status 2>/dev/null | sed -n '/Sources:/,/^\s*$/p' | grep -qE '[0-9]+\.'; then
  pass "PipeWire lists at least one audio source"
else
  fail "no audio sources in wpctl status"
fi
rec=$(mktemp --suffix=.wav)
timeout --signal=INT 2 pw-record --rate 16000 "$rec" >/dev/null 2>&1 || true
if [ -s "$rec" ]; then
  pass "recorded audio from the default source"
else
  fail "pw-record produced no data"
fi
rm -f "$rec"

# ------------------------------------------------------------ 5. Monitors
section "Monitors (Wayland, via niri)"
outputs=$(niri msg outputs 2>/dev/null || true)
if [ -z "$outputs" ]; then
  fail "niri msg outputs failed — run inside the niri session"
else
  current=$(grep 'Current mode:' <<<"$outputs" || true)
  n_primary=$(grep -cE '2560x1440 @ 14[0-9]' <<<"$current" || true)
  n_secondary=$(grep -cE '1920x1080 @ (59|60)' <<<"$current" || true)
  if [ "$n_primary" = 1 ]; then
    pass "primary at 2560x1440@144"
  else
    fail "expected one output at 2560x1440@144, found $n_primary"
  fi
  if [ "$n_secondary" = 2 ]; then
    pass "both secondaries at 1920x1080@60"
  else
    fail "expected two outputs at 1920x1080@60, found $n_secondary"
  fi
fi

# ---------------------------------------- 6. Windows NVMe isolation
section "Windows NVMe (CT500P2SSD8) isolation"
nvme_dev=$(lsblk -dno NAME,MODEL | awk '/CT500P2SSD8/ {print $1; exit}' || true)
if [ -z "$nvme_dev" ]; then
  fail "Windows NVMe (CT500P2SSD8) not found — cannot verify isolation"
else
  mounts=$(lsblk -no MOUNTPOINTS "/dev/$nvme_dev" 2>/dev/null | grep -v '^$' || true)
  if [ -z "$mounts" ]; then
    pass "Windows NVMe has no mounted partitions"
  else
    fail "Windows NVMe is MOUNTED: $mounts"
  fi
fi
if bootctl list 2>/dev/null | grep -qi windows; then
  fail "systemd-boot contains a Windows entry — it must not (firmware menu only)"
else
  pass "no Windows entry in systemd-boot"
fi
esp_src=$(findmnt -no SOURCE /boot 2>/dev/null || true)
esp_parent=$(lsblk -no PKNAME "$esp_src" 2>/dev/null | head -n1 || true)
esp_model=$(lsblk -dno MODEL "/dev/$esp_parent" 2>/dev/null || true)
if grep -qi "WD Green" <<<"$esp_model"; then
  pass "/boot ESP lives on the WD Green ($esp_model)"
else
  fail "/boot ESP is on '$esp_model' — expected the WD Green 1 TB"
fi

# ------------------------------------------- 7. 2 TB data disk untouched
section "2 TB data disk (WD20EZAZ) untouched"
hdd_dev=$(lsblk -dno NAME,MODEL | awk '/WD20EZAZ/ {print $1; exit}' || true)
if [ -z "$hdd_dev" ]; then
  fail "2 TB WD20EZAZ not found"
else
  hdd_mounts=$(lsblk -no MOUNTPOINTS "/dev/$hdd_dev" 2>/dev/null | grep -v '^$' || true)
  if [ -z "$hdd_mounts" ]; then
    pass "2 TB disk has no mounted partitions (/tank decision deferred)"
  else
    fail "2 TB disk is MOUNTED: $hdd_mounts — it must stay untouched in Phase 0"
  fi
fi

# ------------------------------------------------------------- summary
printf -- '\n=== jarvis-doctor: '
if [ "$FAILURES" = 0 ]; then
  printf 'ALL PASS ===\n'
else
  printf '%d FAILURE(S) ===\n' "$FAILURES"
fi
exit "$FAILURES"
