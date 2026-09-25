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

WHAT IT CANNOT SEE. QML. `ops/ralph/qmltest.sh` and `ops/ralph/hudshots.sh`
are the strongest gates over `shell/jv-hud`, and a QML test names its subject
by TYPE (`ReplyState {}`), not by path. There is no path to find, so this
prints the two scripts as a standing caveat rather than pretending the list is
complete.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, Sequence

RUNTESTS = "bash ops/ralph/runtests.sh"

# The gates this tool is blind to, named every time it has anything to say.
QML_GATES = ("ops/ralph/qmltest.sh", "ops/ralph/hudshots.sh")

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
    """
    if not top or not top.isidentifier():
        return None
    for base in bases:
        stem = f"{base}/{top}" if base else top
        if (root / stem / "__init__.py").exists():
            return stem
        if (root / f"{stem}.py").exists():
            return f"{stem}.py"
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
    """Suite name -> the changed paths it reads. Empty when nobody reads them."""
    skip = set(exclude)
    want = sorted({rel for given in paths for rel in _expand(root, given)})
    out: dict[str, list[str]] = {}
    for suite in suites(root, warn):
        if suite.name in skip:
            continue
        hit = [p for p in want if is_read(suite.reads, p)]
        if hit:
            out[suite.name] = hit
    return dict(sorted(out.items()))


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


def _report(root: Path, paths: Sequence[str], found: dict[str, list[str]]) -> list[str]:
    if not found:
        return [
            f"dependents: no Python suite names any of the "
            f"{len(paths)} path{'s' if len(paths) != 1 else ''} that changed."
        ]
    width = max(len(name) for name in found)
    head = (
        "dependents: one suite reads what changed — run it:"
        if len(found) == 1
        else f"dependents: {len(found)} suites read what changed — run them:"
    )
    lines = [head, ""]
    for name, why in found.items():
        shown = ", ".join(why[:3]) + (f", +{len(why) - 3} more" if len(why) > 3 else "")
        lines.append(f"  {RUNTESTS} {name.ljust(width)}   # {shown}")
    lines += [
        "",
        f"(Python suites only — {QML_GATES[0]} and {QML_GATES[1]} name their",
        " subjects by QML type, not by path, and nothing here can find them.)",
    ]
    return lines


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

    for line in _report(root, paths, readers(root, paths, exclude=args.exclude)):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
