"""TurnTiming: where inside `think` the model actually started.

`jv tap --latency` measures `think` off the bus — the final transcript to
the first `speech.say` — and that span is the LLM plus a bus hop each way
plus whatever jv-brain's input worker was doing when the transcript
landed. Only jv-brain knows where the model's part of it begins, so it
states it. These tests pin WHEN it refuses to state it at all.
"""

from jv_brain.service import TurnTiming


def test_a_turn_that_never_reached_the_llm_has_no_model_span():
    t = TurnTiming()
    assert t.model_ms(100.0) is None


def test_one_completion_measures_from_when_the_request_went_out():
    t = TurnTiming()
    t.request(10.0)
    assert t.model_ms(10.25) == 250.0


def test_a_tool_turn_refuses_to_call_its_own_tool_time_the_model():
    """A turn that ran tools spends real time in jv-act between the first
    completion and the words the user hears. That time is inside `think`
    and it is not the LLM's, so there is no number to publish for it —
    a `model` gauge containing a confirm window is worse than none."""
    t = TurnTiming()
    t.request(10.0)   # completion 1: asked for a tool, said nothing
    t.request(12.0)   # completion 2: the one that speaks
    assert t.model_ms(12.5) is None
