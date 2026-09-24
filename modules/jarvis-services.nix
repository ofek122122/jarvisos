# systemd wiring for the Phase 1 stack (BRIEF-phase1 task 6).
#
# Topology (departure Q&A): HYBRID.
#   system: jarvisd (bus, /run/jarvis/bus.sock) · jv-llm (llama-server
#           behind the jv-llm-launch VRAM guard) · jv-brain
#   user:   jv-ears · jv-voice (PipeWire lives in the session)
# Killing any one service leaves the others running (invariant 1) —
# exit-checklist item 4 verifies on the machine.
#
# TODO(machine): units authored on Windows; first `nixos-rebuild build`
# verifies. Exit items 1–5 all run through this module.
{ config, lib, pkgs, self, ... }:
let
  cfg = config.jarvis;
  pyEnvs = import ../nix/jarvis-python.nix { inherit pkgs; };
  jarvisd = self.packages.x86_64-linux.jarvisd;
  jv-act = self.packages.x86_64-linux.jv-act;
  jv-hud = self.packages.x86_64-linux.jv-hud;
  llama = pkgs.llama-cpp.override { cudaSupport = true; };

  busSock = "/run/jarvis/bus.sock";
  modelsDir = "/var/lib/jarvis/models";
  rungFile = "/run/jarvis-llm/rung";

  commonEnv = {
    JARVIS_BUS = busSock;
    JARVIS_MODELS_DIR = modelsDir;
    JARVIS_PERSONALITY_DIR = "/etc/jarvis/personality";
    JARVIS_LLM_RUNG_FILE = rungFile;
  };

  harden = {
    NoNewPrivileges = true;
    PrivateTmp = true;
    ProtectSystem = "strict";
    ProtectHome = true;
    Restart = "on-failure";
    RestartSec = 2;
  };
in
{
  # ----------------------------------------------------------------- options
  # The machine's declared knobs. Everything else in this file is wiring that
  # is the same on every JarvisOS install; these are the parts of it a host is
  # allowed to differ on, and they live here because this module is their only
  # consumer.

  options.jarvis.voice.outputDevice = lib.mkOption {
    type = lib.types.nullOr lib.types.str;
    default = null;
    example = "alsa_output.usb-Focusrite_Scarlett_2i2-00.analog-stereo";
    description = ''
      The playback device jv-voice opens, named as PortAudio names it
      (it reaches the process as `JARVIS_VOICE_OUTPUT_DEVICE`). `null`, the
      default, leaves Jarvis on PortAudio's default device.

      Not a private knob. While it is null — and only while it is null — the
      default sink jv-context reports is provably the one Jarvis speaks into,
      which is the assumption the HUD's OutputPlate makes when it says OUTPUT
      MUTED. So jv-voice publishes whether it is set (`output_device_pinned`
      in its heartbeat) and the HUD goes quiet rather than confidently wrong
      the day somebody pins a device here (PLAN A41).
    '';
  };

  config = {
    # jv-voice reads an empty variable as "no device" (jv_voice/config.py), so
    # `outputDevice = ""` would be a configuration that says a device is pinned
    # while the running service reports none and the HUD keeps trusting a sink
    # nobody promised. There is no reading of the empty string worth having.
    assertions = [
      {
        assertion =
          cfg.voice.outputDevice == null
          || builtins.match "[[:space:]]*" cfg.voice.outputDevice == null;
        message = ''
          jarvis.voice.outputDevice is set to an empty (or whitespace-only)
          string. Use null to leave Jarvis on the default playback device, or
          name a real one — jv-voice would read this as null anyway and publish
          output_device_pinned = false, which is not what this config says.
        '';
      }
    ];

    # Personality is /etc-deployed from the repo — versioned identity,
    # readable by every service, writable by none (invariant 9).
    environment.etc."jarvis/personality/system.md".source = ../personality/system.md;
    environment.etc."jarvis/personality/voice.toml".source = ../personality/voice.toml;
    # theme.toml is the HUD's §06 tokens. Nothing reads it at runtime — it is
    # compiled into jv-hud's Theme singleton at build time — but identity is
    # identity: the whole of what Jarvis is should be readable in one directory
    # on the running machine, not two-thirds of it.
    environment.etc."jarvis/personality/theme.toml".source = ../personality/theme.toml;

    # The jv-act tool registry — reviewed like code (invariant 3), the
    # authoritative capability table. /etc, read-only.
    environment.etc."jarvis/tools.toml".source = ../services/jv-act/tools.toml;

    users.users.jarvisd = {
      isSystemUser = true;
      group = "jarvis";
    };
    users.users.jv-llm = {
      isSystemUser = true;
      group = "jarvis";
      extraGroups = [ "video" ];
    };
    users.users.jv-brain = {
      isSystemUser = true;
      group = "jarvis";
    };

    systemd.tmpfiles.rules = [
      "d /var/lib/jarvis 0755 root root -"
      "d ${modelsDir} 0775 root jarvis -"
    ];

    # ------------------------------------------------------------- system

    systemd.services.jarvisd = {
      description = "JarvisOS bus broker";
      wantedBy = [ "multi-user.target" ];
      serviceConfig = harden // {
        User = "jarvisd";
        Group = "jarvis";
        ExecStart = "${jarvisd}/bin/jarvisd --bus ${busSock}";
        RuntimeDirectory = "jarvis";
        RuntimeDirectoryMode = "0770";
        UMask = "0007"; # socket must be group-connectable
      };
    };

    systemd.services.jv-llm = {
      description = "llama-server behind the jv-llm-launch VRAM guard";
      wantedBy = [ "multi-user.target" ];
      path = [ config.hardware.nvidia.package.bin llama ];
      environment = commonEnv;
      serviceConfig = harden // {
        User = "jv-llm";
        Group = "jarvis";
        ExecStart = "${pyEnvs.brainEnv}/bin/jv-llm-launch --port 8080";
        RuntimeDirectory = "jarvis-llm";
        RuntimeDirectoryMode = "0750";
        ReadOnlyPaths = [ modelsDir ];
        # GPU access
        DeviceAllow = [
          "/dev/nvidia0 rw"
          "/dev/nvidiactl rw"
          "/dev/nvidia-uvm rw"
          "/dev/nvidia-uvm-tools rw"
        ];
      };
    };

    systemd.services.jv-brain = {
      description = "Jarvis brain v1 (conversation + tool calling)";
      wantedBy = [ "multi-user.target" ];
      wants = [ "jarvisd.service" "jv-llm.service" ];
      after = [ "jarvisd.service" "jv-llm.service" ];
      environment = commonEnv // { JARVIS_LLM_URL = "http://127.0.0.1:8080"; };
      serviceConfig = harden // {
        User = "jv-brain";
        Group = "jarvis";
        ExecStart = "${pyEnvs.brainEnv}/bin/jv-brain";
        ReadOnlyPaths = [ "/run/jarvis-llm" ];
        # user profile (who the user is) lives here — writable, private
        StateDirectory = "jarvis/brain";
        Environment = [ "JARVIS_STATE_DIR=/var/lib/jarvis" ];
      };
    };

    systemd.services.jv-guard = {
      description = "Jarvis guard (screens Windows binaries)";
      wantedBy = [ "multi-user.target" ];
      wants = [ "jarvisd.service" ];
      after = [ "jarvisd.service" ];
      path = [ pkgs.clamav ];
      environment = commonEnv;
      serviceConfig = harden // {
        User = "jv-guard";
        Group = "jarvis";
        ExecStart = "${pyEnvs.guardEnv}/bin/jv-guard";
      };
    };

    users.users.jv-guard = {
      isSystemUser = true;
      group = "jarvis";
    };

    # jv-context runs in the user session (compositor IPC + PipeWire).
    systemd.user.services.jv-context = {
      description = "Jarvis context (window events + system snapshot)";
      wantedBy = [ "default.target" ];
      unitConfig.ConditionUser = "ofek";
      environment = commonEnv;
      serviceConfig = {
        ExecStart = "${pyEnvs.contextEnv}/bin/jv-context";
        Restart = "on-failure";
        RestartSec = 2;
      };
    };

    # jv-act — REVIEW-PASSED 2026-08-22, now wired. User session: its
    # executors drive the compositor (niri msg), PipeWire (wpctl/playerctl)
    # and launch .desktop apps, all of which live in the session. It has
    # NO uinput and NO shell tool in v0. The registry at /etc/jarvis/
    # tools.toml is authoritative; the audit log is under the user's state.
    systemd.user.services.jv-act = {
      description = "Jarvis act (the privileged service — capability-gated tools)";
      wantedBy = [ "default.target" ];
      after = [ "jv-context.service" ];
      unitConfig.ConditionUser = "ofek";
      path = with pkgs; [
        niri wireplumber playerctl fd ripgrep xdg-utils systemd
      ];
      environment = commonEnv // {
        JARVIS_ACT_AUDIT = "%S/jarvis-act/audit.jsonl";
      };
      serviceConfig = {
        ExecStart = "${jv-act}/bin/jv-act --registry /etc/jarvis/tools.toml";
        StateDirectory = "jarvis-act";
        Restart = "on-failure";
        RestartSec = 2;
      };
    };

    # jv-hud — the HUD shell (blueprint §06). Installed and startable, but
    # deliberately NOT wanted by default.target yet: the HUD can now read the
    # bus (A5), but no element renders a signal from it, so there is still
    # nothing truthful to display — and a resident-but-empty overlay is
    # exactly the set dressing §06 forbids. `systemctl --user start jv-hud`
    # (or JV_HUD_SELFTEST=1 jv-hud) runs it; PLAN A3 turns it on for real.
    #
    # The bus bridge is NOT a unit of its own: the HUD spawns it as a child,
    # so the socket lives and dies with the surface that reads it. It
    # inherits JARVIS_BUS from commonEnv below.
    systemd.user.services.jv-hud = {
      description = "Jarvis HUD (Quickshell layer-shell overlay)";
      unitConfig.ConditionUser = "ofek";
      # Part of the graphical session: starts once niri is up (which exports
      # WAYLAND_DISPLAY into the user manager) and stops with it. The HUD is
      # 0 fps when idle and empty until a real signal, so running it always is
      # correct (blueprint §06 / invariant 10).
      wantedBy = [ "graphical-session.target" ];
      partOf = [ "graphical-session.target" ];
      after = [ "graphical-session.target" ];
      environment = commonEnv;
      serviceConfig = {
        ExecStart = "${jv-hud}/bin/jv-hud";
        Restart = "on-failure";
        RestartSec = 2;
      };
    };

    # jv-compat is on-demand (jv-compat install <path>), reachable via
    # binfmt/MIME — no persistent unit.
    environment.systemPackages = [ jarvisd jv-act jv-hud pyEnvs.compatEnv ];

    # --------------------------------------------------------------- user
    # PipeWire is a session service; ears and voice follow it. ConditionUser
    # keeps them out of the greeter's session.

    systemd.user.services.jv-ears = {
      description = "Jarvis ears (wake word -> VAD -> ASR)";
      wantedBy = [ "default.target" ];
      # Declared, not just commented: PortAudio loses the ALSA race if the
      # capture stream opens before PipeWire is up (seen at login,
      # 2026-09-15). Ordering narrows the race; the non-zero exit in
      # jv_ears/main.py + Restart=on-failure closes what's left of it.
      after = [ "pipewire.service" "wireplumber.service" ];
      wants = [ "pipewire.service" ];
      unitConfig.ConditionUser = "ofek";
      environment = commonEnv;
      serviceConfig = {
        ExecStart = "${pyEnvs.earsEnv}/bin/jv-ears";
        Restart = "on-failure";
        RestartSec = 2;
      };
    };

    systemd.user.services.jv-voice = {
      description = "Jarvis voice (speech.say -> piper + chain -> speakers)";
      wantedBy = [ "default.target" ];
      # Same PipeWire ordering as jv-ears (playback side of the same race).
      after = [ "pipewire.service" "wireplumber.service" ];
      wants = [ "pipewire.service" ];
      unitConfig.ConditionUser = "ofek";
      # The variable is written only when a device is actually declared: an
      # unconditional one would leave the unit saying `JARVIS_VOICE_OUTPUT_DEVICE=""`
      # on every machine, and "the config names no device" should not look like
      # "the config names the empty device" to anyone reading the unit.
      environment = commonEnv // lib.optionalAttrs (cfg.voice.outputDevice != null) {
        JARVIS_VOICE_OUTPUT_DEVICE = cfg.voice.outputDevice;
      };
      serviceConfig = {
        ExecStart = "${pyEnvs.voiceEnv}/bin/jv-voice";
        Restart = "on-failure";
        RestartSec = 2;
      };
    };

    # Greeting / onboarding trigger: on session start, ask the brain to
    # greet (or, on first boot, meet the user). A oneshot that publishes
    # one brain.request(source=system). jv publishes then exits.
    # TODO(machine): needs jv-ears/voice up; ordering verified on ares.
    systemd.user.services.jv-greeting = {
      description = "Jarvis greeting / first-boot onboarding trigger";
      wantedBy = [ "default.target" ];
      after = [ "jv-voice.service" ];
      unitConfig.ConditionUser = "ofek";
      environment = commonEnv;
      serviceConfig = {
        Type = "oneshot";
        # small settle so voice/ears are subscribed before we speak
        ExecStartPre = "${pkgs.coreutils}/bin/sleep 3";
        ExecStart =
          "${jarvisd}/bin/jv pub brain.request "
          + "--src jv-session --body '"
          + builtins.toJSON { text = "session_start"; source = "system"; conversation_id = "system"; speak = false; }
          + "'";
      };
    };
  };
}
