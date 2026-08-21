#!/usr/bin/env bash
# models/fetch.sh — fetch all model weights with pinned SHA256s.
# (BRIEF-phase1 §6: no "download it manually from somewhere".)
#
# Usage:
#   ./models/fetch.sh [--only ears,voice,brain] [--check]
#
# Target dir: $JARVIS_MODELS_DIR, else /var/lib/jarvis/models on Linux,
# else ./models-cache (Windows/dev). Idempotent: verified files are
# skipped; hash mismatches are fatal and the file is removed.
#
# Hash provenance (2026-08-21): LFS sha256 from the HuggingFace API;
# small files + GitHub assets hashed locally at pin time.
set -euo pipefail

only="ears,voice,brain"
check=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only) only="$2"; shift 2 ;;
    --check) check=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -n "${JARVIS_MODELS_DIR:-}" ]; then
  dest_root="$JARVIS_MODELS_DIR"
elif [ "$(uname -s)" = "Linux" ]; then
  dest_root="/var/lib/jarvis/models"
else
  dest_root="$(cd "$(dirname "$0")/.." && pwd)/models-cache"
fi
mkdir -p "$dest_root"
echo "models -> $dest_root (groups: $only)"

HF="https://huggingface.co"
OWW="https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"

# group|relative dest|sha256|url
manifest() {
  cat <<EOF
ears|openwakeword/hey_jarvis_v0.1.onnx|94a13cfe60075b132f6a472e7e462e8123ee70861bc3fb58434a73712ee0d2cb|$OWW/hey_jarvis_v0.1.onnx
ears|openwakeword/melspectrogram.onnx|ba2b0e0f8b7b875369a2c89cb13360ff53bac436f2895cced9f479fa65eb176f|$OWW/melspectrogram.onnx
ears|openwakeword/embedding_model.onnx|70d164290c1d095d1d4ee149bc5e00543250a7316b59f31d056cff7bd3075c1f|$OWW/embedding_model.onnx
ears|silero/silero_vad.onnx|1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3|https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx
ears|whisper/faster-distil-small.en/model.bin|1187de3982cdcf962a2fb8f797e429fb4651b875b18fe9ce50b58b52fc9072b7|$HF/Systran/faster-distil-whisper-small.en/resolve/main/model.bin
ears|whisper/faster-distil-small.en/config.json|b571ae8022a34c1df50876a65b5f813a5c22e5ee3b87bc0e4db5662dfc9c2c3d|$HF/Systran/faster-distil-whisper-small.en/resolve/main/config.json
ears|whisper/faster-distil-small.en/preprocessor_config.json|a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d|$HF/Systran/faster-distil-whisper-small.en/resolve/main/preprocessor_config.json
ears|whisper/faster-distil-small.en/tokenizer.json|c9c77688528c0509abbd41873edab16384b8f041531b1d3092ab4d1d83a02a50|$HF/Systran/faster-distil-whisper-small.en/resolve/main/tokenizer.json
ears|whisper/faster-distil-small.en/vocabulary.json|4dadfee7c4a871665f65c06037f5f5ec893fb2d7f5eb4cf11063618e31dbe11a|$HF/Systran/faster-distil-whisper-small.en/resolve/main/vocabulary.json
voice|piper/en_US-ryan-high.onnx|b3990d7606e183ec8dbfba70a4607074f162de1a0c412e0180d1ff60bb154eca|$HF/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx
voice|piper/en_US-ryan-high.onnx.json|c6d3b98f08315cb4bebf0d49d50fc4ff491b503c64b940cd3d5ca28543b48011|$HF/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx.json
brain|llm/Qwen3-8B-Q4_K_M.gguf|d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785|$HF/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf
brain|llm/Qwen3-8B-Q4_K_S.gguf|3672483a71bb93e2a18c1c1b8ca39e0b7018ce877ca8aff3df6539184a042fb0|$HF/bartowski/Qwen_Qwen3-8B-GGUF/resolve/main/Qwen_Qwen3-8B-Q4_K_S.gguf
EOF
}

sha() { sha256sum "$1" | cut -d' ' -f1; }

fail=0
while IFS='|' read -r group rel want url; do
  case ",$only," in *",$group,"*) ;; *) continue ;; esac
  dst="$dest_root/$rel"
  if [ -f "$dst" ] && [ "$(sha "$dst")" = "$want" ]; then
    echo "ok       $rel"
    continue
  fi
  if [ "$check" = 1 ]; then
    echo "MISSING  $rel"
    fail=1
    continue
  fi
  echo "fetch    $rel"
  mkdir -p "$(dirname "$dst")"
  curl -fL --retry 5 --retry-delay 2 -o "$dst.part" "$url"
  got="$(sha "$dst.part")"
  if [ "$got" != "$want" ]; then
    rm -f "$dst.part"
    echo "HASH MISMATCH for $rel" >&2
    echo "  want $want" >&2
    echo "  got  $got" >&2
    exit 1
  fi
  mv "$dst.part" "$dst"
done < <(manifest)

if [ "$fail" = 1 ]; then
  echo "some models missing (run without --check to fetch)" >&2
  exit 1
fi
echo "all requested models verified."
