# jv-snapshot-restore — the one command PLAN F3 asks for: "a documented
# one-command restore" over the snapper timeline modules/snapshots.nix
# declares for `@root` and `@home`.
#
# WHY A WRAPPER AND NOT "JUST RUN SNAPPER". `snapper undochange` is already
# one command, but it is one command with three ways to get it wrong under
# pressure — the config is a name (`root`/`home`), not the path you are
# staring at; the range is `<snapshot>..0` and typing `0..<snapshot>` runs it
# backwards, restoring your CURRENT files over the old ones; and there is no
# built-in "what number was that" step, so the panic-restore is usually
# preceded by scrollback-hunting through `snapper list`. This fixes the
# config name to one of exactly two known-good values, fixes the direction of
# the range so the argument you type is simply "which snapshot", and makes
# `list` the same command family as `restore` so there is one thing to
# remember at 2 a.m., not two.
#
# WHY THIS DOES NOT TOUCH jv-act. Invariant 3 is that only jv-act mutates
# system state, but that invariant governs Jarvis's OWN actions — what the
# assistant does on your behalf without your hands on the keyboard. This is a
# terminal tool a human runs deliberately, the same tier as `nixos-rebuild`
# or `snapper` itself, not a bus-driven capability. If J-track work ever wants
# "Jarvis, undo that" as a voice command, THAT tool proposal belongs in
# docs/optimization-backlog.md for human review — this file is the plumbing
# it would call, not the capability grant.
{
  writeShellApplication,
  snapper,
}:
writeShellApplication {
  name = "jv-snapshot-restore";

  runtimeInputs = [ snapper ];

  text = ''
    usage() {
      cat >&2 <<'EOF'
    usage: jv-snapshot-restore list <root|home>
           jv-snapshot-restore restore <root|home> <snapshot-number> [path...]

    list     shows the numbered snapshots modules/snapshots.nix' timeline has
             taken of / (root) or /home (home).
    restore  copies the state of <snapshot-number> back over the CURRENT
             subvolume — the whole thing, or only the given paths (relative
             to the subvolume root, e.g. Documents/report.md). Run 'list'
             first if you do not already know the number.
    EOF
      exit 2
    }

    [ "$#" -ge 1 ] || usage
    cmd="$1"; shift

    [ "$#" -ge 1 ] || usage
    config="$1"; shift
    case "$config" in
      root|home) ;;
      *)
        echo "jv-snapshot-restore: unknown config '$config' (must be 'root' or 'home')" >&2
        exit 2
        ;;
    esac

    case "$cmd" in
      list)
        exec snapper -c "$config" list
        ;;
      restore)
        [ "$#" -ge 1 ] || {
          echo "jv-snapshot-restore: restore needs a snapshot number — see 'jv-snapshot-restore list $config'" >&2
          exit 2
        }
        num="$1"; shift
        if [[ ! "$num" =~ ^[0-9]+$ ]]; then
          echo "jv-snapshot-restore: '$num' is not a snapshot number — see 'jv-snapshot-restore list $config'" >&2
          exit 2
        fi
        # <num>..0 and never the reverse: 0 is always "the subvolume as it is
        # right now", so this direction restores the OLD state over the new
        # one. Typing it backwards would restore your current files over the
        # snapshot, silently doing nothing useful and destroying nothing
        # visible until the next time you needed that snapshot.
        exec snapper -c "$config" undochange "$num..0" "$@"
        ;;
      *)
        usage
        ;;
    esac
  '';

  meta = {
    description = "One-command restore over JarvisOS's snapper timeline (PLAN F3)";
    mainProgram = "jv-snapshot-restore";
  };
}
