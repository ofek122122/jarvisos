# jv-notify-sound — the one arrival chime PLAN G8 asks for (blueprint §06:
# "Sound as UI. Three or four short, quiet, distinct cues"). Rendered from
# arithmetic at build time, the same discipline `pkgs/jarvis-wallpaper` uses
# for the desktop art: no binary .wav checked in, so the sound is reviewable
# as the two frequencies/durations/peak level in `tools/gen_notify_sound.py`
# rather than as an opaque file nobody can diff.
#
# This is deliberately its own package rather than a step inside jv-notify's
# own derivation: the generator has no QML/qmllint/Quickshell dependency at
# all, so giving it one build would tie a change to the sound's arithmetic to
# a full quickshell + qmllint rebuild for no reason. `pkgs/jv-notify` takes
# this package as an input and wires its one output path into the wrapper it
# already builds, the same shape `jv-wall` takes `jarvis-wallpaper`.
{
  lib,
  runCommand,
  python3,
}:
runCommand "jv-notify-sound"
  {
    nativeBuildInputs = [ python3 ];
    generator = ../../tools/gen_notify_sound.py;
  }
  ''
    mkdir -p $out/share/jv-notify-sound
    python3 $generator --out $out/share/jv-notify-sound/arrived.wav
  ''
