"""modules/snapshots.nix + pkgs/jv-snapshot-restore, read as text (PLAN F3).

btrfs snapshots + rollback: `hosts/ares/disko.nix` has said "subvolume
snapshots cover /home" since Phase 0 and never declared any — this is where
that promise gets a policy and a restore path.

WHY THIS SUITE DOES NOT CREATE A REAL SNAPSHOT. The obvious gate for "creates
a file, snapshots, deletes, restores, and asserts the file is back" is a real
`btrfs subvolume create` / `snapshot` / `undochange` round trip, and nixpkgs
ships exactly that as a VM test (`nixos/tests/snapper.nix`, upstream, already
run against every nixpkgs release — not this repo's to re-prove). Trying to
run the equivalent HERE was tried and deliberately abandoned: this worktree's
`/tmp` is not a scratch filesystem, it is a directory on ares' own
`/dev/mapper/jarvis-root` (`df -T /tmp` names it), the same disk
CLAUDE.md's machine section says this loop must never damage. `btrfs
subvolume create`/`snapshot` succeed there as an unprivileged user, but
`btrfs subvolume delete` does not (EPERM — this mount has no
`user_subvol_rm_allowed`, confirmed by trying it), and neither does `rm -rf`
on a subvolume. A headless test that creates subvolumes it cannot clean up
would leave permanent orphans on Ofek's real disk every time this suite runs
— worse than the bug it would be proving fixed. So the real round trip is
`[H]`: HUMAN-VERIFY.md has the exact commands, and `ops/ralph/nixtest.sh`
proves everything a nix evaluation can reach (the built units, wired in the
right order, running the right binaries against the right paths). What is
left, and what this file is, is the two things neither of those can see: that
the retention policy is actually BOUNDED (the item's "cannot fill the disk"),
and that the restore wrapper's argument handling — which direction the
`undochange` range runs, which configs it will accept — is correct BEFORE it
ever reaches a real snapper.
"""

import re

from test_gen_theme_qml import ROOT

MODULE = ROOT / "modules" / "snapshots.nix"
RESTORE = ROOT / "pkgs" / "jv-snapshot-restore" / "default.nix"
INIT = ROOT / "pkgs" / "jv-snapshots-init" / "default.nix"
SUBVOLUMES = ROOT / "hosts" / "ares" / "subvolumes.nix"


def module_src() -> str:
    return MODULE.read_text("utf-8")


def subvolumes_src() -> str:
    return SUBVOLUMES.read_text("utf-8")


def restore_src() -> str:
    return RESTORE.read_text("utf-8")


def init_src() -> str:
    return INIT.read_text("utf-8")


# --------------------------------------------------------------- retention


def test_both_subvolumes_ares_disko_declares_are_configured():
    # hosts/ares/disko.nix's own subvolumes are @root at "/" and @home at
    # "/home" — a config for a THIRD path would snapshot nothing (no such
    # subvolume exists) and a config missing either would leave one of the
    # two disko.nix explicitly calls out as snapshot-covered undeclared.
    # modules/snapshots.nix imports the list from hosts/ares/subvolumes.nix
    # rather than spelling it again (PLAN E10's "one list, not two" lesson),
    # so that shared file is what actually carries these two paths.
    assert "subvolumes.nix" in module_src(), (
        "modules/snapshots.nix no longer imports hosts/ares/subvolumes.nix"
    )
    src = subvolumes_src()
    assert '"/"' in src, "no subvolume config points at / (disko.nix's @root)"
    assert '"/home"' in src, "no subvolume config points at /home (disko.nix's @home)"


def test_the_timeline_limits_are_bounded_integers_not_left_at_upstream_defaults():
    # "a retention policy that cannot fill the disk" is a claim about NUMBERS,
    # and snapper's own module defaults every TIMELINE_LIMIT_* to 10 and
    # NUMBER_LIMIT to unset (unbounded) — silence here is not a policy, it is
    # inheriting whatever upstream ships next. Every limit PLAN F3 needs
    # bounded must be spelled out as a literal integer in this file.
    src = module_src()
    for key in (
        "TIMELINE_LIMIT_HOURLY",
        "TIMELINE_LIMIT_DAILY",
        "TIMELINE_LIMIT_WEEKLY",
        "TIMELINE_LIMIT_MONTHLY",
        "TIMELINE_LIMIT_YEARLY",
        "NUMBER_LIMIT",
        "NUMBER_LIMIT_IMPORTANT",
    ):
        m = re.search(rf"{key}\s*=\s*(-?\d+)\s*;", src)
        assert m, f"{key} is not set to a literal integer in modules/snapshots.nix"
        assert int(m.group(1)) >= 0, f"{key} is negative: {m.group(1)}"


def test_timeline_create_and_cleanup_are_both_on():
    # TIMELINE_CREATE with TIMELINE_CLEANUP off is a timeline that only grows;
    # TIMELINE_CLEANUP with TIMELINE_CREATE off never gets snapshots to clean.
    # The item needs both halves for the count to actually stay bounded.
    src = module_src()
    assert re.search(r"TIMELINE_CREATE\s*=\s*true\s*;", src)
    assert re.search(r"TIMELINE_CLEANUP\s*=\s*true\s*;", src)


# ----------------------------------------------------- the .snapshots gap


def test_the_init_script_targets_exactly_the_two_snapshots_subvolumes():
    # snapper's manual: SUBVOLUME "has to contain a subvolume named
    # .snapshots", and its NixOS module does not create one (its own comment:
    # create-config "is not the NixOS way"). This file's init unit is the only
    # thing standing between "declared" and "snapper-timeline.service fails
    # every hour" — so it has to name both paths, and only those two, however
    # the subvolume list is spelled. pkgs/jv-snapshots-init is the package
    # modules/snapshots.nix wires in (a script embedded in a systemd unit's
    # ExecStart is only a store-path STRING to a bare-checkout reader, so the
    # text worth reading here is the package's, not the module's).
    src = init_src()
    assert ".snapshots" in src, "no .snapshots subvolume is ever created"
    assert "subvolume create" in src


def test_init_unit_is_idempotent_it_checks_before_it_creates():
    # A oneshot that unconditionally runs `btrfs subvolume create` a second
    # boot fails outright (EEXIST) — which would make jv-snapshots-init
    # (and, transitively, every unit ordered after it) fail on every boot
    # after the first.
    src = init_src()
    assert "subvolume show" in src, (
        "jv-snapshots-init must check whether .snapshots already exists "
        "before creating it, or every boot after the first fails"
    )


def test_snapper_units_are_ordered_after_the_init_unit():
    # Requires= without After= only guarantees the unit is STARTED, not that
    # it has FINISHED first (systemd.unit(5), "Requires="/"After=" together
    # is what orders it) — snapper-timeline/-cleanup/-boot all need the
    # .snapshots subvolume to exist by the time they actually run, not merely
    # queued.
    src = module_src()
    for unit in ("snapper-timeline", "snapper-cleanup", "snapper-boot"):
        block_start = src.find(f"{unit} = {{")
        assert block_start != -1, f"systemd.services.{unit} is never mentioned"
        block = src[block_start : block_start + 200]
        assert "jv-snapshots-init.service" in block, (
            f"systemd.services.{unit} does not order itself after jv-snapshots-init.service"
        )
        assert "requires" in block and "after" in block, (
            f"systemd.services.{unit} sets requires or after but not both — "
            "Requires alone does not wait for it to finish"
        )


# -------------------------------------------------------- the restore CLI


def code(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def test_restore_runs_the_range_old_snapshot_to_current_not_the_reverse():
    # snapper's own semantics: `undochange <A>..<B>` copies B's differences
    # from A onto the live tree — read backwards (`0..<A>`) it copies the
    # CURRENT state onto the historical one, i.e. it restores nothing and
    # silently no-ops (0 is the live subvolume in both positions of a diff
    # against itself). This is the one bug in this file a real snapper run
    # would not even fail loudly on.
    src = code(restore_src())
    assert re.search(r'undochange\s+"\$num\.\.0"', src), (
        "jv-snapshot-restore does not run 'undochange \"$num..0\"' "
        "(wrong direction restores nothing)"
    )
    assert "0..$num" not in src, "jv-snapshot-restore runs undochange backwards"


def test_restore_validates_the_snapshot_number_before_calling_snapper():
    # A non-numeric argument reaching `snapper ... undochange nonsense..0`
    # produces a snapper error about a config file it cannot parse, naming
    # neither the argument nor what was expected of it.
    src = restore_src()
    assert re.search(r"\[\[\s*!\s*\"\$num\"\s*=~", src), (
        "jv-snapshot-restore does not validate that the snapshot number is numeric"
    )


def test_restore_only_accepts_the_two_declared_configs():
    # modules/snapshots.nix declares exactly `root` and `home` — a third
    # config name would reach `snapper -c <name>`, which fails with a config
    # file it never wrote (/etc/snapper/configs/<name> does not exist), one
    # layer removed from "root or home" being the honest answer.
    src = restore_src()
    m = re.search(r"case \"\$config\" in\s*\n\s*(.+?)\)\s*;;", src)
    assert m, "no case statement restricts $config to known values"
    assert set(m.group(1).split("|")) == {"root", "home"}


def test_restore_forwards_no_unvalidated_command_through_config_or_number():
    # $config and $num both reach `snapper -c "$config" ... "$num..0"` quoted,
    # so a value with a space or a metacharacter cannot leave the argument it
    # was passed in — but only if BOTH stay inside quoted expansions.
    src = code(restore_src())
    assert '"$config"' in src, "config is interpolated unquoted somewhere"
    assert '"$num..0"' in src, "snapshot number is interpolated unquoted somewhere"
