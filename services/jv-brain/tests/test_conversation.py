"""Conversation trimming must be BATCHED, not one-message-per-add.

The 2026-09-15 latency measurements showed why: llama-server reuses the
KV cache only for an unchanged prompt PREFIX. The old deque behavior
dropped one message per add once at the cap, shifting the prefix every
single turn — every turn re-prefilled the whole history (10 s for 1400
tokens on the 1660). Trimming in one batch down to a target keeps the
prefix stable for many turns between trims.
"""

import dataclasses

from jv_brain.config import BrainConfig
from jv_brain.service import Conversation


def cfg(**overrides) -> BrainConfig:
    base = BrainConfig()
    return dataclasses.replace(base, **overrides)


def fill(conv: Conversation, n: int, size: int = 100) -> None:
    """n alternating user/assistant messages of `size` chars each."""
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        conv.add_raw({"role": role, "content": ("m%03d" % i).ljust(size, "x")})


def total_chars(conv: Conversation) -> int:
    return sum(len(m.get("content") or "") for m in conv.messages)


def test_char_overflow_trims_in_one_batch_to_target():
    c = cfg(max_context_chars=1_000, trim_target_chars=600, max_turns=100)
    conv = Conversation(c)
    fill(conv, 11)  # 1100 chars — crosses the cap
    assert total_chars(conv) <= 600


def test_prefix_is_stable_between_trims():
    """After one trim, further adds must NOT shift the front of the
    context until the cap is crossed again — that stability is what
    makes the llama-server prompt cache hit."""
    c = cfg(max_context_chars=1_000, trim_target_chars=600, max_turns=100)
    conv = Conversation(c)
    fill(conv, 11)  # forces the batched trim
    head_after_trim = conv.messages[0]["content"]
    # room for ~3 more 100-char messages before the next overflow
    fill(conv, 3)
    assert conv.messages[0]["content"] == head_after_trim


def test_trimmed_context_starts_on_a_user_message():
    """Never hand the model a context that opens mid-exchange with an
    assistant (or tool) message."""
    c = cfg(max_context_chars=1_000, trim_target_chars=600, max_turns=100)
    conv = Conversation(c)
    fill(conv, 11)
    assert conv.messages[0]["role"] == "user"


def test_turn_cap_is_also_batched():
    c = cfg(max_context_chars=10**9, trim_target_chars=10**9, max_turns=4)
    conv = Conversation(c)
    fill(conv, 9, size=10)  # 9 messages > 4*2
    assert len(conv.messages) <= 5  # batched well below the cap, not 8
    head = conv.messages[0]["content"]
    fill(conv, 2, size=10)
    assert conv.messages[0]["content"] == head  # stable until next overflow


def test_repair_open_tool_calls_answers_only_the_unanswered():
    """A turn cancelled mid-tool (barge-in) leaves an assistant tool_calls
    message whose result never came. A chat template needs one result per
    call, so the NEXT request would be malformed — the conversation would
    be poisoned for the rest of the session, by an interruption."""
    conv = Conversation(cfg())
    conv.add_raw({"role": "user", "content": "do two things"})
    conv.add_raw(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "a", "type": "function",
                 "function": {"name": "t", "arguments": "{}"}},
                {"id": "b", "type": "function",
                 "function": {"name": "t", "arguments": "{}"}},
            ],
        }
    )
    conv.add_raw({"role": "tool", "tool_call_id": "a", "content": "{}"})

    assert conv.repair_open_tool_calls('{"ok": false, "error": "interrupted"}') == 1
    last = conv.messages[-1]
    assert last["role"] == "tool" and last["tool_call_id"] == "b"
    assert "interrupted" in last["content"]
    # every call now has exactly one result
    ids = [m["tool_call_id"] for m in conv.messages if m.get("role") == "tool"]
    assert sorted(ids) == ["a", "b"]


def test_repair_open_tool_calls_is_a_noop_when_every_call_was_answered():
    conv = Conversation(cfg())
    conv.add_raw({"role": "user", "content": "one thing"})
    conv.add_raw(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "a", "type": "function",
                 "function": {"name": "t", "arguments": "{}"}}
            ],
        }
    )
    conv.add_raw({"role": "tool", "tool_call_id": "a", "content": "{}"})
    before = list(conv.messages)
    assert conv.repair_open_tool_calls("{}") == 0
    assert list(conv.messages) == before


def test_repair_open_tool_calls_leaves_a_plain_conversation_alone():
    conv = Conversation(cfg())
    conv.add_raw({"role": "user", "content": "hello"})
    conv.add_raw({"role": "assistant", "content": "hi"})
    assert conv.repair_open_tool_calls("{}") == 0
    assert len(conv.messages) == 2
