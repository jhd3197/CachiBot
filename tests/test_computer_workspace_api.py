"""API tests for the C4 computer file routes: the Files-sheet workspace
listing (viewer+, never boots the computer) and "Open on computer"
(operator+, routed into the editor_open driven tool).

Same hermetic setup as test_computer_api: SQLite in a tmp dir, scripted
FakeDockerRunner/FakeVelaClient — no Docker, no network, no containers.
"""

import uuid
from typing import Any

import pytest

from cachibot.models.group import BotAccessLevel
from tests.conftest import create_test_user
from tests.test_computer_api import auth, make_shared_bot, share_bot, wake_bot

# The computer fixtures (sqlite_db/computer_env/computer_client) live in
# test_computer_api; register that module's fixtures without importing the
# names into this namespace (imported fixture names read as redefinitions).
pytest_plugins = ["tests.test_computer_api"]


FILES = {
    "bakery/index.html": "<h1>Corner Bakery</h1>\n",
    "bakery/styles.css": "body { color: #2b2118 }\n",
    "notes/todo.txt": "- [ ] water the plants\n",
}


def workspace_step_handler(files: dict[str, str]):
    """A driven-step handler answering workspace_list from a fixed file set.

    Emits folder entries for the first path segment, like Vela's own listing.
    """

    def handler(tool: str, arguments: dict[str, Any], _step_id: str) -> dict[str, Any]:
        if tool == "workspace_list":
            prefix = arguments.get("path") or ""
            entries: list[dict[str, Any]] = []
            seen: set[str] = set()
            for path, content in files.items():
                if prefix and not path.startswith(prefix + "/"):
                    continue
                rest = path[len(prefix) + 1 :] if prefix else path
                if "/" in rest:
                    name = rest.split("/", 1)[0]
                    entry = {
                        "name": name,
                        "path": f"{prefix}/{name}" if prefix else name,
                        "kind": "folder",
                        "size": None,
                        "modified": None,
                    }
                else:
                    entry = {
                        "name": rest,
                        "path": path,
                        "kind": "file",
                        "size": len(content),
                        "modified": "2026-11-24T12:00:00+00:00",
                    }
                if entry["name"] in seen:
                    continue
                seen.add(entry["name"])
                entries.append(entry)
            return {"result": {"entries": entries}, "budget": {}}
        return {"result": {"tool": tool}, "budget": {}}

    return handler


@pytest.fixture
async def awake_bot(computer_env, auth_service):
    """Awake computer with the workspace/editor surfaces, driven steps scripted."""
    bot_id, owner_id, token = await make_shared_bot(auth_service, level=BotAccessLevel.OPERATOR)
    computer_env.vela.info["features"]["workspace"] = True
    computer_env.vela.info["features"]["editor"] = True
    computer_env.vela.step_handler = workspace_step_handler(FILES)
    await wake_bot(computer_env, bot_id)
    return bot_id, owner_id, token


class TestWorkspaceListing:
    async def test_requires_auth(self, computer_client, awake_bot) -> None:  # noqa: F811
        bot_id, _owner, _ = awake_bot
        resp = await computer_client.get(f"/api/bots/{bot_id}/computer/workspace")
        assert resp.status_code == 401

    async def test_viewer_can_list_root(self, computer_client, auth_service, awake_bot) -> None:  # noqa: F811
        bot_id, owner_id, _ = awake_bot
        viewer_token = await self._viewer_token(auth_service, bot_id, owner_id)
        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/workspace", headers=auth(viewer_token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["path"] == ""
        names = {e["name"] for e in body["entries"]}
        # Only the folder roots show at the top level.
        assert names == {"bakery", "notes"}

    async def test_lists_a_subfolder(self, computer_client, awake_bot) -> None:  # noqa: F811
        bot_id, owner_id, token = awake_bot
        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/workspace",
            params={"path": "bakery"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert {(e["name"], e["path"], e["size"]) for e in entries} == {
            ("index.html", "bakery/index.html", len("<h1>Corner Bakery</h1>\n")),
            ("styles.css", "bakery/styles.css", len("body { color: #2b2118 }\n")),
        }

    async def test_accepts_workspace_prefixed_paths(self, computer_client, awake_bot) -> None:  # noqa: F811
        bot_id, owner_id, token = awake_bot
        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/workspace",
            params={"path": "/workspace/bakery"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert {e["name"] for e in resp.json()["entries"]} == {"index.html", "styles.css"}

    async def test_escaping_path_is_422(self, computer_client, awake_bot) -> None:  # noqa: F811
        bot_id, owner_id, token = awake_bot
        for bad in ("..", "../etc", "a/../../b"):
            resp = await computer_client.get(
                f"/api/bots/{bot_id}/computer/workspace",
                params={"path": bad},
                headers=auth(token),
            )
            assert resp.status_code == 422, bad

    async def test_asleep_is_409_and_does_not_wake(
        self, computer_client, auth_service, computer_env
    ) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.OPERATOR)
        computer_env.vela.info["features"]["workspace"] = True
        computer_env.vela.step_handler = workspace_step_handler(FILES)
        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/workspace", headers=auth(token)
        )
        assert resp.status_code == 409
        assert "wake" in resp.json()["detail"]
        # Browsing never boots the computer: no container was started.
        assert computer_env.runner.calls_for("run") == []

    async def _viewer_token(self, auth_service, bot_id: str, owner_id: str) -> str:
        """Share the bot with a fresh viewer; return their token."""
        viewer, _ = await create_test_user(
            auth_service,
            email=f"v-{uuid.uuid4().hex[:6]}@test.com",
            username=f"v{uuid.uuid4().hex[:6]}",
        )
        await share_bot(bot_id, viewer.id, BotAccessLevel.VIEWER, owner_id)
        return auth_service.create_access_token(viewer.id, "user")


class TestEditorOpen:
    async def test_viewer_cannot_open(self, computer_client, auth_service, awake_bot) -> None:  # noqa: F811
        bot_id, owner_id, _ = awake_bot
        viewer_token = await TestWorkspaceListing()._viewer_token(auth_service, bot_id, owner_id)
        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/editor/open",
            headers=auth(viewer_token),
            json={"path": "bakery/index.html"},
        )
        assert resp.status_code == 403

    async def test_operator_open_runs_the_editor_step(
        self, computer_client, computer_env, awake_bot
    ) -> None:  # noqa: F811
        bot_id, owner_id, token = awake_bot
        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/editor/open",
            headers=auth(token),
            json={"path": "/workspace/bakery/index.html"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        step = computer_env.vela.step_calls[-1]
        assert step["tool"] == "editor_open"
        assert step["arguments"] == {"path": "bakery/index.html"}

    async def test_normalizes_the_path_before_the_step(
        self, computer_client, computer_env, awake_bot
    ) -> None:  # noqa: F811
        bot_id, owner_id, token = awake_bot
        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/editor/open",
            headers=auth(token),
            json={"path": "./bakery/index.html"},
        )
        assert resp.status_code == 200
        step = computer_env.vela.step_calls[-1]
        assert step["arguments"] == {"path": "bakery/index.html"}

    async def test_escaping_path_is_422(self, computer_client, awake_bot) -> None:  # noqa: F811
        bot_id, owner_id, token = awake_bot
        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/editor/open",
            headers=auth(token),
            json={"path": "../secrets.txt"},
        )
        assert resp.status_code == 422

    async def test_not_awake_is_409(self, computer_client, auth_service, computer_env) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.OPERATOR)
        computer_env.vela.info["features"]["editor"] = True
        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/editor/open",
            headers=auth(token),
            json={"path": "bakery/index.html"},
        )
        assert resp.status_code == 409
        assert computer_env.runner.calls_for("run") == []

    async def test_step_refusal_is_a_plain_409(
        self, computer_client, computer_env, awake_bot
    ) -> None:  # noqa: F811
        bot_id, owner_id, token = awake_bot

        def refusing(_tool: str, _arguments: dict[str, Any], _step_id: str) -> dict[str, Any]:
            return {
                "refusal": {"code": "not_found", "detail": "No such file.", "retryable": False},
                "budget": {},
            }

        computer_env.vela.step_handler = refusing
        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/editor/open",
            headers=auth(token),
            json={"path": "missing.txt"},
        )
        assert resp.status_code == 409
        assert "No such file." in resp.json()["detail"]
