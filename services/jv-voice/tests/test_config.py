"""The output device is the one piece of jv-voice's configuration another
service reads (PLAN A41).

`OutputPlate` on the HUD says OUTPUT MUTED by reading jv-context's view of
the DEFAULT SINK, and that the thing jv-voice plays into is that sink is an
assumption, not a fact — true only while nobody has pinned a device. So the
knob is not private: whether it is set is published in jv-voice's heartbeat
(`output_device_pinned`), and the HUD goes quiet rather than confidently
wrong the day it is. These tests pin the knob itself; test_player.py pins
what the player does with it, and test_voice_service.py the publishing.
"""

import pytest

from jv_voice.config import VoiceConfig


def test_no_device_is_configured_by_default(monkeypatch):
    monkeypatch.delenv("JARVIS_VOICE_OUTPUT_DEVICE", raising=False)
    assert VoiceConfig.load().output_device is None


def test_the_environment_pins_a_device(monkeypatch):
    monkeypatch.setenv("JARVIS_VOICE_OUTPUT_DEVICE", "alsa_output.usb-Focusrite")
    assert VoiceConfig.load().output_device == "alsa_output.usb-Focusrite"


@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_setting_is_not_a_device(monkeypatch, value):
    """A unit file that writes the variable unconditionally leaves it
    empty when nothing is configured. Empty must read as "unset" — the
    alternative is jv-voice reporting a pinned device it did not pin,
    which silences the HUD's plate for no reason at all."""
    monkeypatch.setenv("JARVIS_VOICE_OUTPUT_DEVICE", value)
    assert VoiceConfig.load().output_device is None
