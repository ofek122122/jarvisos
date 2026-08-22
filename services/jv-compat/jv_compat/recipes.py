"""Recipe database: TOML files in recipes/ (in-repo, reviewed like
code — a recipe grants capabilities to a Windows app)."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ModuleNotFoundError:  # 3.10
    import tomli as tomllib  # type: ignore[no-redef]

REPO = Path(__file__).resolve().parents[3]
DEFAULT_RECIPES_DIR = REPO / "recipes"


@dataclasses.dataclass
class Recipe:
    app: str  # slug, prefix directory name
    match_sha256: list[str]
    match_installer: str  # nsis|inno|msi|"" (any)
    silent: bool = True
    extra_args: list[str] = dataclasses.field(default_factory=list)
    # Confinement grants — DEFAULT DENY (blueprint §08 + invariant 8):
    network: bool = False
    home_paths: list[str] = dataclasses.field(default_factory=list)


def load_recipes(recipes_dir: Optional[Path] = None) -> list[Recipe]:
    recipes_dir = recipes_dir or DEFAULT_RECIPES_DIR
    out: list[Recipe] = []
    if not recipes_dir.is_dir():
        return out
    for f in sorted(recipes_dir.glob("*.toml")):
        data = tomllib.loads(f.read_text(encoding="utf-8"))
        r = data.get("recipe", {})
        grants = data.get("grants", {})
        out.append(
            Recipe(
                app=r["app"],
                match_sha256=[s.lower() for s in r.get("match_sha256", [])],
                match_installer=r.get("match_installer", ""),
                silent=r.get("silent", True),
                extra_args=r.get("extra_args", []),
                network=grants.get("network", False),
                home_paths=grants.get("home_paths", []),
            )
        )
    return out


def find_recipe(
    recipes: list[Recipe], sha256: str, installer: str
) -> Optional[Recipe]:
    """sha256 pin wins; otherwise the first installer-type match with no
    sha pin (generic recipe)."""
    for r in recipes:
        if sha256.lower() in r.match_sha256:
            return r
    for r in recipes:
        if not r.match_sha256 and r.match_installer and r.match_installer == installer:
            return r
    return None
