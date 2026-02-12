"""
Skills Service for CachiBot

Uses Prompture's skills system for parsing and discovery.
Skill files use SKILL.md format in .claude/skills/ directories.
"""

import hashlib
import logging
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from cachibot.models.skill import SkillDefinition, SkillSource
from cachibot.storage.repository import SkillsRepository

# Import Prompture's skills system
try:
    from prompture import discover_skills_async, load_skill_async
    from prompture.skills import SkillInfo

    PROMPTURE_SKILLS_AVAILABLE = True
except ImportError:
    PROMPTURE_SKILLS_AVAILABLE = False
    SkillInfo = None

logger = logging.getLogger(__name__)

# Skills directory structure (Claude Code compatible)
# Local skills: ./.claude/skills/ (project-local)
# User skills: ~/.claude/skills/ (user-global)
PROJECT_SKILLS_DIR = Path.cwd() / ".claude" / "skills"
USER_SKILLS_DIR = Path.home() / ".claude" / "skills"

# Legacy CachiBot paths for installed skills (from URLs)
CACHIBOT_DIR = Path.home() / ".cachibot" / "skills"
INSTALLED_DIR = CACHIBOT_DIR / "installed"


class SkillParseError(Exception):
    """Error parsing a skill file."""

    pass


class SkillInstallError(Exception):
    """Error installing a skill."""

    pass


def _skill_info_to_definition(
    skill_info: "SkillInfo", source: SkillSource, filepath: str | None = None
) -> SkillDefinition:
    """
    Convert Prompture SkillInfo to CachiBot SkillDefinition.

    Args:
        skill_info: Prompture SkillInfo object
        source: Whether this is a local or installed skill
        filepath: Path to the skill file

    Returns:
        CachiBot SkillDefinition
    """
    # Generate stable ID from name and filepath
    path_hash = hashlib.md5(  # nosec B324 — not used for security, just stable IDs
        (filepath or skill_info.name).encode(), usedforsecurity=False
    ).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", skill_info.name.lower()).strip("-")
    skill_id = f"{slug}-{path_hash}"

    return SkillDefinition(
        id=skill_id,
        name=skill_info.name,
        description=skill_info.description or "",
        version=skill_info.version or "1.0.0",
        author=skill_info.author,
        tags=list(skill_info.tags) if skill_info.tags else [],
        requires_tools=list(skill_info.tools) if skill_info.tools else [],
        instructions=skill_info.instructions or "",
        source=source,
        filepath=filepath,
    )


class SkillsService:
    """
    Service for managing skill definitions.

    Uses Prompture's skills system for parsing SKILL.md files.
    Skills are discovered from:
    - ./.claude/skills/ (project-local)
    - ~/.claude/skills/ (user-global)
    - ~/.cachibot/skills/installed/ (URL-installed)
    """

    def __init__(self) -> None:
        self._repo = SkillsRepository()
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure skills directories exist."""
        INSTALLED_DIR.mkdir(parents=True, exist_ok=True)
        # Don't auto-create .claude/skills as user may not want it

    def _generate_skill_id(self, path: Path, name: str) -> str:
        """Generate a stable ID for a skill based on its path and name."""
        path_hash = hashlib.md5(  # nosec B324 — not used for security, just stable IDs
            str(path).encode(), usedforsecurity=False
        ).hexdigest()[:8]
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return f"{slug}-{path_hash}"

    async def parse_skill_file(self, path: Path, source: SkillSource) -> SkillDefinition:
        """
        Parse a skill file using Prompture's async parser.

        Args:
            path: Path to the SKILL.md file
            source: Whether this is a local or installed skill

        Returns:
            Parsed SkillDefinition

        Raises:
            SkillParseError: If the file cannot be parsed
        """
        if not PROMPTURE_SKILLS_AVAILABLE:
            raise SkillParseError("Prompture skills module not available")

        try:
            skill_info = await load_skill_async(str(path))
            return _skill_info_to_definition(skill_info, source, str(path))
        except Exception as e:
            raise SkillParseError(f"Failed to parse skill at {path}: {e}")

    async def scan_claude_skills(self) -> list[SkillDefinition]:
        """
        Scan .claude/skills/ directories using Prompture's discover_skills_async().

        Returns:
            List of parsed skill definitions
        """
        if not PROMPTURE_SKILLS_AVAILABLE:
            logger.warning("Prompture skills not available, skipping discovery")
            return []

        skills: list[SkillDefinition] = []
        try:
            # discover_skills_async() scans both project and user directories
            discovered = await discover_skills_async()

            for skill_info in discovered:
                try:
                    # Use path property (added in Prompture 1.0.6)
                    filepath = str(skill_info.path) if skill_info.path else None

                    skill = _skill_info_to_definition(skill_info, SkillSource.LOCAL, filepath)
                    skills.append(skill)
                except Exception as e:
                    logger.warning(f"Failed to convert skill {skill_info.name}: {e}")

        except Exception as e:
            logger.warning(f"Error discovering skills: {e}")

        return skills

    async def scan_installed_skills(self) -> list[SkillDefinition]:
        """
        Scan the installed skills directory for skill files.

        These are skills installed from URLs, stored in ~/.cachibot/skills/installed/

        Returns:
            List of parsed skill definitions
        """
        skills: list[SkillDefinition] = []
        if not INSTALLED_DIR.exists():
            return skills

        # Look for SKILL.md files in subdirectories or direct .md files
        for path in INSTALLED_DIR.glob("**/SKILL.md"):
            try:
                skill = await self.parse_skill_file(path, SkillSource.INSTALLED)
                skills.append(skill)
            except SkillParseError as e:
                logger.warning(f"Skipping invalid skill file: {e}")

        # Also check for standalone .md files (legacy format)
        for path in INSTALLED_DIR.glob("*.md"):
            if path.name == "SKILL.md":
                continue  # Already handled above
            try:
                skill = await self.parse_skill_file(path, SkillSource.INSTALLED)
                skills.append(skill)
            except SkillParseError as e:
                logger.warning(f"Skipping invalid skill file: {e}")

        return skills

    async def scan_all_skills(self) -> list[SkillDefinition]:
        """Scan all skill directories."""
        skills: list[SkillDefinition] = []

        # 1. Discover from .claude/skills/ (via Prompture)
        skills.extend(await self.scan_claude_skills())

        # 2. Scan installed skills (from URLs)
        skills.extend(await self.scan_installed_skills())

        return skills

    async def sync_skills_to_db(self) -> list[SkillDefinition]:
        """
        Scan all skill directories and sync to database.

        Returns:
            List of all synced skills
        """
        skills = await self.scan_all_skills()

        for skill in skills:
            await self._repo.upsert_skill(skill)

        return skills

    async def install_from_url(self, url: str) -> SkillDefinition:
        """
        Install a skill from a URL (raw markdown file or SKILL.md).

        Args:
            url: URL to the skill file

        Returns:
            Installed skill definition

        Raises:
            SkillInstallError: If installation fails
        """
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise SkillInstallError(f"Invalid URL: {url}")

        # Fetch the content
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True, timeout=30.0)
                response.raise_for_status()
                content = response.text
        except httpx.HTTPError as e:
            raise SkillInstallError(f"Failed to fetch skill from {url}: {e}")

        # Parse to validate and get name
        try:
            # Write to temp location first to validate
            temp_path = INSTALLED_DIR / f"temp_{uuid.uuid4().hex}.md"
            temp_path.write_text(content, encoding="utf-8")

            try:
                skill = await self.parse_skill_file(temp_path, SkillSource.INSTALLED)
            finally:
                # Clean up temp file
                temp_path.unlink(missing_ok=True)

        except SkillParseError as e:
            raise SkillInstallError(f"Invalid skill file: {e}")

        # Create skill directory and save as SKILL.md
        slug = re.sub(r"[^a-z0-9]+", "-", skill.name.lower()).strip("-")
        skill_dir = INSTALLED_DIR / slug

        # Handle name conflicts
        counter = 1
        while skill_dir.exists():
            skill_dir = INSTALLED_DIR / f"{slug}-{counter}"
            counter += 1

        skill_dir.mkdir(parents=True, exist_ok=True)
        final_path = skill_dir / "SKILL.md"

        # Write the file
        final_path.write_text(content, encoding="utf-8")

        # Re-parse with final path for correct ID
        skill = await self.parse_skill_file(final_path, SkillSource.INSTALLED)

        # Save to database
        await self._repo.upsert_skill(skill)

        logger.info(f"Installed skill '{skill.name}' from {url}")
        return skill

    async def install_from_skillssh(self, owner_repo: str) -> SkillDefinition:
        """
        Install a skill from skills.sh using owner/repo format.

        Args:
            owner_repo: GitHub-style owner/repo identifier (e.g., "anthropics/code-reviewer")

        Returns:
            Installed skill definition
        """
        # Try raw GitHub URL for SKILL.md
        url = f"https://raw.githubusercontent.com/{owner_repo}/main/SKILL.md"

        try:
            return await self.install_from_url(url)
        except SkillInstallError:
            # Fallback to skill.md (legacy)
            url = f"https://raw.githubusercontent.com/{owner_repo}/main/skill.md"
            return await self.install_from_url(url)

    async def get_skills_instructions_async(
        self, skill_definitions: list[SkillDefinition]
    ) -> str | None:
        """
        Get combined instructions from skill definitions.

        Args:
            skill_definitions: List of skill definitions

        Returns:
            Combined instructions string, or None if no skills
        """
        if not skill_definitions:
            return None

        instructions = []
        for skill in skill_definitions:
            # Format each skill's instructions with its name
            instructions.append(f"### {skill.name}\n{skill.instructions}")

        return "\n\n".join(instructions)


# Singleton instance
_service: SkillsService | None = None


def get_skills_service() -> SkillsService:
    """Get the shared SkillsService instance."""
    global _service
    if _service is None:
        _service = SkillsService()
    return _service
