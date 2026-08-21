# PipeWire — the only audio stack. The far-field mic array lands here;
# jv-voice's filter-chain node (blueprint §06) plugs into this in Phase 1+.
{ ... }:
{
  security.rtkit.enable = true; # realtime priority for the audio graph

  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true; # Wine/Proton audio (Phase 2)
    pulse.enable = true;
  };

  services.pulseaudio.enable = false;
}
