"""The codec every body on the bus goes through (PLAN B60).

`to_body` and `from_body` are eleven lines each and they encode and decode
EVERY body on this bus, in every Python service, on every topic. Until this
file there was one test on them — `test_to_body_wire_rules`, on an
`AudioWake`, whose `_optional` set is empty and which has no nested field and
no array: the one body in the frozen set that exercises none of the rules.
Nine mutations were graded against the pylib suite before this file existed
and NINE SURVIVED. One of them (an absent key stopping being a default) was
caught by jv-context's suite, incidentally, because that suite happens to
decode a `context.system` body with `battery_pct` missing. The other eight
were held by nothing in the repository.

That matters more here than in a service. A survivor in jv-voice is wrong in
jv-voice; a survivor here is wrong in eight services and on every topic at
once, and the failures it produces are not local — a body that omits a
required key is rejected by the broker's schema on some other machine's
consumer, and a nested dataclass left unconverted is a `msgpack` TypeError
inside `publish`, thrown by the transport rather than by the code that built
the frame.

Three tests below read `schemas/*.json` rather than restating it. That is
the B55 shape: the frozen schema is the law (invariant 2) and the codec's
whole job is to agree with it, so the assertion is a RELATION between the
generated bindings and the JSON — nothing here imports a service, and the
schema files are read, never run. `services/pylib/jarvis_bus/schema.py` is
itself generated from those files by `tools/gen_bindings.py`, and the codec
is the hand-written epilogue that the generator copies in verbatim.
"""

import dataclasses
import json
from pathlib import Path

import msgpack
import pytest

from jarvis_bus.schema import (
    AudioTranscript,
    AudioTranscriptWord,
    AudioWake,
    BrainResponse,
    BrainResponseInReplyTo,
    GuardVerdict,
    SpeechSay,
    SpeechState,
    from_body,
    to_body,
)

REPO = Path(__file__).resolve().parents[3]
SCHEMAS = REPO / "schemas"


def frozen_schema(cls) -> dict:
    """The JSON this binding was generated from, by topic."""
    return json.loads((SCHEMAS / f"{cls.TOPIC}.json").read_text(encoding="utf-8"))


# One instance per shape the codec has a branch for. Nothing here is a
# fixture: each test says which shape it is about.
MINIMAL_SAY = SpeechSay(text="hello", say_id="s-1", in_reply_to_utterance=None)
MINIMAL_STATE = SpeechState(state="idle")
FULL_TRANSCRIPT = AudioTranscript(
    kind="final",
    utterance_id="u-1",
    text="what time is it",
    lang="en",
    t0=0.0,
    t1=1.25,
    words=[
        AudioTranscriptWord(w="what", t0=0.0, t1=0.3, p=0.98),
        AudioTranscriptWord(w="time", t0=0.3, t1=0.6),  # p omitted
    ],
)
NESTED_RESPONSE = BrainResponse(
    text="just after nine",
    finish_reason="stop",
    in_reply_to=BrainResponseInReplyTo(src="jv-ears", seq=7),
    latency_ms=812.0,
)
SCALAR_ARRAY_VERDICT = GuardVerdict(
    sha256="a" * 64, verdict="clean", reasons=["signed", "known_publisher"]
)

WIRE_BODIES = [MINIMAL_SAY, MINIMAL_STATE, FULL_TRANSCRIPT, NESTED_RESPONSE, SCALAR_ARRAY_VERDICT]


# --- to_body: what goes on the wire ----------------------------------------


@pytest.mark.parametrize("obj", WIRE_BODIES, ids=lambda o: type(o).__name__)
def test_every_key_to_body_emits_is_a_property_its_frozen_schema_declares(obj):
    """Every body schema is `additionalProperties: false`. A key the codec
    invents — a `ClassVar` that stopped being one, a field name the generator
    spells differently from the JSON — is not a mislabelled frame, it is a
    frame the schema rejects outright.
    """
    declared = set(frozen_schema(type(obj))["properties"])
    emitted = set(to_body(obj))
    assert emitted <= declared, f"not in schemas/{type(obj).TOPIC}.json: {emitted - declared}"


@pytest.mark.parametrize("obj", WIRE_BODIES, ids=lambda o: type(o).__name__)
def test_the_topic_and_version_constants_never_reach_the_wire(obj):
    """`TOPIC` and `V` live on the class as `ClassVar`s, which is exactly why
    `dataclasses.fields()` does not return them. They belong to the ENVELOPE
    (`topic`, `v`), and a copy of either inside the body would be a second
    source of truth for the one thing the broker routes on.
    """
    body = to_body(obj)
    assert "TOPIC" not in body and "V" not in body


@pytest.mark.parametrize("obj", WIRE_BODIES, ids=lambda o: type(o).__name__)
def test_every_required_key_survives_to_body_even_when_its_value_is_null(obj):
    """THE FIRST RULE, and the one with the sharpest edge. `in_reply_to_utterance`
    is required AND nullable (`speech.say.json`: `"type": ["string", "null"]`) —
    a system announcement has no triggering utterance and must say so with a
    null, not by omission. A codec that omitted every None would publish a
    `speech.say` the schema rejects for a missing required key, and it would
    do it only for unprompted speech: the proactivity path, which is the one
    that runs when nobody is watching.
    """
    required = set(frozen_schema(type(obj))["required"])
    body = to_body(obj)
    assert required <= set(body), f"required and missing: {required - set(body)}"


@pytest.mark.parametrize("obj", WIRE_BODIES, ids=lambda o: type(o).__name__)
def test_a_null_on_the_wire_is_only_ever_a_key_the_schema_lets_be_null(obj):
    """THE SECOND RULE, which is the first one's mirror. Optional keys are
    declared with a bare type (`"type": "string"`), so an explicit null in one
    is a validation failure — "absent" and "present and null" are different
    words on this bus, and `to_body` is where the difference is made.
    """
    props = frozen_schema(type(obj))["properties"]
    for key, value in to_body(obj).items():
        if value is None:
            allowed = props[key].get("type")
            types = allowed if isinstance(allowed, list) else [allowed]
            assert "null" in types, (
                f"{type(obj).TOPIC}.{key} was published as null, but the frozen "
                f"schema declares it {allowed!r} — omit it instead"
            )


def test_an_optional_field_left_unset_is_absent_rather_than_null():
    """The same rule stated once without the schema, because this is the
    assertion a reader of `to_body` needs: the minimal `speech.state` frame
    is one key wide.
    """
    assert to_body(MINIMAL_STATE) == {"state": "idle"}


def test_the_omit_rule_applies_inside_a_nested_object_too():
    """`AudioTranscriptWord.p` is optional and `words[1]` does not have one.
    The recursion is a separate call, so the rule holds in the nested body
    only because the recursion goes through `to_body` and not through
    `dataclasses.asdict` — which would emit `"p": null` and, being the
    obvious one-line simplification of this function, is the change this
    test exists to stop.
    """
    words = to_body(FULL_TRANSCRIPT)["words"]
    assert words[0]["p"] == pytest.approx(0.98)
    assert "p" not in words[1]


@pytest.mark.parametrize("obj", WIRE_BODIES, ids=lambda o: type(o).__name__)
def test_a_body_is_msgpack_packable_which_is_the_real_reason_to_recurse(obj):
    """Nested dataclasses and arrays of them must become dicts, and the
    consequence of not doing it is not a mislabelled frame: `msgpack.packb`
    cannot serialise a dataclass, so `BusClient.publish` raises TypeError
    from inside the transport, on a frame the calling code built correctly.
    Packing with the client's own options is the whole claim.
    """
    msgpack.packb(to_body(obj), use_bin_type=True)


def test_a_nested_dataclass_becomes_a_plain_dict():
    assert to_body(NESTED_RESPONSE)["in_reply_to"] == {"src": "jv-ears", "seq": 7}


def test_an_array_of_dataclasses_becomes_an_array_of_dicts():
    words = to_body(FULL_TRANSCRIPT)["words"]
    assert words == [
        {"w": "what", "t0": 0.0, "t1": 0.3, "p": 0.98},
        {"w": "time", "t0": 0.3, "t1": 0.6},
    ]


def test_an_array_of_scalars_passes_through_untouched():
    """`guard.verdict.reasons` is an array of strings. The list branch asks
    each ITEM whether it is a dataclass; a branch that assumed every array
    was an array of objects would raise TypeError on the first string —
    `dataclasses.fields("signed")` — in `jv-guard`, on the topic whose whole
    job is to refuse an untrusted binary (invariant 8).
    """
    assert to_body(SCALAR_ARRAY_VERDICT)["reasons"] == ["signed", "known_publisher"]


# --- from_body: what a consumer gets ---------------------------------------


def test_a_key_absent_from_the_body_leaves_the_dataclass_default():
    """Invariant 4's other half — "consumers must handle missing input". The
    codec's answer is that an absent optional key is not decoded at all, so
    the dataclass default (None) stands. Indexing the body instead would
    raise KeyError in the consumer for a frame that is perfectly valid, which
    is most frames: almost every optional key in the frozen set is usually
    absent.
    """
    state = from_body(SpeechState, {"state": "idle"})
    assert state.state == "idle"
    assert state.say_id is None
    assert state.reason is None


def test_a_nested_object_is_decoded_through_its_optional_wrapper():
    """`in_reply_to` is typed `Optional[BrainResponseInReplyTo]`, and
    `dataclasses.is_dataclass(Optional[X])` is False — so without the Union
    unwrap the field arrives as a raw dict and every consumer that reads
    `resp.in_reply_to.seq` gets AttributeError. That field is how a reply is
    tied back to the frame that caused it, which is what `jv tap --latency`
    and jv-memory's turn stitching are built on.
    """
    decoded = from_body(BrainResponse, to_body(NESTED_RESPONSE))
    assert isinstance(decoded.in_reply_to, BrainResponseInReplyTo)
    assert decoded.in_reply_to.src == "jv-ears"
    assert decoded.in_reply_to.seq == 7


def test_an_explicit_null_nested_object_stays_none_instead_of_exploding():
    """jarvisd validates the ENVELOPE and never the body (`proto.rs`:
    "Full body validation is deliberately not done here"), so `"in_reply_to":
    null` really can arrive — from a replay fixture, from `jv pub`, from any
    producer that spells absence as null. The `isinstance(v, dict)` guard is
    what turns that into a None field instead of a TypeError inside the
    consumer's decode.
    """
    decoded = from_body(BrainResponse, {"text": "hi", "finish_reason": "stop", "in_reply_to": None})
    assert decoded.in_reply_to is None


def test_an_array_of_objects_is_decoded_elementwise():
    """`Optional[List[AudioTranscriptWord]]` needs both the Union unwrap and
    the list branch, and nothing but word timings uses the shape today —
    which is exactly why it can rot unnoticed until the ASR starts emitting
    them.
    """
    decoded = from_body(AudioTranscript, to_body(FULL_TRANSCRIPT))
    assert [type(w) for w in decoded.words] == [AudioTranscriptWord, AudioTranscriptWord]
    assert decoded.words[1].w == "time"
    assert decoded.words[1].p is None


def test_a_key_the_binding_has_never_heard_of_is_ignored_and_not_fatal():
    """The forward-compatibility half of the envelope's `v`. `from_body`
    iterates over the dataclass's FIELDS, not over the body's keys, so a v2
    producer that adds a key does not crash a v1 consumer — it is ignored,
    and a consumer that cares reads `v` and hedges (HealthState already
    refuses a `v` it does not know). Passing the body through instead would
    raise TypeError on an unexpected keyword and take down every Python
    consumer on that topic the moment a migration began.
    """
    decoded = from_body(SpeechState, {"state": "speaking", "listen_id": "not-in-v1"})
    assert decoded.state == "speaking"
    assert not hasattr(decoded, "listen_id")


def test_a_body_missing_a_required_key_fails_loudly_at_the_decode():
    """The other direction, and it must NOT be lenient. A required key is
    required because consumers may not check it; filling it with None here
    would push the failure into whatever reads the field, arbitrarily far
    from the malformed frame. The dataclass has no default for it, so the
    constructor is the check.
    """
    with pytest.raises(TypeError):
        from_body(SpeechSay, {"text": "hello"})  # no say_id, no in_reply_to_utterance


@pytest.mark.parametrize("obj", WIRE_BODIES, ids=lambda o: type(o).__name__)
def test_a_body_survives_the_round_trip_unchanged(obj):
    """Encode, decode, and get the same object — across a required null, an
    absent optional, a nested object and both kinds of array. Dataclass
    equality is field-by-field, so this is the one assertion in the file that
    is about the pair rather than about either function.
    """
    assert from_body(type(obj), to_body(obj)) == obj


def test_the_round_trip_goes_through_msgpack_and_not_just_through_python():
    """The wire is MessagePack, and the dict that comes back off it is not
    the dict that went in — every key is a fresh str, floats have been
    through a binary64 round trip and small ints may come back as a
    different width. The `AudioWake` round trip in test_client.py proves this
    for three scalars against a real broker; this proves it for the shapes
    that broker never sees in a test: a nested object and an array of them.
    """
    for obj in (FULL_TRANSCRIPT, NESTED_RESPONSE, MINIMAL_SAY):
        wire = msgpack.unpackb(msgpack.packb(to_body(obj), use_bin_type=True), raw=False)
        assert from_body(type(obj), wire) == obj


def test_the_codec_is_the_generators_epilogue_and_not_hand_written_here():
    """`schema.py` says DO NOT EDIT, and it means it: the codec these tests
    exercise is copied verbatim out of `tools/gen_bindings.py`, so a fix
    applied to the generated file is erased by the next regeneration and a
    fix applied only to the generator is not what any service imports. This
    is a read of the generator, not a run of it (invariant 1), and it exists
    so that whoever changes one of the two is told about the other.
    """
    generator = (REPO / "tools" / "gen_bindings.py").read_text(encoding="utf-8")
    codec = (REPO / "services" / "pylib" / "jarvis_bus" / "schema.py").read_text(encoding="utf-8")
    start = codec.index("def to_body(")
    assert codec[start:].strip() in generator, (
        "the codec in services/pylib/jarvis_bus/schema.py is no longer the "
        "PY_HELPERS text in tools/gen_bindings.py — the generated file was "
        "edited in place, and the next regeneration will silently undo it"
    )


def test_a_binding_with_no_optional_fields_still_declares_the_set():
    """`AudioWake._optional` is empty, and `to_body` reads it on every field
    of every body. A generator that emitted the ClassVar only when there was
    something in it would make the codec raise AttributeError on the highest
    -frequency topic in the system.
    """
    assert AudioWake._optional == frozenset()
    assert all(hasattr(type(o), "_optional") for o in WIRE_BODIES)
    assert all(
        hasattr(t, "_optional")
        for o in WIRE_BODIES
        for f in dataclasses.fields(o)
        for t in ([type(getattr(o, f.name))] if dataclasses.is_dataclass(getattr(o, f.name)) else [])
    )
