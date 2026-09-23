"""SentenceChunker: turn a token stream into speakable sentences as early
as possible. This is what lets jv-brain hand piper the first sentence
while the LLM is still generating the rest (research 2026: streaming TTS
is non-negotiable for sub-second voice; split at sentence boundaries)."""

from jv_brain.service import SentenceChunker


def test_emits_each_complete_sentence_as_it_closes():
    c = SentenceChunker()
    assert c.push("Hello there. How ") == ["Hello there."]
    assert c.push("are you?") == []          # no trailing space yet
    assert c.flush() == "How are you?"


def test_no_split_without_following_space():
    """A period mid-token (a decimal, a filename) must not split until a
    real boundary — we only cut on terminator + whitespace."""
    c = SentenceChunker()
    assert c.push("The file is v1.2.txt and ") == []
    assert c.push("that is it. Done.") == ["The file is v1.2.txt and that is it."]
    assert c.flush() == "Done."


def test_newline_forces_a_break():
    c = SentenceChunker()
    assert c.push("First line\nsecond") == ["First line"]
    assert c.flush() == "second"


def test_flush_returns_none_when_empty():
    c = SentenceChunker()
    c.push("All done. ")
    # the sentence already emitted on push; nothing left
    assert c.push("All done. ") == ["All done."]
    assert c.flush() is None


def test_handles_bang_and_question():
    c = SentenceChunker()
    out = c.push("Wow! Really? Yes.")
    assert out == ["Wow!", "Really?"]
    assert c.flush() == "Yes."


def test_tiny_fragments_do_not_emit_alone():
    """A lone terminator or 1-2 char fragment shouldn't become its own
    utterance — piper on 'K.' sounds broken. Hold until it has substance."""
    c = SentenceChunker(min_chars=4)
    assert c.push("K. ") == []
    assert c.push("That works. ") == ["K. That works."]
