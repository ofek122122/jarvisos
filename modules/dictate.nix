# jv-dictate (PLAN F5b) — push-to-talk dictation: hold Pause, speak, release,
# and the transcript is handed to a Sink. Today that Sink is jv_dictate.
# injector.LogSink, which only prints — the real keystroke injector needs a
# NEW jv-act tool (`input.type_text`) that does not exist yet and is
# human-review-only (docs/optimization-backlog.md R11, PLAN F5, still `[B]`).
# Swapping it in later is a one-call change inside services/jv-dictate/
# jv_dictate/main.py; nothing here has to move.
#
# No wake word, no VAD, and no dialog.listen — the key IS the gate, so this
# never asks jv-ears for a no-wake window and needs no schemas/** change:
# the one fact the HUD could ever want (a recording is in progress) already
# has a home on sys.health's free-form, service-local `metrics` (the same
# extension point jv-ears' own `mic_open` rides on). A HUD plate reading it
# is PLAN F5c, not built here — see PLAN.md.
{ pkgs, ... }:
let
  pyEnvs = import ../nix/jarvis-python.nix { inherit pkgs; };
  busSock = "/run/jarvis/bus.sock";
in
{
  systemd.user.services.jv-dictate = {
    description = "Jarvis dictate (push-to-talk: key -> Whisper -> a Sink)";
    wantedBy = [ "default.target" ];
    # Same PortAudio/PipeWire race jv-ears orders against (modules/
    # jarvis-services.nix) — this service opens its own capture stream.
    after = [ "pipewire.service" "wireplumber.service" ];
    wants = [ "pipewire.service" ];
    unitConfig.ConditionUser = "ofek";
    environment = {
      JARVIS_BUS = busSock;
      JARVIS_MODELS_DIR = "/var/lib/jarvis/models";
    };
    serviceConfig = {
      ExecStart = "${pyEnvs.dictateEnv}/bin/jv-dictate";
      Restart = "on-failure";
      RestartSec = 2;
    };
  };
}
