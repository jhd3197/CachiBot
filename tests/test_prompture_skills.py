"""Regression tests for the Prompture skills integration.

The imports in ``cachibot.services.skills`` used to reference ``prompture.skills``,
which no longer exists in prompture 1.19, so the ``ImportError`` fallback silently
disabled skill parsing and discovery. These tests pin the imports to the current
locations (``prompture.agents.skills``) and exercise the enabled code paths against
a temporary skills directory. No network, no real HOME, no real repo.
"""

from pathlib import Path

import pytest

import cachibot.services.skills as skills_mod
from cachibot.models.skill import SkillSource
from cachibot.services.skills import PROMPTURE_SKILLS_AVAILABLE, SkillsService

SKILL_MD = """\
---
name: code-reviewer
description: Reviews code for issues
version: 1.2.0
author: tester
tags: [code, review]
tools: [Read, Grep]
---

Review the code carefully.
"""


def _write_skill(directory: Path, name: str, content: str = SKILL_MD) -> Path:
    skill_dir = directory / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def service(tmp_path, monkeypatch):
    """SkillsService with every filesystem root redirected into tmp_path."""
    installed = tmp_path / ".cachibot" / "skills" / "installed"
    monkeypatch.setattr(skills_mod, "INSTALLED_DIR", installed)
    monkeypatch.setattr(skills_mod, "CACHIBOT_DIR", installed.parent)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    return SkillsService()


def test_prompture_skills_import_available():
    """The prompture skills imports must resolve — no silent fallback."""
    assert PROMPTURE_SKILLS_AVAILABLE is True
    assert skills_mod.SkillInfo is not None
    assert callable(skills_mod.load_skill_async)
    assert callable(skills_mod.discover_skills_async)


async def test_parse_skill_file_maps_frontmatter(service, tmp_path):
    path = _write_skill(tmp_path / "src", "code-reviewer")

    skill = await service.parse_skill_file(path, SkillSource.LOCAL)

    assert skill.id.startswith("code-reviewer-")
    assert skill.name == "code-reviewer"
    assert skill.description == "Reviews code for issues"
    assert skill.version == "1.2.0"
    assert skill.author == "tester"
    assert skill.tags == ["code", "review"]
    assert skill.requires_tools == ["Read", "Grep"]
    assert skill.instructions == "Review the code carefully."
    assert skill.source == SkillSource.LOCAL
    assert skill.filepath == str(path)


async def test_parse_skill_file_defaults_when_optional_fields_missing(service, tmp_path):
    content = "---\nname: minimal\ndescription: Just the basics\n---\n\nDo the thing.\n"
    path = _write_skill(tmp_path / "src", "minimal", content)

    skill = await service.parse_skill_file(path, SkillSource.INSTALLED)

    assert skill.name == "minimal"
    assert skill.version == "1.0.0"
    assert skill.author is None
    assert skill.tags == []
    assert skill.requires_tools == []
    assert skill.instructions == "Do the thing."
    assert skill.source == SkillSource.INSTALLED


async def test_parse_skill_file_invalid_raises(service, tmp_path):
    path = _write_skill(tmp_path / "src", "broken", "---\nname: [unclosed\n---\nbody\n")

    with pytest.raises(skills_mod.SkillParseError):
        await service.parse_skill_file(path, SkillSource.LOCAL)


async def test_scan_installed_skills(service, tmp_path, monkeypatch):
    installed = tmp_path / ".cachibot" / "skills" / "installed"
    _write_skill(installed, "url-installed")

    skills = await service.scan_installed_skills()

    assert len(skills) == 1
    assert skills[0].name == "code-reviewer"
    assert skills[0].source == SkillSource.INSTALLED


async def test_scan_claude_skills_discovers_project_skills(service, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_skill(tmp_path / ".claude" / "skills", "code-reviewer")

    skills = await service.scan_claude_skills()

    assert len(skills) == 1
    skill = skills[0]
    assert skill.name == "code-reviewer"
    assert skill.source == SkillSource.LOCAL
    assert skill.version == "1.2.0"
    assert skill.filepath is not None
    assert skill.filepath.endswith("SKILL.md")
