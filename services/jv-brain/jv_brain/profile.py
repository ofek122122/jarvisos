"""User profile — Jarvis's memory of WHO its user is. This is user DATA,
not Jarvis identity: it lives in the state dir, never in personality/,
never committed. Structured as a seed for the Phase 4 semantic store
(blueprint §05): every fact carries its own evidence-ish metadata.

Nothing about the user is hardcoded anywhere. Out of the box this file
does not exist, and Jarvis knows it hasn't met anyone yet.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[3]

SCHEMA_VERSION = 1

# The follow-up basics that trickle in over the first sessions (NOT asked
# at first boot). Data-driven so the set is easy to change.
SEED_PENDING_QUESTIONS = [
    {"id": "rhythm", "prompt": "Are you more of a morning person or a night owl?"},
    {"id": "machine_use", "prompt": "What do you mostly use this machine for?"},
    {"id": "formality", "prompt": "Do you like me brief and formal, or loose and casual?"},
]


def default_profile_path() -> Path:
    if env := os.environ.get("JARVIS_STATE_DIR"):
        return Path(env) / "brain" / "profile.json"
    if sys.platform != "win32":
        return Path("/var/lib/jarvis/brain/profile.json")
    return REPO / ".state" / "brain" / "profile.json"


@dataclasses.dataclass
class Fact:
    value: str
    kind: str  # name | pronunciation | preference | routine | ...
    confidence: float
    first_seen: str
    last_confirmed: str
    source: str  # onboarding | correction | inferred


@dataclasses.dataclass
class Profile:
    path: Path
    schema_version: int = SCHEMA_VERSION
    facts: dict = dataclasses.field(default_factory=dict)
    pending_questions: list = dataclasses.field(default_factory=list)
    onboarding_complete: bool = False

    # ---------------------------------------------------------- lifecycle

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Profile":
        path = path or default_profile_path()
        if not path.exists():
            # Fresh install: no user known yet. Seed the trickle list.
            return cls(
                path=path,
                pending_questions=[dict(q) for q in SEED_PENDING_QUESTIONS],
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            path=path,
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            facts=data.get("facts", {}),
            pending_questions=data.get("pending_questions", []),
            onboarding_complete=data.get("onboarding_complete", False),
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.schema_version,
            "facts": self.facts,
            "pending_questions": self.pending_questions,
            "onboarding_complete": self.onboarding_complete,
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def exists(self) -> bool:
        return self.path.exists()

    @staticmethod
    def reset(path: Optional[Path] = None) -> bool:
        """Delete the profile file. Returns True if one was removed."""
        path = path or default_profile_path()
        if path.exists():
            path.unlink()
            return True
        return False

    # -------------------------------------------------------------- facts

    def set_fact(self, fact_id: str, value: str, kind: str, now: str, source: str) -> None:
        """Insert or update a fact. A correction is just a re-set: it
        keeps first_seen and bumps last_confirmed."""
        existing = self.facts.get(fact_id)
        first_seen = existing["first_seen"] if existing else now
        self.facts[fact_id] = dataclasses.asdict(
            Fact(
                value=value,
                kind=kind,
                confidence=0.95,
                first_seen=first_seen,
                last_confirmed=now,
                source=source,
            )
        )

    def get_value(self, fact_id: str) -> Optional[str]:
        f = self.facts.get(fact_id)
        return f["value"] if f else None

    @property
    def name(self) -> Optional[str]:
        return self.get_value("name")

    # ------------------------------------------------- pending questions

    def pop_pending(self) -> Optional[dict]:
        return self.pending_questions.pop(0) if self.pending_questions else None

    def render_about_user(self) -> str:
        """The 'About your user' block injected into the system prompt.
        When empty, it explicitly says Jarvis hasn't met anyone yet —
        that's what makes the first-boot self-introduction honest."""
        if not self.name:
            return (
                "You have not met your user yet. You do not know their name "
                "or anything about them. You will learn as you go."
            )
        lines = [f"Your user's name is {self.name}."]
        if (pron := self.get_value("pronunciation")):
            lines.append(f"Pronounce it: {pron}.")
        for fid, f in self.facts.items():
            if fid in ("name", "pronunciation"):
                continue
            lines.append(f"- {f['kind']}: {f['value']}")
        lines.append(
            "This is what you've learned so far; you keep learning, and you "
            "can be corrected at any time."
        )
        return "\n".join(lines)
