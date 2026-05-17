from __future__ import annotations

import re
from typing import Any

import yaml

from physical_agent.protocol.schemas import WorkspaceDocument


FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
YAML_BLOCK_RE = re.compile(r"```yaml\s*\n(.*?)\n```", re.DOTALL)


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=False).strip()


def fenced_yaml(data: Any) -> str:
    return f"```yaml\n{dump_yaml(data)}\n```"


def parse_front_matter(text: str) -> WorkspaceDocument:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        raise ValueError("Workspace Markdown documents must start with YAML front matter.")
    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ValueError("Front matter must be a YAML mapping.")
    for key in ("schema", "owner"):
        if key not in metadata:
            raise ValueError(f"Front matter is missing required key: {key}")
    if "revision" not in metadata and "updated_at" not in metadata:
        raise ValueError("Front matter must include revision or updated_at.")
    return WorkspaceDocument(metadata=metadata, body=match.group(2))


def render_front_matter(metadata: dict[str, Any], body: str) -> str:
    for key in ("schema", "owner"):
        if key not in metadata:
            raise ValueError(f"Front matter is missing required key: {key}")
    if "revision" not in metadata and "updated_at" not in metadata:
        raise ValueError("Front matter must include revision or updated_at.")
    front = dump_yaml(metadata)
    clean_body = body.lstrip("\n")
    return f"---\n{front}\n---\n\n{clean_body.rstrip()}\n"


def extract_yaml_blocks(body: str) -> list[Any]:
    blocks: list[Any] = []
    for match in YAML_BLOCK_RE.finditer(body):
        value = yaml.safe_load(match.group(1))
        blocks.append(value if value is not None else {})
    return blocks


def extract_yaml_block_after_heading(body: str, heading: str, *, level: int = 2) -> Any:
    marker = "#" * level
    heading_re = re.compile(
        rf"^{re.escape(marker)}\s+{re.escape(heading)}\s*$",
        re.MULTILINE,
    )
    heading_match = heading_re.search(body)
    if not heading_match:
        return None
    rest = body[heading_match.end() :]
    block_match = YAML_BLOCK_RE.search(rest)
    if not block_match:
        return None
    value = yaml.safe_load(block_match.group(1))
    return value if value is not None else {}


def extract_section_text(body: str, heading: str, *, level: int = 2) -> str:
    marker = "#" * level
    heading_re = re.compile(
        rf"^{re.escape(marker)}\s+{re.escape(heading)}\s*$",
        re.MULTILINE,
    )
    heading_match = heading_re.search(body)
    if not heading_match:
        return ""
    rest = body[heading_match.end() :]
    next_heading_re = re.compile(rf"^#{{1,{level}}}\s+", re.MULTILINE)
    next_match = next_heading_re.search(rest)
    section = rest[: next_match.start()] if next_match else rest
    return section.strip()

