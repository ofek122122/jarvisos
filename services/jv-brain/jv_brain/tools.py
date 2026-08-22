"""Tool definitions for the brain, read from the SAME registry TOML
jv-act enforces (/etc/jarvis/tools.toml — config distribution, the act
copy stays authoritative). Translated to OpenAI function-calling defs
for llama-server."""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ModuleNotFoundError:  # 3.10
    import tomli as tomllib  # type: ignore[no-redef]

REPO = Path(__file__).resolve().parents[3]

_TYPE_MAP = {"string": "string", "number": "number", "integer": "integer", "boolean": "boolean"}


def default_tools_path() -> Path:
    if env := os.environ.get("JARVIS_TOOLS_TOML"):
        return Path(env)
    etc = Path("/etc/jarvis/tools.toml")
    if etc.exists():
        return etc
    return REPO / "services" / "jv-act" / "tools.toml"


@dataclasses.dataclass
class ToolInfo:
    name: str
    description: str
    capability: str
    parameters: Dict[str, Any]


def load_tools(path: Optional[Path] = None) -> Dict[str, ToolInfo]:
    path = path or default_tools_path()
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, ToolInfo] = {}
    for t in data.get("tool", []):
        props: Dict[str, Any] = {}
        required: List[str] = []
        for arg_name, spec in t.get("args", {}).items():
            prop: Dict[str, Any] = {"type": _TYPE_MAP[spec["type"]]}
            if desc := spec.get("description"):
                prop["description"] = desc
            if one_of := spec.get("one_of"):
                prop["enum"] = one_of
            props[arg_name] = prop
            if spec.get("required"):
                required.append(arg_name)
        out[t["name"]] = ToolInfo(
            name=t["name"],
            description=t["description"],
            capability=t["capability"],
            parameters={
                "type": "object",
                "properties": props,
                "required": required,
            },
        )
    return out


def openai_tool_defs(tools: Dict[str, ToolInfo]) -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools.values()
    ]
