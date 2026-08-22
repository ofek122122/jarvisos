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
{ config, pkgs, self, ... }:
let
  pyEnvs = import ../nix/jarvis-python.nix { inherit pkgs; };
  jarvisd = self.packages.x86_64-linux.jarvisd;
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
  # Personality is /etc-deployed from the repo — versioned identity,
  # readable by every service, writable by none (invariant 9).
  environment.etc."jarvis/personality/system.md".source = ../personality/system.md;
  environment.etc."jarvis/personality/voice.toml".source = ../personality/voice.toml;

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

  # jv-compat is on-demand (jv-compat install <path>), reachable via
  # binfmt/MIME — no persistent unit. jv-act is deliberately ABSENT:
  # REVIEW-REQUIRED (invariant 3). Both onboarding + greeting use jv-brain.
  environment.systemPackages = [ jarvisd pyEnvs.compatEnv ];

  # --------------------------------------------------------------- user
  # PipeWire is a session service; ears and voice follow it. ConditionUser
  # keeps them out of the greeter's session.

  systemd.user.services.jv-ears = {
    description = "Jarvis ears (wake word -> VAD -> ASR)";
    wantedBy = [ "default.target" ];
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
    unitConfig.ConditionUser = "ofek";
    environment = commonEnv;
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
}
