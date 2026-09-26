"""The Sink seam (docs/optimization-backlog.md R11): FakeSink is what the
rest of this suite tests against, LogSink is the whole of production until
PLAN F5's jv-act tool exists."""

from jv_dictate.injector import FakeSink, LogSink


def test_fake_sink_remembers_every_call_in_order():
    sink = FakeSink()
    sink.type_text("hello")
    sink.type_text("world")
    assert sink.calls == ["hello", "world"]


def test_log_sink_never_raises_and_names_the_text(capsys):
    LogSink().type_text("remind me to call my sister")
    out = capsys.readouterr().out
    assert "remind me to call my sister" in out
    assert "jv-dictate" in out
