"""AudioRecorder — buffering, against a fake stream standing in for
sounddevice.InputStream. No sound card involved: the fake calls the exact
callback signature PortAudio calls (indata, frames, time_info, status) and
the test asserts what stop() hands back."""

import numpy as np

from jv_dictate.audio import AudioRecorder


class FakeStream:
    def __init__(self, callback):
        self.callback = callback
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        pass

    def close(self):
        self.closed = True


def make_recorder():
    made = {}

    def factory(callback):
        made["stream"] = FakeStream(callback)
        return made["stream"]

    return AudioRecorder(stream_factory=factory), made


def test_stop_without_a_prior_start_returns_an_empty_int16_array():
    rec, _ = make_recorder()
    out = rec.stop()
    assert out.dtype == np.int16
    assert out.tolist() == []


def test_buffers_every_callback_in_order():
    rec, made = make_recorder()
    rec.start()
    cb = made["stream"].callback
    cb(np.array([[1], [2], [3]], dtype=np.int16), 3, None, None)
    cb(np.array([[4], [5]], dtype=np.int16), 2, None, None)
    out = rec.stop()
    assert out.tolist() == [1, 2, 3, 4, 5]


def test_stop_actually_stops_and_closes_the_stream():
    rec, made = make_recorder()
    rec.start()
    stream = made["stream"]
    rec.stop()
    assert stream.closed


def test_a_second_recording_starts_from_an_empty_buffer():
    rec, made = make_recorder()
    rec.start()
    made["stream"].callback(np.array([[7]], dtype=np.int16), 1, None, None)
    rec.stop()

    rec.start()
    out = rec.stop()
    assert out.tolist() == [], "leftover audio from the first recording leaked into the second"


def test_multichannel_input_keeps_only_the_first_channel():
    # dtype="int16", channels=1 is what this asks sounddevice for, but the
    # buffering code itself only promises to take column 0 — worth pinning
    # so a future change to the stream's channel count fails here first.
    rec, made = make_recorder()
    rec.start()
    made["stream"].callback(np.array([[1, 100], [2, 200]], dtype=np.int16), 2, None, None)
    out = rec.stop()
    assert out.tolist() == [1, 2]
