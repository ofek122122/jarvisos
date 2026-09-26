# jarvis-doctor — Phase 0 exit-checklist verifier (BRIEF-phase0 task 3),
# plus PLAN G6's `--repair` for the one class of breakage a doctor can fix
# by itself: a Jarvis systemd --user unit that has crashed into `failed`.
#
# Checks, each printing PASS/FAIL:
#   1. nvidia-smi sees the GTX 1660 SUPER
#   2. CUDA executes a trivial kernel (cuda-smoke)
#   3. Lenovo 510 FHD enumerates RGB *and* IR nodes; a frame captures from each
#   4. PipeWire sees the microphone and records audio
#   5. Every monitor hosts/ares/outputs.nix declares is live at exactly the
#      mode and position it declares, and no other output is connected
#   6. Windows NVMe is NOT mounted and NOT in the bootloader
#   7. The 2 TB data disk is not mounted (permanently off-limits)
#   8. Every jv-*/jarvis-* systemd --user unit is not in `failed` state; with
#      `--repair`, a failed one is reset and restarted (never anything system-
#      level, never jv-act's or jarvisd's own CODE — only the ordinary
#      `systemctl --user restart` a human would run by hand).
#
# Exit code = number of failures. Run as your normal user inside a niri
# session (check 5 talks to the compositor; check 3 needs `video` group).
#
# Invoked via writeShellApplication: set -euo pipefail is active, and the
# wrapper provides $CUDA_SMOKE and $JARVIS_OUTPUTS (check 5's expectation,
# generated from the host's declaration — see pkgs/jarvis-doctor/default.nix).

usage() {
  printf 'usage: jarvis-doctor [--repair]\n' >&2
  exit 2
}

REPAIR=0
case "${1:-}" in
  "") ;;
  --repair) REPAIR=1 ;;
  *) usage ;;
esac

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
# PLAN E13. This check used to be `grep -cE '2560x1440 @ 14[0-9]'` and
# `grep -cE '1920x1080 @ (59|60)'` — ares' three monitors written a fourth
# time, in a regex, in a shell script, where the primary's 144.006 had become a
# character class. It asked "is this machine what somebody typed in August".
# It asks "is this machine the machine this flake declares" now: the
# expectation is GENERATED from hosts/ares/outputs.nix and interpolated into
# the package as $JARVIS_OUTPUTS, one tab-separated row per declared output —
#
#     name <TAB> width <TAB> height <TAB> refresh <TAB> x <TAB> y
#
# and a monitor added there is checked here on the next rebuild with nobody
# remembering to edit this file.
#
# BOTH DIRECTIONS, because they are different findings: a declared output that
# is missing or running the wrong mode is a panel showing art and bars composed
# for something else, and an UNDECLARED output is a monitor nothing in this
# flake has ever heard of — no bespoke wallpaper, no niri rule, and no other
# check that would ever mention it.
#
# THE WHOLE POSITION, not just the left edge (PLAN E14). `Logical position:
# X, Y` used to be read for its X alone, because the declaration had no `y` to
# compare the other half against — so a side panel sitting a screen-height too
# low was three passes and no finding: right modes, right names, a desktop
# whose bar and wallpaper are placed for a row of three that is not a row.
decl_file="${JARVIS_OUTPUTS:-}"
declared=""
if [ -n "$decl_file" ] && [ -r "$decl_file" ]; then
  declared=$(grep -vE '^[[:space:]]*$' "$decl_file" || true)
fi
outputs=$(niri msg outputs 2>/dev/null || true)
if [ -z "$decl_file" ]; then
  # Unset, unreadable and empty are three different findings and none of them
  # may be reported as one of the others (the E12 lesson, one package along):
  # each is a sentence about a file, and only one of them is about its contents.
  fail "JARVIS_OUTPUTS is unset — this is the unwrapped doctor.sh, which carries no expectation to check the monitors against"
elif [ ! -r "$decl_file" ]; then
  fail "JARVIS_OUTPUTS points at $decl_file, which cannot be read — the declaration never reached the built package"
elif [ -z "$declared" ]; then
  fail "$decl_file declares no monitors, so this check would pass on any screen at all"
elif [ -z "$outputs" ]; then
  fail "niri msg outputs failed — run inside the niri session"
else
  # One `connector <TAB> WxH <TAB> refresh <TAB> x <TAB> y` row per live
  # output, from niri's blocks:
  #
  #     Output "HP Inc. HP 27xq CNK038121B" (HDMI-A-1)
  #       Current mode: 2560x1440 @ 144.006 Hz
  #       Logical position: 0, 0
  #
  # A DISABLED output has a block and no `Current mode:`, so its fields keep
  # the `?` the header set — which is a mismatch below, and not a skip.
  live=$(awk '
    function flush() { if (conn != "") printf "%s\t%s\t%s\t%s\t%s\n", conn, mode, hz, x, y }
    /^Output /                       { flush(); conn = $NF; gsub(/[()]/, "", conn)
                                       mode = "?"; hz = "?"; x = "?"; y = "?" }
    /^[[:space:]]+Current mode:/     { mode = $3; hz = $5 }
    /^[[:space:]]+Logical position:/ { x = $3; sub(/,$/, "", x); y = $4 }
    END { flush() }
  ' <<<"$outputs")

  # `while read` over a here-string runs in THIS shell, not a subshell, so the
  # failures these arms count survive the loop.
  while IFS=$'\t' read -r name w h hz x y; do
    [ -n "$name" ] || continue
    want=$(printf '%s\t%sx%s\t%s\t%s\t%s' "$name" "$w" "$h" "$hz" "$x" "$y")
    got=$(awk -F'\t' -v n="$name" '$1 == n { print; exit }' <<<"$live")
    if [ -z "$got" ]; then
      fail "$name is declared (${w}x${h} @ ${hz} Hz at ${x},${y}) and the session has no such output"
    elif [ "$got" = "$want" ]; then
      pass "$name at ${w}x${h} @ ${hz} Hz, at ${x},${y} in the layout"
    else
      fail "$name is declared as '$(tr '\t' ' ' <<<"$want")' and is live as '$(tr '\t' ' ' <<<"$got")'"
    fi
  done <<<"$declared"

  extra=$(awk -F'\t' '
    NR == FNR { want[$1] = 1; next }
    !($1 in want) { printf " %s (%s @ %s Hz)", $1, $2, $3 }
  ' "$decl_file" - <<<"$live")
  if [ -z "$extra" ]; then
    pass "the session has no output beyond the $(wc -l <<<"$declared") this flake declares"
  else
    fail "the session also has${extra} — hosts/ares/outputs.nix does not declare them, so nothing composed art or placed a bar for them"
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

# -------------------------------- 7. 2 TB data disk off-limits (not mounted)
section "2 TB data disk (WD20EZAZ) off-limits — not mounted"
hdd_dev=$(lsblk -dno NAME,MODEL | awk '/WD20EZAZ/ {print $1; exit}' || true)
if [ -z "$hdd_dev" ]; then
  fail "2 TB WD20EZAZ not found"
else
  hdd_mounts=$(lsblk -no MOUNTPOINTS "/dev/$hdd_dev" 2>/dev/null | grep -v '^$' || true)
  if [ -z "$hdd_mounts" ]; then
    pass "2 TB disk has no mounted partitions (permanently off-limits; os-prober reads its ESP RO only)"
  else
    fail "2 TB disk is MOUNTED: $hdd_mounts — it is off-limits, JarvisOS must never mount it"
  fi
fi

# --------------------------------------- 8. Jarvis user services (systemd)
section "Jarvis user services (systemd --user)"
# Every unit this flake declares for Jarvis follows one of two prefixes
# everywhere in modules/ — jv-* or jarvis-* (jarvis-wallpaper is the one
# jarvis- name, and it is a real one: `grep -rn "systemd.user.services\."
# modules/ hosts/` is what confirms it, not a guess). That naming convention
# is the thing this check reads instead of a second, hand-kept list of unit
# names — the same "declared once, generated everywhere" reason check 5's
# monitor list stopped being typed a fourth time (PLAN E13): a unit is either
# named like ours or it is not this doctor's to touch.
units=$(systemctl --user list-units --all --plain --no-legend --type=service,timer 'jv-*' 'jarvis-*' 2>/dev/null || true)
if [ -z "$units" ]; then
  fail "systemctl --user lists no jv-*/jarvis-* units — this session has not switched this flake's generation, or this is not a real login session"
else
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    unit=$(awk '{print $1}' <<<"$line")
    active=$(awk '{print $3}' <<<"$line")
    if [ "$active" != "failed" ]; then
      pass "$unit ($active)"
      continue
    fi
    if [ "$REPAIR" = 1 ]; then
      systemctl --user reset-failed "$unit" >/dev/null 2>&1 || true
      systemctl --user restart "$unit" >/dev/null 2>&1 || true
      fixed=$(systemctl --user is-active "$unit" 2>/dev/null || true)
      if [ "$fixed" = "failed" ] || [ -z "$fixed" ]; then
        fail "$unit was FAILED and --repair could not bring it back (now '$fixed') — see: journalctl --user -u $unit"
      else
        pass "$unit was FAILED, --repair restarted it and it is now $fixed"
      fi
    else
      fail "$unit has FAILED — re-run 'jarvis-doctor --repair' to restart it, or: systemctl --user restart $unit"
    fi
  done <<<"$units"
fi

# ------------------------------------------------------------- summary
printf -- '\n=== jarvis-doctor: '
if [ "$FAILURES" = 0 ]; then
  printf 'ALL PASS ===\n'
else
  printf '%d FAILURE(S) ===\n' "$FAILURES"
fi
exit "$FAILURES"
