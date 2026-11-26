"""Tests for the server-side HTML artifact persistence (click-to-edit).

Covers the artifacts API (PUT/GET with version bumps), Website Builder
write-back to pages/{slug}/v{N}/index.html, path-traversal refusal, bot
access rules, the context builder's "## Current HTML artifacts" section,
and the website-preview markdown promotion helper.

SQLite in a tmp dir (same pattern as tests/test_computer_api.py) — no
PostgreSQL, no network; websites_dir is patched so nothing touches the real
~/.cachibot.
"""

import base64
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.models.artifact import Artifact, ArtifactType
from cachibot.models.auth import BotOwnership, UserRole
from cachibot.models.bot import Bot
from cachibot.models.group import BotAccessLevel
from cachibot.services import website_files
from cachibot.services.context_builder import ContextBuilder
from cachibot.storage.artifact_repository import ArtifactRepository
from cachibot.storage.db import Base
from cachibot.storage.group_repository import BotAccessRepository, GroupRepository
from cachibot.storage.repository import BotRepository
from cachibot.storage.user_repository import OwnershipRepository
from tests.conftest import create_test_user  # noqa: F401  (re-exported helper)

# An edited page with a plain comment and an Outlook conditional comment —
# both must survive byte-for-byte through the store and the website file.
EDITED_HTML = (
    "<!DOCTYPE html>\n"
    "<html><head><title>Edited</title></head><body>\n"
    "<!-- keep me -->\n"
    "<!--[if mso]><p>Hello Outlook</p><![endif]-->\n"
    "<p>Edited by hand</p>\n"
    "</body></html>\n"
)
MSO_COMMENT = "<!--[if mso]><p>Hello Outlook</p><![endif]-->"


@pytest.fixture
async def sqlite_db(tmp_path):
    """SQLite in a tmp dir patched into the shared session maker (WAL on)."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/test.db",
        connect_args={"timeout": 30},
        echo=False,
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _set_wal(dbapi_conn, _record) -> None:  # pragma: no cover - plumbing
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")

    import cachibot.storage.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original_engine = db_mod.engine
    original_session_maker = db_mod.async_session_maker
    db_mod.engine = engine
    db_mod.async_session_maker = session_maker

    yield session_maker

    await engine.dispose()
    db_mod.engine = original_engine
    db_mod.async_session_maker = original_session_maker


@pytest.fixture
async def artifacts_client(sqlite_db, auth_service):
    """HTTP client wired to an app with only the artifacts routes."""
    from fastapi import FastAPI

    from cachibot.api.routes import artifacts

    app = FastAPI()
    app.include_router(artifacts.router, tags=["artifacts"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def tmp_websites(tmp_path, monkeypatch):
    """A patch of websites_dir() rooted in tmp_path (never the real HOME)."""
    base = tmp_path / "websites"
    base.mkdir()
    monkeypatch.setattr(website_files, "websites_dir", lambda: base)
    return base


async def make_bot(owner_user_id: str | None = None) -> str:
    """Create a bot (optionally owned by a user). Returns bot id."""
    bot_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await BotRepository().upsert_bot(
        Bot(
            id=bot_id,
            name="Test Bot",
            model="test/model",
            systemPrompt="You are a test bot.",
            createdAt=now,
            updatedAt=now,
        )
    )
    if owner_user_id:
        await OwnershipRepository().assign_bot_owner(
            BotOwnership(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                user_id=owner_user_id,
                created_at=now,
            )
        )
    return bot_id


async def share_bot(bot_id: str, user_id: str, level: BotAccessLevel, owner_id: str) -> None:
    """Share a bot with a user's group at the given access level."""
    group = await GroupRepository().create_group(
        f"{level.value}s-{uuid.uuid4().hex[:6]}", created_by=owner_id
    )
    await GroupRepository().add_member(group.id, user_id)
    await BotAccessRepository().share_bot(bot_id, group.id, level, granted_by=owner_id)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_website_project(base: Path, project_id: str, versions: list[int]) -> Path:
    """AgentSite layout: project.json plus pages/index/v{N}/index.html."""
    root = base / project_id
    root.mkdir(parents=True)
    (root / "project.json").write_text(json.dumps({"id": project_id}), encoding="utf-8")
    for version in versions:
        page_dir = root / "pages" / "index" / f"v{version}"
        page_dir.mkdir(parents=True)
        (page_dir / "index.html").write_text("<html>old</html>", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# 1. PUT then GET: content + bumped version persist, comments survive
# ---------------------------------------------------------------------------


class TestSaveAndGet:
    async def test_put_then_get_persists_content_and_bumps_version(
        self, artifacts_client, auth_service
    ) -> None:
        owner, _ = await create_test_user(auth_service, email="o@t.com", username="owner1")
        token = auth_service.create_access_token(owner.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)
        artifact_id = str(uuid.uuid4())
        url = f"/api/bots/{bot_id}/artifacts/{artifact_id}"

        resp = await artifacts_client.put(
            url,
            headers=auth(token),
            json={
                "content": EDITED_HTML,
                "title": "Landing page",
                "type": "html",
                "chatId": "chat-1",
                "messageId": "msg-1",
                "version": 1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # First save upserts the (previously browser-only) artifact:
        # seeded at (provided version 1) + 1.
        assert body["version"] == 2
        assert body["content"] == EDITED_HTML
        assert body["websiteWritten"] is False
        assert body["chatId"] == "chat-1"

        resp = await artifacts_client.get(url, headers=auth(token))
        assert resp.status_code == 200
        stored = resp.json()
        assert stored["version"] == 2
        # HTML comments and the MSO conditional survive byte-for-byte.
        assert stored["content"] == EDITED_HTML
        assert MSO_COMMENT in stored["content"]
        assert "<!-- keep me -->" in stored["content"]

        # A second save bumps the stored version by exactly 1 again.
        resp = await artifacts_client.put(
            url,
            headers=auth(token),
            json={"content": EDITED_HTML + "<!-- v3 -->", "version": 2},
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 3
        assert resp.json()["title"] == "Landing page"  # unspecified fields kept

        # A stale client version is accepted (no 409) and still increments
        # the stored version — it never rewinds it.
        resp = await artifacts_client.put(
            url,
            headers=auth(token),
            json={"content": EDITED_HTML + "<!-- v4 -->", "version": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 4

    async def test_list_scoped_to_bot_and_chat(self, artifacts_client, auth_service) -> None:
        owner, _ = await create_test_user(auth_service, email="l@t.com", username="owner2")
        token = auth_service.create_access_token(owner.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)
        other_bot_id = await make_bot(owner.id)
        repo = ArtifactRepository()
        for aid, bot, chat in (
            ("a-1", bot_id, "chat-1"),
            ("a-2", bot_id, "chat-2"),
            ("a-3", other_bot_id, "chat-1"),
        ):
            await repo.upsert(
                Artifact(
                    id=aid,
                    bot_id=bot,
                    chat_id=chat,
                    type=ArtifactType.HTML,
                    title=aid,
                    content="<html></html>",
                )
            )

        resp = await artifacts_client.get(
            f"/api/bots/{bot_id}/artifacts", headers=auth(token), params={"chatId": "chat-1"}
        )
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()]
        assert ids == ["a-1"]  # never another chat's or another bot's artifact

        resp = await artifacts_client.get(f"/api/bots/{bot_id}/artifacts", headers=auth(token))
        assert sorted(a["id"] for a in resp.json()) == ["a-1", "a-2"]


# ---------------------------------------------------------------------------
# 2. Website Builder write-back
# ---------------------------------------------------------------------------


class TestWebsiteWriteback:
    async def test_save_writes_comments_through_to_latest_version(
        self, artifacts_client, auth_service, tmp_websites
    ) -> None:
        owner, _ = await create_test_user(auth_service, email="w@t.com", username="owner3")
        token = auth_service.create_access_token(owner.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)
        root = make_website_project(tmp_websites, "proj1", versions=[1, 2])

        resp = await artifacts_client.put(
            f"/api/bots/{bot_id}/artifacts/{uuid.uuid4()}",
            headers=auth(token),
            json={
                "content": EDITED_HTML,
                "title": "Website Preview",
                "type": "html",
                "plugin": "website_builder",
                "metadata": {"project_id": "proj1"},
                "version": 1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["websiteWritten"] is True
        assert body["version"] == 2

        # The highest version dir was overwritten in place, byte-for-byte.
        latest = (root / "pages" / "index" / "v2" / "index.html").read_text(encoding="utf-8")
        assert latest == EDITED_HTML
        assert MSO_COMMENT in latest
        assert "<!-- keep me -->" in latest
        # Older versions are untouched.
        assert (root / "pages" / "index" / "v1" / "index.html").read_text(
            encoding="utf-8"
        ) == "<html>old</html>"

    async def test_writeback_defaults_slug_and_accepts_project_id_camel(
        self, artifacts_client, auth_service, tmp_websites
    ) -> None:
        owner, _ = await create_test_user(auth_service, email="c@t.com", username="owner4")
        token = auth_service.create_access_token(owner.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)
        root = make_website_project(tmp_websites, "proj2", versions=[3])

        resp = await artifacts_client.put(
            f"/api/bots/{bot_id}/artifacts/{uuid.uuid4()}",
            headers=auth(token),
            json={
                "content": EDITED_HTML,
                "plugin": "website_builder",
                "metadata": {"projectId": "proj2", "slug": "index"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["websiteWritten"] is True
        assert (root / "pages" / "index" / "v3" / "index.html").read_text(
            encoding="utf-8"
        ) == EDITED_HTML

    async def test_missing_project_still_saves_artifact(
        self, artifacts_client, auth_service, tmp_websites
    ) -> None:
        owner, _ = await create_test_user(auth_service, email="m@t.com", username="owner5")
        token = auth_service.create_access_token(owner.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)

        resp = await artifacts_client.put(
            f"/api/bots/{bot_id}/artifacts/{uuid.uuid4()}",
            headers=auth(token),
            json={
                "content": EDITED_HTML,
                "plugin": "website_builder",
                "metadata": {"project_id": "no-such-project"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["websiteWritten"] is False
        assert body["content"] == EDITED_HTML
        # No project is created from scratch.
        assert not (tmp_websites / "no-such-project").exists()


# ---------------------------------------------------------------------------
# 3. Path traversal
# ---------------------------------------------------------------------------


class TestPathTraversal:
    @pytest.mark.parametrize(
        "metadata",
        [
            {"project_id": "../etc"},
            {"project_id": ".."},
            {"project_id": "proj1/../../etc"},
            {"project_id": "proj1", "slug": "../index"},
            {"project_id": "proj1", "slug": "a/../../b"},
        ],
    )
    async def test_traversal_never_writes_outside_websites_dir(
        self, artifacts_client, auth_service, tmp_websites, metadata
    ) -> None:
        owner, _ = await create_test_user(
            auth_service,
            email=f"p-{uuid.uuid4().hex[:6]}@t.com",
            username=f"p{uuid.uuid4().hex[:6]}",
        )
        token = auth_service.create_access_token(owner.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)
        make_website_project(tmp_websites, "proj1", versions=[1])

        resp = await artifacts_client.put(
            f"/api/bots/{bot_id}/artifacts/{uuid.uuid4()}",
            headers=auth(token),
            json={"content": EDITED_HTML, "plugin": "website_builder", "metadata": metadata},
        )
        # The artifact still saves; only the disk write is refused.
        assert resp.status_code == 200
        body = resp.json()
        assert body["websiteWritten"] is False
        assert body["content"] == EDITED_HTML
        # Nothing escaped: tmp_websites holds only the legit project, and no
        # sibling ("etc" from "../etc") was created next to it.
        assert [p.name for p in tmp_websites.iterdir()] == ["proj1"]
        assert not (tmp_websites.parent / "etc").exists()
        # The legit project's page is untouched.
        page = tmp_websites / "proj1" / "pages" / "index" / "v1" / "index.html"
        assert page.read_text(encoding="utf-8") == "<html>old</html>"


# ---------------------------------------------------------------------------
# 4. Access rules
# ---------------------------------------------------------------------------


class TestAccess:
    async def test_unauthenticated_put_is_401(self, artifacts_client, auth_service) -> None:
        bot_id = await make_bot()
        resp = await artifacts_client.put(
            f"/api/bots/{bot_id}/artifacts/{uuid.uuid4()}",
            json={"content": "<html></html>"},
        )
        assert resp.status_code == 401
        resp = await artifacts_client.get(f"/api/bots/{bot_id}/artifacts")
        assert resp.status_code == 401

    async def test_user_without_bot_access_is_403(self, artifacts_client, auth_service) -> None:
        owner, _ = await create_test_user(auth_service, email="ao@t.com", username="owner6")
        stranger, _ = await create_test_user(auth_service, email="as@t.com", username="stranger1")
        stranger_token = auth_service.create_access_token(stranger.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)

        resp = await artifacts_client.put(
            f"/api/bots/{bot_id}/artifacts/{uuid.uuid4()}",
            headers=auth(stranger_token),
            json={"content": "<html></html>"},
        )
        assert resp.status_code == 403
        resp = await artifacts_client.get(
            f"/api/bots/{bot_id}/artifacts", headers=auth(stranger_token)
        )
        assert resp.status_code == 403

    async def test_viewer_reads_but_cannot_save(self, artifacts_client, auth_service) -> None:
        owner, _ = await create_test_user(auth_service, email="vo@t.com", username="owner7")
        viewer, _ = await create_test_user(auth_service, email="vv@t.com", username="viewer1")
        viewer_token = auth_service.create_access_token(viewer.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)
        await share_bot(bot_id, viewer.id, BotAccessLevel.VIEWER, owner.id)
        artifact_id = str(uuid.uuid4())
        await ArtifactRepository().upsert(
            Artifact(
                id=artifact_id,
                bot_id=bot_id,
                type=ArtifactType.HTML,
                title="Page",
                content="<html></html>",
            )
        )

        resp = await artifacts_client.get(
            f"/api/bots/{bot_id}/artifacts/{artifact_id}", headers=auth(viewer_token)
        )
        assert resp.status_code == 200
        resp = await artifacts_client.put(
            f"/api/bots/{bot_id}/artifacts/{artifact_id}",
            headers=auth(viewer_token),
            json={"content": "<html>edited</html>"},
        )
        assert resp.status_code == 403

    async def test_cross_bot_artifact_id_is_404(self, artifacts_client, auth_service) -> None:
        owner, _ = await create_test_user(auth_service, email="xo@t.com", username="owner8")
        token = auth_service.create_access_token(owner.id, UserRole.USER.value)
        bot_a = await make_bot(owner.id)
        bot_b = await make_bot(owner.id)
        artifact_id = str(uuid.uuid4())
        await ArtifactRepository().upsert(
            Artifact(
                id=artifact_id,
                bot_id=bot_a,
                type=ArtifactType.HTML,
                title="A's page",
                content="<html></html>",
            )
        )

        resp = await artifacts_client.get(
            f"/api/bots/{bot_b}/artifacts/{artifact_id}", headers=auth(token)
        )
        assert resp.status_code == 404
        resp = await artifacts_client.put(
            f"/api/bots/{bot_b}/artifacts/{artifact_id}",
            headers=auth(token),
            json={"content": "<html>hijack</html>"},
        )
        assert resp.status_code == 404
        # The artifact still belongs to bot A, unchanged.
        stored = await ArtifactRepository().get(artifact_id)
        assert stored is not None
        assert stored.bot_id == bot_a
        assert stored.content == "<html></html>"


# ---------------------------------------------------------------------------
# 5. Context builder sees the edited HTML
# ---------------------------------------------------------------------------


class TestContextBuilder:
    async def test_prompt_includes_edited_html_and_artifact_id(self, sqlite_db) -> None:
        bot_id = await make_bot()
        other_bot_id = await make_bot()
        repo = ArtifactRepository()
        saved = await repo.save_edited(
            Artifact(
                id="art-ctx-1",
                bot_id=bot_id,
                chat_id="chat-ctx",
                type=ArtifactType.HTML,
                title="Landing",
                content=EDITED_HTML,
                plugin="website_builder",
                metadata={"project_id": "proj9"},
                version=1,
            )
        )
        assert saved.version == 2
        await repo.upsert(
            Artifact(
                id="art-other-bot",
                bot_id=other_bot_id,
                chat_id="chat-ctx",
                type=ArtifactType.HTML,
                title="Other",
                content="<html>other bot secret</html>",
            )
        )

        builder = ContextBuilder()
        # Empty user message keeps the vector store out of the path entirely.
        prompt = await builder.build_enhanced_system_prompt(
            "You are a test bot.", bot_id, "", "chat-ctx"
        )

        assert "## Current HTML artifacts" in prompt
        assert "art-ctx-1" in prompt
        # The exact edited source — MSO conditional included — is in the prompt.
        assert EDITED_HTML in prompt
        assert MSO_COMMENT in prompt
        assert "project_id: proj9" in prompt
        # Another bot's artifact is never leaked into this bot's prompt.
        assert "other bot secret" not in prompt

    async def test_no_artifacts_omits_section(self, sqlite_db) -> None:
        bot_id = await make_bot()
        builder = ContextBuilder()
        prompt = await builder.build_enhanced_system_prompt(
            "You are a test bot.", bot_id, "", "chat-none"
        )
        assert "Current HTML artifacts" not in prompt


# ---------------------------------------------------------------------------
# 6. Website-preview markdown promotion helper (pure)
# ---------------------------------------------------------------------------


class TestWebsitePreviewParsing:
    def test_parses_project_id_and_preserves_mso_comment(self) -> None:
        encoded = base64.b64encode(EDITED_HTML.encode("utf-8")).decode("ascii")
        markdown = (
            "## Website built\n\n"
            "Project: `abc-123`\n\n"
            f"![Website Preview](data:text/html;base64,{encoded})\n"
        )
        preview = website_files.parse_website_preview(markdown)
        assert preview is not None
        assert preview.project_id == "abc-123"
        assert preview.slug == "index"
        assert preview.html == EDITED_HTML
        assert MSO_COMMENT in preview.html

    def test_parses_bold_project_id_variant(self) -> None:
        encoded = base64.b64encode(b"<html>hi</html>").decode("ascii")
        markdown = f"**Project ID:** `xyz-9`\n\n![Website Preview](data:text/html;base64,{encoded})"
        preview = website_files.parse_website_preview(markdown)
        assert preview is not None
        assert preview.project_id == "xyz-9"
        assert preview.html == "<html>hi</html>"

    def test_rejects_non_matching_or_corrupt_results(self) -> None:
        assert website_files.parse_website_preview("just some markdown") is None
        assert website_files.parse_website_preview("Project: `abc`\n\nno preview image") is None
        assert (
            website_files.parse_website_preview(
                "Project: `abc`\n\n![Website Preview](data:text/html;base64,!!!not-base64!!!)"
            )
            is None
        )

    def test_artifact_id_is_stable_per_bot_project_slug(self) -> None:
        first = website_files.website_preview_artifact_id("bot-1", "proj-1", "index")
        assert first == website_files.website_preview_artifact_id("bot-1", "proj-1", "index")
        assert first != website_files.website_preview_artifact_id("bot-2", "proj-1", "index")
        uuid.UUID(first)  # a valid uuid string
