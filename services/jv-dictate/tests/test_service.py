"""DictateService — the whole start -> record -> transcribe -> sink ->
heartbeat path, against fakes: no bus, no evdev, no microphone, no faster-
whisper. The one thing this suite cannot exercise is a real evdev event or
a real recording (see ops/ralph/HUMAN-VERIFY.md)."""

import numpy as np

from jv_dictate.audio import AudioRecorder
from jv_dictate.injector import FakeSink
from jv_dictate.ptt import PushToTalk
from jv_dictate.service import DictateService

TRIGGER = 99


class FakeBus:
    def __init__(self):
        self.published = []

    async def publish(self, topic, body):
        self.published.append((topic, body))


class StubTranscriber:
    def __init__(self, result=("", "en", 0.0)):
        self.result = result

    def transcribe(self, audio_i16):
        return self.result


def sync_executor(fn, *args):
    fn(*args)


def make_service(*, clock=None, transcript=("", "en", 0.0)):
    clock = clock or (lambda: 0.0)
    bus = FakeBus()
    made = {}

    def factory(callback):
        made["callback"] = callback
        return _FakeStream()

    recorder = AudioRecorder(stream_factory=factory)
    sink = FakeSink()
    ptt = PushToTalk(TRIGGER, clock=clock)
    transcriber = StubTranscriber(transcript)
    service = DictateService(
        bus, transcriber, recorder, sink, ptt, health_period_s=5.0, executor=sync_executor, clock=clock
    )
    return service, bus, sink, made


class _FakeStream:
    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


async def test_start_publishes_one_hello_heartbeat_with_recording_false():
    service, bus, _sink, _made = make_service()
    await service.start()
    assert len(bus.published) == 1
    topic, body = bus.published[0]
    assert topic == "sys.health"
    assert body["service"] == "jv-dictate"
    assert body["state"] == "ok"
    assert body["metrics"]["recording"] == 0.0


async def test_pressing_the_key_starts_recording_and_beats_recording_true():
    service, bus, _sink, made = make_service()
    await service.start()
    await service.on_key_event(TRIGGER, True)

    assert service.ptt.active
    _, body = bus.published[-1]
    assert body["metrics"]["recording"] == 1.0
    # the recorder is actually armed — a callback delivered now is captured
    made["callback"](np.array([[1], [2]], dtype=np.int16), 2, None, None)


async def test_releasing_the_key_transcribes_and_reaches_the_sink():
    service, bus, sink, made = make_service(transcript=("remind me to call my sister", "en", 0.9))
    await service.start()
    await service.on_key_event(TRIGGER, True)
    made["callback"](np.array([[1], [2], [3]], dtype=np.int16), 3, None, None)
    await service.on_key_event(TRIGGER, False)

    assert sink.calls == ["remind me to call my sister"]
    assert not service.ptt.active
    _, body = bus.published[-1]
    assert body["metrics"]["recording"] == 0.0


async def test_silence_produces_no_text_and_sends_nothing():
    service, bus, sink, made = make_service(transcript=("", "en", 0.0))
    await service.start()
    await service.on_key_event(TRIGGER, True)
    await service.on_key_event(TRIGGER, False)
    assert sink.calls == []


async def test_expiry_force_stops_and_still_transcribes_what_was_captured():
    clock = {"t": 0.0}
    service, bus, sink, made = make_service(clock=lambda: clock["t"], transcript=("hello", "en", 0.5))
    await service.start()
    await service.on_key_event(TRIGGER, True)
    made["callback"](np.array([[9]], dtype=np.int16), 1, None, None)

    clock["t"] = PushToTalk.MAX_RECORDING_S
    await service.poll_expiry()

    assert not service.ptt.active
    assert sink.calls == ["hello"]


async def test_poll_expiry_is_a_no_op_while_nothing_is_recording():
    service, bus, sink, _made = make_service()
    await service.start()
    before = len(bus.published)
    await service.poll_expiry()
    assert len(bus.published) == before
    assert sink.calls == []


async def test_maybe_beat_is_quiet_before_the_period_elapses():
    clock = {"t": 0.0}
    service, bus, _sink, _made = make_service(clock=lambda: clock["t"])
    await service.start()
    clock["t"] = 1.0
    await service.maybe_beat()
    assert len(bus.published) == 1


async def test_maybe_beat_fires_once_a_full_period_has_elapsed():
    clock = {"t": 0.0}
    service, bus, _sink, _made = make_service(clock=lambda: clock["t"])
    await service.start()
    clock["t"] = 5.0
    await service.maybe_beat()
    assert len(bus.published) == 2
