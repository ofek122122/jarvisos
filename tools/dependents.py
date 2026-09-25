#!/usr/bin/env python3
"""Name the suites that read what you just changed (PLAN B68).

The verify gate says "run the relevant test suite(s) for what you touched",
and for three iterations in a row that sentence was read by someone who could
not see the readers. B65 and B66 changed `services/jv-compat/jv_compat/` and
ran `runtests.sh jv-compat`; both were green, and both left `tools` red. A71
found it, fixed it, and committed the fix's 31 other files.

Nobody was careless. Invariant 1 forbids one service importing another, so
every claim this repo makes ABOUT A RELATION between two of its parts is made
by a THIRD suite that reads them both as source text: `tools` reads jv-compat's
installer, jv-guard's heuristics, jv-brain's prompts, jv-act's tool table, the
frozen schemas, `personality/theme.toml` and every QML file in the HUD. That
is not guessable from the directory you are editing, and writing it down in
prose is what had already failed.

So it is derived, every time, from the suites themselves.

THE RULE, whole: **a suite reads what it names, if what it names exists.**
Names are taken out of the syntax tree — `ROOT / "services" / "jv-compat"`,
`"services/jv-voice/jv_voice/service.py"`, `from jv_compat import fingerprint`
— and kept only when the repo really has that path. A path that changed is
read by a suite when the suite names it or any directory above it.

WHERE IT IS GENEROUS, deliberately. `(ROOT / "services").iterdir()` claims
every service, because the suite really does depend on what is in there and
this cannot tell which granularity was meant. The cost of naming one suite too
many is five seconds; the cost of missing one is a red commit that stands for
two days. WHERE IT IS NARROW, also deliberately: comments are not in the tree,
so the paragraph of prose above a test names nothing — and `Path(".")`, `".."`
and `"/etc"` are refused, because a candidate that resolves to the repo root
or outside it would claim everything and end with "run every suite", which is
the same as saying nothing.

AND THE SAME QUESTION IN QML (B69). `ops/ralph/qmltest.sh` and
`ops/ralph/hudshots.sh` are the strongest gates over `shell/jv-hud`, and the
rule above cannot find either: a QML file names its subject by TYPE
(`ReplyState {}`), never by path. But a QML type IS a file, and the engine
finds it two ways — the directories `import "..."` puts on the path, and the
`qmldir` those directories ship. So the gates are walked the way the engine
walks them, from the drivers outward, and a `core/` element three types below
the contact sheet is reached.

AND THE TWO GATES THAT ARE A NIX EVALUATION (B72). `ops/ralph/nixtest.sh` and
`ops/ralph/hudscreens.sh` read `.#nixosConfigurations.ares` and `.#jv-hud` —
flake attributes, not paths, so there is no syntax to walk. Those two are
DECLARED, in `DECLARED_GATES`, and the declaration is checked against the
`# reads:` header of the script it describes. One of them is not run for you,
and says so where the plan is printed rather than being left out in silence.

AND THE GATES THEMSELVES (B73). Every rule above walks from a suite OUTWARD
to the sources it reads, and none of them can walk to the script that does the
running: a QML gate is found from its entry directory and a bash file is not a
type on any import path; a Python suite cannot import `runtests.sh`. So the
one change most likely to break a gate — a change to the gate — was the one
change it could not see. Both are implicit reads now, the way `DECLARED_GATES`
already had it: a QML gate reads its own script, and `runtests.sh` is read by
every suite it can run, because it picks the interpreter, layers the venv and
sets the PYTHONPATH that decides which `jarvis_bus` all ten of them import.
`cargotest.sh` is the same rule for Rust and lives in `tools/verify.py`, with
the rest of the Rust half.

WHAT IT STILL CANNOT SEE. Rust. `services/jarvisd` and `services/jv-act` are
crates; their tests live inside the source they test and `cargotest.sh` takes
a crate name, so there is nothing to derive. That is printed as a standing
caveat, which is what this used to say about QML.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, Sequence

# The script every Python suite is RUN by, and the command that runs one.
# Split apart because the path is a read-set entry as well as a prefix: a
# suite cannot name its own runner, so the rule in `readers` puts it there
# (PLAN B73).
RUNTESTS_SH = "ops/ralph/runtests.sh"
RUNTESTS = f"bash {RUNTESTS_SH}"

# Punctuation a path picks up when it is quoted inside prose.
EDGES = "`'\",;:()[]{}<>*"

SKIP_DIRS = {".git", "__pycache__", "target", "result"}


@dataclasses.dataclass(frozen=True)
class Suite:
    """One `runtests.sh` argument, and every repo path its files name."""

    name: str
    tests: Path
    reads: frozenset[str]


def _warn(message: str) -> None:
    print(message, file=sys.stderr)


# ------------------------------------------------------------------- names


def _const_str(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _chain(node: ast.BinOp, consumed: set[int]) -> list[str] | None:
    """The constant segments of a `x / "a" / "b"` expression, left to right.

    Every node it used is marked consumed, so the sub-expression `x / "a"` is
    not ALSO reported: `ROOT / "services" / "jv-compat"` must claim one
    service and not all of them. A chain with a computed segment
    (`SHELL / name`) yields nothing and marks nothing — the constant part of
    it is a node of its own and gets its own turn.
    """
    segs: list[str] = []
    used: list[ast.AST] = []
    cur: ast.AST = node
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Div):
        if not _const_str(cur.right):
            return None
        if cur is not node:
            used.append(cur)
        segs.append(cur.right.value)  # type: ignore[attr-defined]
        used.append(cur.right)
        cur = cur.left
    if not segs:
        return None
    if _const_str(cur):
        segs.append(cur.value)  # type: ignore[attr-defined]
        used.append(cur)
    elif isinstance(cur, ast.Call) and cur.args and _const_str(cur.args[0]):
        # Path("docs") / "hud"
        segs.append(cur.args[0].value)  # type: ignore[attr-defined]
        used.append(cur.args[0])
    for n in used:
        consumed.add(id(n))
    return list(reversed(segs))


def _candidates(text: str) -> Iterable[str]:
    """Path-shaped readings of one plain string literal.

    A slash is required, and that is the one rule here earned by being wrong
    first: `assert ("tools" in warm)` in jv-brain's suite is a word that
    happens to be a directory in this repo, and reading it as a path made
    every edit to `tools/` name jv-brain. An expression built with `/` is a
    path by construction and needs no slash of its own (see `_chain`); a bare
    string has to look like one.

    The literal whole, plus every slashed token inside it — because
    `test_mutate.py` feeds the harness multi-line specs whose first line is a
    path, and a spec that names a file is a suite that reads it.
    """
    if len(text) > 4096:
        return
    whole = text.strip()
    if "/" in whole:
        yield whole
    for tok in text.split():
        tok = tok.strip(EDGES)
        if "/" in tok:
            yield tok


def _resolve(root: Path, candidate: str) -> str | None:
    """`candidate` as a repo-relative path that exists, or nothing.

    Refuses the readings that would claim the whole repository: empty, `.`,
    anything with a `..` in it, and anything absolute. `/etc` is a real
    directory and `<root>/etc` is not the same claim.
    """
    if not candidate or candidate.startswith("/") or "\\" in candidate:
        return None
    if "\n" in candidate or len(candidate) > 256:
        return None
    parts = [p for p in candidate.split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        return None
    rel = "/".join(parts)
    try:
        if not (root / rel).exists():
            return None
    except (OSError, ValueError):
        return None
    return rel


def _package_bases(root: Path) -> list[str]:
    """Where a top-level importable name can live in this repo: beside the
    suites (`tools/mutate.py`), in a service (`services/pylib/jarvis_bus`),
    or at the root."""
    bases = ["", "tools", "harness"]
    services = root / "services"
    if services.is_dir():
        bases += sorted(f"services/{d.name}" for d in services.iterdir() if d.is_dir())
    return bases


def _module_path(root: Path, top: str, bases: Sequence[str]) -> str | None:
    """The file or package directory a bare `import <top>` would read here.

    Nothing for `json` or `pytest` — this asks the repo, not the interpreter,
    so a name it does not own is simply not a dependency.

    Resolved in TWO passes, because `<top>/` with no `__init__.py` is still a
    module (PEP 420) and `services/jv-ears/jv_ears` is this repo's one of
    those — setuptools ships it regardless, its pyproject discovery defaulting
    to `namespaces = true`, so nothing ever complained. Asking only for
    `__init__.py` made `import jv_ears` resolve to NOTHING: the closure walk
    stopped at the first edge and a change to that package planned every gate
    except the 136-test suite that runs it (PLAN B86, and it is B68 with the
    roles reversed).

    Two passes and not one, because such a directory is a namespace *portion*
    and the interpreter does not stop at it either — it remembers it, keeps
    searching the rest of the path, and lets a real package or a plain module
    found anywhere later win. Resolving eagerly, on the accident of which base
    is listed first, would aim an import at source Python does not read: a
    wrong suite, which is worse than none.

    NARROWER than the interpreter in one place: any directory at all is a
    portion to Python, and a portion is taken here only when it has Python
    UNDER it — which is to say, only when `_module_files` would find the
    resolution something to read. A stray `import docs` must not claim every
    PNG in the repo, because this tool's one forbidden answer is "run every
    suite". Not narrower than that, though: `*.py` directly inside would have
    refused the shape namespace packages are usually FOR, a `foo/` whose only
    modules are in `foo/bar/`, and refusing costs a missed reader.
    """
    if not top or not top.isidentifier():
        return None
    for base in bases:
        stem = f"{base}/{top}" if base else top
        if (root / stem / "__init__.py").exists():
            return stem
        if (root / f"{stem}.py").exists():
            return f"{stem}.py"
    for base in bases:
        stem = f"{base}/{top}" if base else top
        if (root / stem).is_dir() and _module_files(root, stem):
            return stem
    return None


def _module_files(root: Path, rel: str) -> list[Path]:
    """The files a resolved import actually brings in. A package is taken
    whole: `from jv_ears.audio import X` runs one module of it, `import
    jv_ears` runs another, and this cannot tell which — so it reads all of
    them, on the same generous side as everything else here."""
    p = root / rel
    if p.is_dir():
        return [f for f in sorted(p.rglob("*.py")) if not SKIP_DIRS & set(f.parts)]
    return [p] if p.is_file() else []


def _imported_tops(tree: ast.AST) -> list[str]:
    tops: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tops += [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            tops.append(node.module.split(".")[0])
    return tops


def _closure(
    root: Path,
    rel: str,
    bases: Sequence[str],
    cache: dict[str, frozenset[str]],
    warn: Callable[[str], None],
) -> frozenset[str]:
    """An imported module, plus everything it imports from inside this repo.

    This is the reading `jv-ears` needed. Its suite names `jarvis_bus`
    nowhere — but it imports `jv_ears`, and `jv_ears/main.py` imports the bus
    client, so a change to the codec runs in that suite and can turn it red.
    Only IMPORTS are followed, never the paths a file merely names: a suite
    reading jv-compat's source as TEXT does not thereby depend on what
    jv-compat imports.
    """
    if rel in cache:
        return cache[rel]
    cache[rel] = frozenset({rel})  # breaks an import cycle at its first edge
    out = {rel}
    for f in _module_files(root, rel):
        try:
            tree = ast.parse(f.read_text("utf-8", errors="replace"))
        except SyntaxError as exc:
            warn(
                f"dependents: cannot read {f.relative_to(root).as_posix()} "
                f"({exc.msg}, line {exc.lineno}) — what it imports is unknown"
            )
            continue
        for top in _imported_tops(tree):
            target = _module_path(root, top, bases)
            if target and target not in out:
                out |= _closure(root, target, bases, cache, warn)
    cache[rel] = frozenset(out)
    return cache[rel]


def names(
    root: Path,
    py: Path,
    warn: Callable[[str], None] | None = None,
    *,
    bases: Sequence[str] | None = None,
    cache: dict[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """Every repo path one Python file names — by expression, string or import."""
    if warn is None:
        warn = _warn
    if bases is None:
        bases = _package_bases(root)
    if cache is None:
        cache = {}
    try:
        tree = ast.parse(py.read_text("utf-8", errors="replace"))
    except SyntaxError as exc:
        try:
            shown = py.relative_to(root).as_posix()
        except ValueError:
            shown = str(py)
        warn(
            f"dependents: cannot read {shown} ({exc.msg}, line {exc.lineno}) — "
            "the suites that read it are unknown, not none"
        )
        return frozenset()

    out: set[str] = set()
    consumed: set[int] = set()
    for node in ast.walk(tree):
        if id(node) in consumed:
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            segs = _chain(node, consumed)
            if segs is not None:
                rel = _resolve(root, "/".join(segs))
                if rel:
                    out.add(rel)
                continue
        if _const_str(node):
            for cand in _candidates(node.value):  # type: ignore[attr-defined]
                rel = _resolve(root, cand)
                if rel:
                    out.add(rel)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for top in _imported_tops(node):
                rel = _module_path(root, top, bases)
                if rel:
                    out |= _closure(root, rel, bases, cache, warn)
    return frozenset(out)


# ------------------------------------------------------------------ suites


def suites(root: Path, warn: Callable[[str], None] | None = None) -> list[Suite]:
    """Every Python suite `runtests.sh` can run, with what each one reads.

    Discovered, not listed: a `tests/` directory one or two levels down that
    holds at least one `test_*.py`. That last clause is what drops
    `services/jarvisd/tests` and `services/jv-act/tests`, which are Rust.
    """
    bases = _package_bases(root)
    cache: dict[str, frozenset[str]] = {}
    out: list[Suite] = []
    for tests in sorted({*root.glob("*/tests"), *root.glob("*/*/tests")}):
        if not tests.is_dir() or SKIP_DIRS & set(tests.parts):
            continue
        pys = [
            p
            for p in sorted(tests.rglob("*.py"))
            if not SKIP_DIRS & set(p.parts)
        ]
        if not any(p.name.startswith("test_") for p in pys):
            continue
        reads: set[str] = set()
        for p in pys:
            reads |= names(root, p, warn, bases=bases, cache=cache)
        out.append(Suite(tests.parent.name, tests, frozenset(reads)))
    return out


def is_read(reads: Iterable[str], path: str) -> bool:
    """Does this read-set cover `path` — by naming it, or a directory above it?"""
    return any(path == r or path.startswith(r + "/") for r in reads)


def _expand(root: Path, given: str) -> list[str]:
    """One given path as the repo-relative files it stands for.

    A directory becomes its files, because `git status` reports an untracked
    directory as a single entry and the suites name what is inside it. A path
    that no longer exists is kept as it is: a deletion is a change, and the
    directory the suite named above it is still there.
    """
    p = Path(given)
    if p.is_absolute():
        try:
            rel = p.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return []
    else:
        rel = "/".join(part for part in p.as_posix().split("/") if part not in ("", "."))
    if not rel:
        return []
    target = root / rel
    if target.is_dir():
        return [
            f.relative_to(root).as_posix()
            for f in sorted(target.rglob("*"))
            if f.is_file() and not SKIP_DIRS & set(f.relative_to(root).parts)
        ]
    return [rel]


def readers(
    root: Path,
    paths: Iterable[str],
    *,
    exclude: Iterable[str] = (),
    warn: Callable[[str], None] | None = None,
) -> dict[str, list[str]]:
    """Suite name -> the changed paths it reads. Empty when nobody reads them.

    Every suite also reads `runtests.sh`, which is not a path any of them
    NAMES — a suite cannot import the script that runs it — and is the one
    thing all ten have in common (PLAN B73). It picks the interpreter, layers
    the venv, and sets the PYTHONPATH that decides which copy of `jarvis_bus`
    gets imported; that last line, when it was added, changed the answer every
    suite in this repo gives. Before this, a change to it named `tools` alone,
    because `tools` reads the script as TEXT to check the service list in its
    header — a real reader, and not the one at risk.

    Guarded on the file being there, the same refusal the QML and declared
    gates make: a command naming a script this repo does not have is worse
    advice than none, and a DELETED runner is a changed path like any other.
    """
    skip = set(exclude)
    want = sorted({rel for given in paths for rel in _expand(root, given)})
    runner = (RUNTESTS_SH,) if (root / RUNTESTS_SH).is_file() else ()
    out: dict[str, list[str]] = {}
    for suite in suites(root, warn):
        if suite.name in skip:
            continue
        hit = [p for p in want if is_read((*suite.reads, *runner), p)]
        if hit:
            out[suite.name] = hit
    return dict(sorted(out.items()))


# --------------------------------------------------------------- QML gates
#
# The rule above reads Python, and Python is not where this repo's strongest
# assertions about the HUD live. `ops/ralph/qmltest.sh` runs the headless
# element tests; `ops/ralph/hudshots.sh` draws the contact sheet, replays the
# recorded sessions through the real plates and reads the sheet back against
# the PNGs committed at HEAD. Neither can be found by matching strings,
# because a QML file names its subject by TYPE — `ReplyState {}` — and never
# by path (PLAN B69).
#
# A QML type IS a file, though, and the engine finds it the same two ways
# every time: the directory `import "..."` lines put on the path, and the
# `qmldir` that directory ships. So this reads what the engine reads.


@dataclasses.dataclass(frozen=True)
class QmlGate:
    """One gate script, and the QML tree it points an engine at.

    `entry` is the directory whose `.qml` files the runner is given. Every
    other directory follows from the `import` lines inside them — resolved
    against the real repo, because for `qmltest.sh` the tree IS the repo.

    `mounts` is the exception, and the only thing here that is written down
    rather than derived: `hudshots.sh` assembles a temporary stage (the whole
    shell, with two Quickshell-bound singletons overwritten by stubs), so a
    driver's `import ".."` means something no reader of the QML could work
    out. Each mount maps a virtual directory — relative to `entry`, as the
    driver writes it — onto the repo directories that land there, later
    shadowing earlier. `test_dependents.py` checks every one of them against
    the script that does the staging, so a stage that moves cannot leave this
    table behind.

    `also` is what the gate reads that is not QML at all: the comparator it
    runs, and the committed sheet it compares against.
    """

    script: str
    entry: str
    mounts: tuple[tuple[str, tuple[str, ...]], ...] = ()
    also: tuple[str, ...] = ()


QML_GATES = (
    QmlGate(
        script="ops/ralph/qmltest.sh",
        entry="shell/jv-hud/tests",
    ),
    # The bar's headless tests, the same shape one shell over: `bartest.sh`
    # and `qmltest.sh` are two scripts rather than one with an argument
    # precisely so this table can tell them apart — a single command pointed
    # at both trees would make a change to a bar element run the HUD's tests.
    QmlGate(
        script="ops/ralph/bartest.sh",
        entry="shell/jv-bar/tests",
    ),
    # And the notifier's (PLAN D2). Third script, same argument: what is
    # derived from a path is which gate runs, so editing a toast must not run
    # the bar's tests.
    QmlGate(
        script="ops/ralph/notifytest.sh",
        entry="shell/jv-notify/tests",
    ),
    QmlGate(
        script="ops/ralph/hudshots.sh",
        entry="tools/hudshots/scene",
        mounts=(
            # The drivers sit in `$stage/shots` beside a copy of Sessions.qml…
            (".", ("tools/hudshots/scene", "shell/jv-hud/tests")),
            # …and `$stage` itself is the shell, with the two singletons that
            # import Quickshell replaced. `shell.qml` is deleted from the
            # stage and is not a type, so nothing reaches it from here.
            ("..", ("shell/jv-hud", "tools/hudshots/stub")),
        ),
        also=("tools/hudsheet.py", "docs/hud"),
    ),
    # And the notification corner's (PLAN D20), the same assembly one shell
    # over. Same argument for a second script as for `notifytest.sh`: a change
    # to a toast must rebuild THIS sheet and not the HUD's.
    QmlGate(
        script="ops/ralph/notifyshots.sh",
        entry="tools/notifyshots/scene",
        mounts=(
            # The driver and the staged strip sit together in `$stage/shots`…
            (".", ("tools/notifyshots/scene",)),
            # …and `$stage` itself is the shell, with the two singletons that
            # import Quickshell replaced: `Notifications` (it IS the D-Bus
            # server) and `Motion`. `shell.qml` is deleted from the stage and
            # is not a type, so nothing reaches it from here.
            ("..", ("shell/jv-notify", "tools/notifyshots/stub")),
        ),
        also=("tools/hudsheet.py", "docs/notify"),
    ),
    # And the top bar's (PLAN D13), which makes it one harness per shell.
    # Third script for the third shell, same argument as `bartest.sh`: what is
    # derived from a path is which gate runs, and a change to a toast must not
    # rebuild the strip.
    QmlGate(
        script="ops/ralph/barshots.sh",
        entry="tools/barshots/scene",
        mounts=(
            # The driver and the staged strip sit together in `$stage/shots`…
            (".", ("tools/barshots/scene",)),
            # …and `$stage` itself is the shell, with the two singletons that
            # import Quickshell replaced: `Niri` (it runs the event stream as a
            # child process) and `Motion`. `shell.qml` is deleted from the
            # stage and is not a type, so nothing reaches it from here.
            ("..", ("shell/jv-bar", "tools/barshots/stub")),
        ),
        also=("tools/hudsheet.py", "docs/bar"),
    ),
)

# `module`, `depends`, `plugin`… — qmldir lines that declare no type.
QMLDIR_KEYWORDS = {"singleton", "internal", "optional", "default", "required"}


def _qml_scrub(text: str) -> tuple[str, str]:
    """`text` with comments gone, and again with string bodies blanked.

    The first is where `import "../core"` is read from; the second is where
    type names are. Both matter: `Sessions.qml` carries whole recorded bus
    frames as string literals and every driver opens with a paragraph about
    the plates it draws, so a scan of the raw file would find a gate named by
    a sentence about it.
    """
    code: list[str] = []
    bare: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and text[i + 1 : i + 2] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and text[i + 1 : i + 2] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            code.append(" ")
            bare.append(" ")
            continue
        if c in "\"'`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            code.append(text[i : min(j + 1, n)])
            bare.append(c + c)
            i = j + 1
            continue
        code.append(c)
        bare.append(c)
        i += 1
    return "".join(code), "".join(bare)


def _qml_imports(code: str) -> list[str]:
    """The directory imports of one QML file, as written."""
    return re.findall(r"^[ \t]*import[ \t]+\"([^\"\n]+)\"", code, re.MULTILINE)


def _qml_names(bare: str) -> set[str]:
    """Every identifier the file uses, with strings and comments already out.

    Not filtered to look like a type: the directory's own map is the filter,
    and it is a better one than any spelling rule.
    """
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", bare))


def _qmldir_types(text: str) -> dict[str, str]:
    """type -> file name, out of a `qmldir`.

    A directory that ships one has turned off the implicit scan — Quickshell
    synthesizes a qmldir per directory and `shell/jv-hud/qmldir` exists
    precisely to replace that — so what it declares is exactly what resolves
    there.
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = [p for p in line.split() if p]
        if not parts or parts[0].startswith("#"):
            continue
        while parts and parts[0] in QMLDIR_KEYWORDS:
            parts.pop(0)
        if len(parts) >= 2 and parts[-1].endswith(".qml") and parts[0].isidentifier():
            out[parts[0]] = parts[-1]
    return out


def _dir_types(root: Path, dirs: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    """One virtual directory: its type map, and the `qmldir`s that made it.

    `dirs` are the repo directories assembled there, later shadowing earlier —
    which is how the sheet's stub `Bus.qml` hides the real one while the
    generated `qmldir` beside it still says `singleton Bus 1.0 Bus.qml`.
    """
    files: dict[str, str] = {}
    declared: dict[str, str] = {}
    maps: list[str] = []
    for d in dirs:
        p = root / d
        if not p.is_dir():
            continue
        for f in sorted(p.glob("*.qml")):
            files[f.name] = f"{d}/{f.name}"
        qmldir = p / "qmldir"
        if qmldir.is_file():
            declared.update(_qmldir_types(qmldir.read_text("utf-8", errors="replace")))
            maps.append(f"{d}/qmldir")
    if declared:
        return {t: files[f] for t, f in declared.items() if f in files}, maps
    # No qmldir: the engine's implicit scan, where a type is a file whose name
    # is capitalised. `shell.qml` and every `tst_*.qml` are not types.
    return (
        {f[:-4]: rel for f, rel in files.items() if f[:1].isupper()},
        maps,
    )


def qml_reads(
    root: Path, gate: QmlGate, warn: Callable[[str], None] | None = None
) -> frozenset[str]:
    """Every repo path one QML gate opens, followed type by type.

    Starts at the files the runner is handed and walks the same edges the
    engine walks: for each file, the directories it imports (plus its own),
    and in them the types it names. A `core/` element three types below a
    driver is reached, because three files away is exactly as far as "I did
    not think of that gate".
    """
    if warn is None:
        warn = _warn
    if not (root / gate.script).is_file():
        return frozenset()

    mounts = dict(gate.mounts)
    mounts.setdefault(".", (gate.entry,))
    cache: dict[str, tuple[dict[str, str], list[str]]] = {}

    def resolve(vdir: str) -> tuple[dict[str, str], list[str]] | None:
        """The type map of a virtual directory, or nothing if the gate does
        not stage it."""
        if vdir in cache:
            return cache[vdir]
        parts = [p for p in vdir.split("/") if p]
        for cut in range(len(parts), -1, -1):
            key = "/".join(parts[:cut]) or "."
            if key in mounts:
                tail = parts[cut:]
                dirs = [posixpath.normpath("/".join([d, *tail])) for d in mounts[key]]
                break
        else:  # pragma: no cover - "." is always a mount
            return None
        if any(d.startswith("..") for d in dirs):
            return None  # climbed out of the repo; the same refusal as `_resolve`
        if not any((root / d).is_dir() for d in dirs):
            return None
        cache[vdir] = _dir_types(root, dirs)
        return cache[vdir]

    # The gate script itself, implicitly and for the same reason the declared
    # gates count theirs (B72, B73): the change most likely to break a gate is
    # a change to the gate, and nothing below can reach it — this walk starts
    # at `entry` and follows QML imports, and a bash script that points an
    # engine at a directory is not a type on anybody's import path.
    out: set[str] = {gate.script}
    out |= {rel for rel in gate.also if (root / rel).exists()}
    seen: set[str] = set()
    # The runner is handed ONE directory, and only its files are entries. The
    # sheet's stage holds `Sessions.qml` from `shell/jv-hud/tests` too, but as
    # a type the drivers may name — not as a driver of its own, which is why
    # the eighteen `tst_*.qml` beside it belong to the other gate alone.
    queue: list[tuple[str, str]] = [
        (".", f"{gate.entry}/{f.name}")
        for f in sorted((root / gate.entry).glob("*.qml"))
    ]

    while queue:
        vdir, rel = queue.pop()
        if rel in seen:
            continue
        seen.add(rel)
        out.add(rel)
        try:
            code, bare = _qml_scrub((root / rel).read_text("utf-8", errors="replace"))
        except OSError:
            continue
        names = _qml_names(bare)
        for imp in [".", *_qml_imports(code)]:
            target = _vjoin(vdir, imp)
            found = resolve(target)
            if found is None:
                warn(
                    f"dependents: {rel} imports {imp!r}, which {gate.script} "
                    "does not stage — what it reads there is unknown, not none"
                )
                continue
            types, maps = found
            hits = [types[n] for n in names if n in types]
            if hits:
                out.update(maps)
            queue += [(target, hit) for hit in hits]
    return frozenset(out)


def _vjoin(vdir: str, imp: str) -> str:
    """A QML import, as a virtual directory relative to the gate's entry.

    `..` is kept when it climbs above the entry — `tools/hudshots/scene` is
    `.` and the stage root above it is `..`, and that is a real place the
    mounts name.
    """
    parts = [p for p in vdir.split("/") if p and p != "."]
    for seg in imp.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            else:
                parts.append("..")
        else:
            parts.append(seg)
    return "/".join(parts) or "."


def qml_readers(
    root: Path,
    paths: Iterable[str],
    *,
    exclude: Iterable[str] = (),
    warn: Callable[[str], None] | None = None,
) -> dict[str, list[str]]:
    """Gate script -> the changed paths it opens. Same shape as `readers`."""
    skip = set(exclude)
    want = sorted({rel for given in paths for rel in _expand(root, given)})
    out: dict[str, list[str]] = {}
    for gate in QML_GATES:
        if gate.script in skip:
            continue
        reads = qml_reads(root, gate, warn)
        hit = [p for p in want if is_read(reads, p)]
        if hit:
            out[gate.script] = hit
    return out


# --------------------------------------------------------- declared gates
#
# Two gates are neither Python, nor QML, nor Rust, and nothing above can find
# either, because what they read is a NIX EVALUATION (PLAN B72).
# `ops/ralph/nixtest.sh` asserts what a module OPTION does to the unit text
# ares is handed — its subject is the flake attribute
# `.#nixosConfigurations.ares`, and an attribute is not a path that any syntax
# tree names. `ops/ralph/hudscreens.sh` is the same shape one level further
# out: it photographs the REAL `.#jv-hud` through a real compositor, so what
# it reads is a derivation and not a set of QML imports.
#
# So these two are DECLARED rather than derived — and a declaration that
# nothing checks is the prose that had already failed once (B68), so it is
# checked twice: every path must exist, and the SCRIPT must say the same list
# in its own `# reads:` header. `test_dependents.py` holds both, which is what
# it already does for the staging `hudshots.sh` performs.
#
# Nothing here is a licence to declare a gate that could have been derived. A
# suite that reads a path in Python, or a QML gate reachable from a driver, is
# found by the rules above and must not be written down.


@dataclasses.dataclass(frozen=True)
class DeclaredGate:
    """One gate whose read-set is stated rather than worked out.

    `reads` are path prefixes, tested the way everything else here is tested:
    a changed path is read when the gate names it or a directory above it.

    `runs_here` is the honest half. The loop's gate binds what it plans — it
    RUNS every step — so a gate that must not be run unattended cannot simply
    be planned, and the alternative is not silence: `note` says why, and is
    printed beside the paths that asked for it, so a green verdict never
    stands where a gate was skipped without saying so.
    """

    script: str
    reads: tuple[str, ...]
    runs_here: bool = True
    note: str = ""


DECLARED_GATES = (
    DeclaredGate(
        script="ops/ralph/nixtest.sh",
        # The whole flake, because the whole flake is what an ares evaluation
        # reads: `flake.nix` assembles the configuration out of `hosts/ares`,
        # `modules`, `pkgs` and `nix`, and `flake.lock` decides which nixpkgs
        # every one of those is evaluated against. Not `services`: a service's
        # source changes the store path inside an ExecStart and nothing this
        # gate asserts, and paying 22 s on every Python edit to learn that
        # would be the noise that gets a gate switched off.
        reads=("flake.lock", "flake.nix", "hosts/ares", "modules", "nix", "pkgs"),
    ),
    DeclaredGate(
        script="ops/ralph/hudscreens.sh",
        # Everything the pictures are OF. The flake is in the list on the
        # script's own argument: it realizes sway and Qt out of the pinned
        # nixpkgs, because a sheet rendered against a different Qt is a
        # picture of a different machine.
        reads=(
            "docs/hud/screens",
            "flake.lock",
            "flake.nix",
            "personality/theme.toml",
            "pkgs/jv-hud",
            "services/jarvisd",
            "shell/jv-hud",
            "tools/hudscreens",
            # The comparator it reads its own sheet back with (B74). Nothing
            # in a nix evaluation names it, and it is the half of this gate
            # that can go wrong quietly: a floor set too high turns a changed
            # HUD into a green run.
            "tools/hudsheet.py",
        ),
        runs_here=False,
        note=(
            "3m00s, a compositor, and a sheet of pictures for a human — "
            "run it yourself, look at the shots, commit them"
        ),
    ),
)


def declared_readers(
    root: Path,
    paths: Iterable[str],
    *,
    exclude: Iterable[str] = (),
) -> list[tuple[DeclaredGate, list[str]]]:
    """Every declared gate that reads `paths`, in declaration order.

    Both kinds, runnable or not: a caller that wants one asks for one. The
    existence of the script is checked the same way the QML gates check it —
    a gate whose script is not in this repo is not offered, because a command
    that cannot run is worse advice than none.

    The script counts as part of its own read-set, and that is implicit rather
    than declared: editing a gate is the change most likely to break it, and a
    `# reads:` header that had to name itself would be stating a rule instead
    of a subject. This iteration is the case in point — B72 rewrote the header
    of `nixtest.sh` and without this nothing would have run it.
    """
    skip = set(exclude)
    want = sorted({rel for given in paths for rel in _expand(root, given)})
    out: list[tuple[DeclaredGate, list[str]]] = []
    for gate in DECLARED_GATES:
        if gate.script in skip or not (root / gate.script).is_file():
            continue
        hit = [p for p in want if is_read((*gate.reads, gate.script), p)]
        if hit:
            out.append((gate, hit))
    return out


def unrun(
    root: Path,
    paths: Iterable[str],
    *,
    exclude: Iterable[str] = (),
) -> list[tuple[DeclaredGate, list[str]]]:
    """The gates that read what changed and are deliberately NOT run for you."""
    return [
        (gate, why)
        for gate, why in declared_readers(root, paths, exclude=exclude)
        if not gate.runs_here
    ]



# ----------------------------------------------------------- the worktree


def changed(root: Path) -> list[str]:
    """What `git status` says you have done, paths only.

    `-z` rather than the quoting `--porcelain` does by default, so a path with
    a space in it arrives whole. A rename is reported as two records and the
    second is where the file was; both are returned, because the old name may
    be what a suite still points at.
    """
    done = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "-z"],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return []
    out: list[str] = []
    for record in done.stdout.split("\0"):
        if len(record) > 3 and record[2] == " ":
            out.append(record[3:])
        elif record:
            out.append(record)  # the source half of a rename
    return sorted({p for p in out if p})


# ------------------------------------------------------------------- CLI


def _why(why: Sequence[str]) -> str:
    """The paths that pulled a gate in, three of them and a count."""
    return ", ".join(why[:3]) + (f", +{len(why) - 3} more" if len(why) > 3 else "")


def _skipped(skipped: Sequence[tuple["DeclaredGate", list[str]]]) -> list[str]:
    """The gates that read what changed and are not offered as a command.

    Printed at all because the alternative is what this said before B72:
    nothing. A list headed "the suites that read what changed" which quietly
    drops one is worse than no list, and it is worse in the direction that
    matters — it reads as coverage.
    """
    if not skipped:
        return []
    lines = ["", "Not run for you, and reading what changed:"]
    for gate, why in skipped:
        lines += [f"  {gate.script}   # {_why(why)}", f"      {gate.note}"]
    return lines


def _report(
    root: Path,
    paths: Sequence[str],
    found: dict[str, list[str]],
    skipped: Sequence[tuple["DeclaredGate", list[str]]] = (),
) -> list[str]:
    """The notice, as the author reads it at the moment they would commit.

    Commands, not names: a suite name is a fact, and a command is the thing a
    tired loop will actually run. The path that pulled each one in is printed
    beside it, because a notice nobody can check is a notice nobody trusts.
    """
    if not found:
        return [
            f"dependents: no suite or gate reads any of the "
            f"{len(paths)} path{'s' if len(paths) != 1 else ''} that changed."
        ] + _skipped(skipped)
    width = max(len(cmd) for cmd in found)
    head = (
        "dependents: one suite reads what changed — run it:"
        if len(found) == 1
        else f"dependents: {len(found)} suites read what changed — run them:"
    )
    lines = [head, ""]
    for cmd, why in found.items():
        lines.append(f"  {cmd.ljust(width)}   # {_why(why)}")
    lines += _skipped(skipped)
    lines += [
        "",
        "(Python, QML, and the two nix gates that are declared. Rust is not read:",
        " a change under services/jarvisd or services/jv-act is",
        " `bash ops/ralph/cargotest.sh <crate>`, always.)",
    ]
    return lines


def commands(
    root: Path,
    paths: Iterable[str],
    *,
    exclude: Iterable[str] = (),
    warn: Callable[[str], None] | None = None,
) -> dict[str, list[str]]:
    """Every gate that reads what changed, as the command that runs it."""
    paths = list(paths)
    out = {
        f"{RUNTESTS} {name}": why
        for name, why in readers(root, paths, exclude=exclude, warn=warn).items()
    }
    out.update(
        {
            f"bash {script}": why
            for script, why in qml_readers(
                root, paths, exclude=exclude, warn=warn
            ).items()
        }
    )
    out.update(
        {
            f"bash {gate.script}": why
            for gate, why in declared_readers(root, paths, exclude=exclude)
            if gate.runs_here
        }
    )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dependents", description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=None, help="the repo (default: this file's)")
    ap.add_argument(
        "--changed",
        action="store_true",
        help="ask git what changed in the worktree, instead of listing paths",
    )
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="SUITE",
        help="a suite the caller has already run (repeatable)",
    )
    ap.add_argument(
        "--quiet-when-empty",
        action="store_true",
        help="print nothing at all when nothing changed (for the gate)",
    )
    ap.add_argument("paths", nargs="*", help="the paths you changed")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    if not (root / "services").is_dir():
        print(f"dependents: {root} does not look like this repo", file=sys.stderr)
        return 2

    paths = list(args.paths)
    if args.changed:
        paths += changed(root)
    if not paths:
        if args.quiet_when_empty:
            return 0
        print("dependents: nothing changed.")
        return 0

    for line in _report(
        root,
        paths,
        commands(root, paths, exclude=args.exclude),
        unrun(root, paths, exclude=args.exclude),
    ):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
