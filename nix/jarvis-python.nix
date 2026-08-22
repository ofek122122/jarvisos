# Python environments for the jv-* services, built from the repo's own
# pyproject packages + two PyPI packages nixpkgs lacks.
#
# BUILD-UNTESTED WARNING (DECISIONS-pending.md): authored on Windows
# where nix cannot run; `nix flake check` in CI validates evaluation
# only. First `nixos-rebuild build` on the machine (or a Linux box)
# verifies the builds — expect at most small fixups here, nowhere else.
{ pkgs }:
let
  py = pkgs.python3;

  espeakng-loader = py.pkgs.buildPythonPackage rec {
    pname = "espeakng_loader";
    version = "0.2.4";
    format = "wheel";
    src = py.pkgs.fetchPypi {
      inherit pname version format;
      dist = "py3";
      python = "py3";
      abi = "none";
      platform = "manylinux_2_17_x86_64.manylinux2014_x86_64";
      hash = "sha256-CHIbryfRPUYfa+bu2aZSd+cNaCNP9IT9i5iXsiLNy20=";
    };
    nativeBuildInputs = [ pkgs.autoPatchelfHook ];
    buildInputs = [ pkgs.stdenv.cc.cc.lib ];
  };

  piper-tts = py.pkgs.buildPythonPackage rec {
    pname = "piper_tts";
    version = "1.7.0";
    format = "wheel";
    src = py.pkgs.fetchPypi {
      inherit pname version format;
      dist = "cp39";
      python = "cp39";
      abi = "abi3";
      platform = "manylinux_2_17_x86_64.manylinux2014_x86_64.manylinux_2_28_x86_64";
      hash = "sha256-cq3GI7l3vbvfPW9r+I1m7afP4u6OeRmnSllSrLd6M54=";
    };
    nativeBuildInputs = [ pkgs.autoPatchelfHook ];
    buildInputs = [ pkgs.stdenv.cc.cc.lib ];
    # piper-tts 1.7.0 core runtime deps (requires_dist, minus extras):
    # onnxruntime + pathvalidate. espeakng-loader is used at runtime for
    # the espeak-ng data path. The VM dry run caught the missing
    # pathvalidate via pythonRuntimeDepsCheck.
    propagatedBuildInputs = [ py.pkgs.onnxruntime py.pkgs.pathvalidate espeakng-loader ];
    pythonImportsCheck = [ "piper" ];
  };

  openwakeword = py.pkgs.buildPythonPackage rec {
    pname = "openwakeword";
    version = "0.6.0";
    pyproject = true;
    src = py.pkgs.fetchPypi {
      inherit pname version;
      hash = "sha256-NoWNkPEYPjB0hVl6kSpOPDOEsU6pkj+D/q/658FWVWU=";
    };
    build-system = [ py.pkgs.setuptools ];
    # tflite-runtime is Linux-marker-required upstream but we run the
    # onnx inference path exclusively (same as CI on 3.11).
    pythonRemoveDeps = [ "tflite-runtime" ];
    nativeBuildInputs = [ py.pkgs.pythonRelaxDepsHook ];
    propagatedBuildInputs = with py.pkgs; [
      onnxruntime
      numpy
      scipy
      scikit-learn
      tqdm
      requests
    ];
    doCheck = false; # tests want model downloads
  };

  mkLocal = name: path: deps:
    py.pkgs.buildPythonPackage {
      pname = name;
      version = "0.1.0";
      pyproject = true;
      src = path;
      build-system = [ py.pkgs.setuptools ];
      propagatedBuildInputs = deps;
    };

  jarvis-bus = mkLocal "jarvis-bus" ../services/pylib [ py.pkgs.msgpack ];

  jv-ears = mkLocal "jv-ears" ../services/jv-ears (with py.pkgs; [
    jarvis-bus
    numpy
    onnxruntime
    openwakeword
    faster-whisper
    soundfile
    sounddevice
  ]);

  jv-voice = mkLocal "jv-voice" ../services/jv-voice (with py.pkgs; [
    jarvis-bus
    numpy
    scipy
    soundfile
    sounddevice
    piper-tts
  ]);

  jv-brain = mkLocal "jv-brain" ../services/jv-brain (with py.pkgs; [
    jarvis-bus
    httpx
  ]);

  jv-context = mkLocal "jv-context" ../services/jv-context (with py.pkgs; [
    jarvis-bus
    psutil
  ]);

  jv-guard = mkLocal "jv-guard" ../services/jv-guard (with py.pkgs; [
    jarvis-bus
    httpx
  ]);

  jv-compat = mkLocal "jv-compat" ../services/jv-compat [ jarvis-bus ];
in
{
  earsEnv = py.withPackages (_: [ jv-ears ]);
  voiceEnv = py.withPackages (_: [ jv-voice ]);
  brainEnv = py.withPackages (_: [ jv-brain ]);
  contextEnv = py.withPackages (_: [ jv-context ]);
  guardEnv = py.withPackages (_: [ jv-guard ]);
  compatEnv = py.withPackages (_: [ jv-compat ]);
  # NOTE: jv-act (Rust) is intentionally NOT built into any service env
  # here and NOT given a systemd unit — REVIEW-REQUIRED (invariant 3).
}
