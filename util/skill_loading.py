
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

WORKDIR = Path.cwd()
# SKILLS_DIR = WORKDIR / "skills"
SKILLS_DIR = Path("~/.claude/skills").expanduser()


@dataclass
class SkillManifest:
    name: str
    description: str
    path: Path


@dataclass
class SkillDocument:
    manifest: SkillManifest
    body: str


class SkillRegistry:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.documents: dict[str, SkillDocument] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.skills_dir.exists():
            return
        # skills_dir 下的所有 *.md 文件，包括子目录
        skill_files = sorted(self.skills_dir.rglob("*.md"))
        for path in skill_files:
            meta, body = self._parse_frontmatter(path.read_text())
            name = meta.get("name", path.parent.name)
            description = meta.get("description", "No description")
            manifest = SkillManifest(name=name, description=description, path=path)
            self.documents[name] = SkillDocument(manifest=manifest, body=body.strip())

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text

        meta = {}
        for line in match.group(1).strip().splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
        return meta, match.group(2)

    def describe_available(self) -> str:
        if not self.documents:
            return "(no skills available)"
        lines = []
        for name in sorted(self.documents):
            manifest = self.documents[name].manifest
            lines.append(f"- {manifest.name}: {manifest.description}")
        return "\n".join(lines)

    def load_full_text(self, name: str) -> str:
        document = self.documents.get(name)
        if not document:
            known = ", ".join(sorted(self.documents)) or "(none)"
            return f"Error: Unknown skill '{name}'. Available skills: {known}"

        return (
            f"<skill name=\"{document.manifest.name}\">\n"
            f"{document.body}\n"
            "</skill>"
        )


SKILL_REGISTRY = SkillRegistry(SKILLS_DIR)

SKILL_LOADING_SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use load_skill when a task needs specialized instructions before you act.

Skills available:
{SKILL_REGISTRY.describe_available()}
"""