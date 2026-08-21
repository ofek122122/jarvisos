"""VRAM-guard ladder tests — pure logic, mocked probe (no GPU in CI;
GPU paths behind the probe seam per the brief)."""

from pathlib import Path

from jv_brain.config import LADDER, BrainConfig
from jv_brain.launcher import launch, llama_args, pick_rung, rung_budget_bytes

GB = 1024**3
MB = 1024**2


def test_ladder_budgets_are_ordered():
    """Each GPU rung must need less VRAM than the one before — otherwise
    the ladder can't be a fallback ladder."""
    budgets = [rung_budget_bytes(r) for r in LADDER if r.gpu]
    assert budgets == sorted(budgets, reverse=True), budgets


def test_plenty_of_vram_picks_full():
    assert pick_rung(16 * GB).index == 0


def test_six_gb_card_with_desktop_running():
    """The real machine: 6 GB card, desktop on three monitors eats a
    chunk. ~5.7 GB free is not enough for full f16-KV (5.03 weights +
    0.58 KV + 0.4 compute + 0.3 margin) -> rung 1 (KV q8)."""
    assert pick_rung(int(5.7 * GB)).index == 1


def test_tighter_vram_descends_the_ladder():
    assert pick_rung(int(5.6 * GB)).index == 2  # needs ctx cut
    assert pick_rung(int(5.4 * GB)).index == 3  # needs smaller weights
    assert pick_rung(2 * GB).index == 4  # game running -> CPU
    assert pick_rung(0).index == 4


def test_no_gpu_falls_back_to_cpu():
    rung = pick_rung(None)
    assert rung.index == 4 and not rung.gpu


def test_launch_writes_rung_file_and_args(tmp_path: Path):
    cfg = BrainConfig(models_dir=tmp_path, rung_file=tmp_path / "llm-rung")
    captured: list[list[str]] = []
    rung = launch(cfg, port=9999, probe=lambda: 16 * GB, exec_fn=captured.append)
    assert rung.index == 0
    content = (tmp_path / "llm-rung").read_text()
    assert "rung=0" in content and "backend=gpu" in content
    args = captured[0]
    assert "--n-gpu-layers" in args and args[args.index("--n-gpu-layers") + 1] == "99"
    assert "--ctx-size" in args and args[args.index("--ctx-size") + 1] == "4096"
    assert "--cache-type-k" not in args  # f16 rung


def test_cpu_rung_args(tmp_path: Path):
    cfg = BrainConfig(models_dir=tmp_path, rung_file=tmp_path / "llm-rung")
    captured: list[list[str]] = []
    rung = launch(cfg, port=9999, probe=lambda: None, exec_fn=captured.append)
    assert rung.index == 4
    args = captured[0]
    assert args[args.index("--n-gpu-layers") + 1] == "0"
    assert "backend=cpu" in (tmp_path / "llm-rung").read_text()


def test_kv_budget_matches_qwen3_geometry():
    """4k ctx f16 KV for Qwen3-8B ≈ 576 MB — sanity-pin the arithmetic
    the whole ladder rests on."""
    full = LADDER[0]
    assert abs(full.kv_bytes() - 576 * MB) < 1 * MB
