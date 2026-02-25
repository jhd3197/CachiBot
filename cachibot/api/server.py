"""
FastAPI Server for Cachibot

Main application entry point with CORS and route registration.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from cachibot import __version__
from cachibot.api.room_websocket import router as room_ws_router
from cachibot.api.routes import (
    admin_executions,
    auth,
    bot_env,
    bots,
    chat,
    chats,
    coding_agents,
    commands,
    config,
    connections,
    contacts,
    creation,
    custom_instructions,
    developer,
    documents,
    executions,
    groups,
    health,
    instructions,
    knowledge,
    marketplace,
    mobile_pair,
    models,
    openai_compat,
    platform_tools,
    platforms,
    plugins,
    providers,
    room_tasks,
    rooms,
    scripts,
    setup,
    skills,
    telemetry,
    update,
    work,
)
from cachibot.api.routes.assets import chat_asset_router, room_asset_router
from cachibot.api.routes.webhooks import custom as wh_custom
from cachibot.api.routes.webhooks import line as wh_line
from cachibot.api.routes.webhooks import teams as wh_teams
from cachibot.api.routes.webhooks import viber as wh_viber
from cachibot.api.routes.webhooks import whatsapp as wh_whatsapp
from cachibot.api.voice_websocket import router as voice_ws_router
from cachibot.api.websocket import router as ws_router
from cachibot.services.job_runner import get_job_runner
from cachibot.services.log_retention import get_log_retention_service
from cachibot.services.message_processor import get_message_processor
from cachibot.services.platform_manager import get_platform_manager
from cachibot.services.scheduler_service import get_scheduler_service
from cachibot.storage.db import close_db, init_db

# Find the frontend dist directory
# 1. Bundled in the package (pip install case): cachibot/frontend_dist/
_BUNDLED_DIST = Path(__file__).parent.parent / "frontend_dist"
# 2. Development repo (editable install / local dev): repo_root/frontend/dist/
_DEV_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

FRONTEND_DIST = _BUNDLED_DIST if (_BUNDLED_DIST / "index.html").exists() else _DEV_DIST


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    import logging

    # ---- Centralized logging (file handler + secret masking — must be first) ----
    from cachibot.logging_config import setup_logging

    setup_logging()

    startup_logger = logging.getLogger("cachibot.startup")

    # ---- Installation health check (P1) ----
    try:
        from cachibot.services.update_service import (
            cleanup_corrupted_packages,
            detect_corruption,
        )

        report = detect_corruption()
        if report.is_corrupted:
            startup_logger.warning("Installation corruption detected: %s", report.details)
            removed = cleanup_corrupted_packages()
            if removed:
                startup_logger.info(
                    "Auto-cleaned %d corrupted artifact(s): %s",
                    len(removed),
                    ", ".join(removed),
                )
    except Exception as exc:
        startup_logger.debug("Corruption check skipped: %s", exc)

    # ---- Stale process guard (kill orphaned uvicorn children) ----
    from cachibot.services.pid_guard import kill_stale_server, remove_pid_file, write_pid_file

    kill_stale_server()
    _pid_port = int(os.environ.get("_CACHIBOT_PORT", "5870"))
    write_pid_file(port=_pid_port)

    # Startup — initialize database
    try:
        await init_db()
    except Exception as e:
        startup_logger.error("Database initialization failed: %s", e)
        startup_logger.error("Check your DATABASE_URL or remove it to use SQLite (default).")
        raise

    # Mark this version as last-known-good after successful startup
    from cachibot.services.update_service import mark_current_version_good

    mark_current_version_good()

    # Set up message processor for platform connections
    platform_manager = get_platform_manager()
    message_processor = get_message_processor()
    platform_manager.set_message_processor(message_processor.process_message)

    # Reset stale connection statuses — after a restart they are disconnected
    await platform_manager.reset_all_statuses()

    # Auto-reconnect connections that were active before restart
    await platform_manager.auto_reconnect_all()

    # Start health monitoring for active adapters
    await platform_manager.start_health_monitor()

    # Start the scheduler service (polls for due schedules & reminders)
    scheduler = get_scheduler_service()
    try:
        from cachibot.config import Config

        _config = Config.load(workspace=app.state.workspace)
        scheduler.timezone = _config.timezone
    except Exception:
        pass
    await scheduler.start()

    # Start the job runner service (executes Work tasks as background Jobs)
    job_runner = get_job_runner()
    await job_runner.start()

    # Start the log retention service (cleans up old execution logs)
    log_retention = get_log_retention_service()
    await log_retention.start()

    # Start telemetry scheduler (opt-in, non-blocking, silent on failure)
    try:
        from cachibot.telemetry.scheduler import start_telemetry_scheduler

        await start_telemetry_scheduler()
    except Exception as exc:
        startup_logger.debug("Telemetry scheduler start skipped: %s", exc)

    # Start terms-version checker (polls cachibot.ai for ToS updates)
    try:
        from cachibot.services.terms_checker import start_terms_checker

        await start_terms_checker()
    except Exception as exc:
        startup_logger.debug("Terms checker start skipped: %s", exc)

    yield

    # Shutdown
    try:
        from cachibot.services.terms_checker import stop_terms_checker

        await stop_terms_checker()
    except Exception:
        pass
    try:
        from cachibot.telemetry.scheduler import stop_telemetry_scheduler

        await stop_telemetry_scheduler()
    except Exception:
        pass
    await log_retention.stop()
    await job_runner.stop()
    await scheduler.stop()
    await platform_manager.stop_health_monitor()
    # Disconnect all platform adapters
    await platform_manager.disconnect_all()
    await close_db()
    remove_pid_file()


def create_app(
    workspace: Path | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """
    Create the FastAPI application.

    Args:
        workspace: Default workspace path
        cors_origins: Allowed CORS origins

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Cachibot API",
        description="AI Agent API with WebSocket streaming",
        version=__version__,
        lifespan=lifespan,
    )

    # Store workspace in app state
    app.state.workspace = workspace or Path.cwd()

    # CORS middleware — include LAN IPs so mobile and other local devices work
    from cachibot.api.routes.mobile_pair import _get_lan_ips

    origins = cors_origins or [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    port_env = os.environ.get("_CACHIBOT_PORT", "5870")
    for ip in _get_lan_ips():
        origins.append(f"http://{ip}:{port_env}")
        origins.append(f"http://{ip}:5173")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )

    # Register routes
    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(mobile_pair.router, prefix="/api", tags=["mobile-pairing"])
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(models.router, prefix="/api", tags=["models"])
    app.include_router(providers.router, prefix="/api", tags=["providers"])
    app.include_router(config.router, prefix="/api", tags=["config"])
    app.include_router(coding_agents.router, prefix="/api", tags=["coding-agents"])
    app.include_router(commands.router, tags=["commands"])
    app.include_router(update.router, prefix="/api", tags=["update"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(creation.router, prefix="/api", tags=["creation"])
    app.include_router(bots.router, tags=["bots"])
    app.include_router(groups.router, tags=["groups"])
    app.include_router(chats.router, tags=["chats"])
    app.include_router(contacts.router, tags=["contacts"])
    app.include_router(connections.router, tags=["connections"])
    app.include_router(bot_env.router, tags=["bot-environment"])
    app.include_router(bot_env.platform_router, tags=["platform-environment"])
    app.include_router(bot_env.skill_config_router, tags=["skill-config"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(instructions.router, tags=["instructions"])
    app.include_router(custom_instructions.router, tags=["custom-instructions"])
    app.include_router(knowledge.router, tags=["knowledge"])
    app.include_router(marketplace.router, tags=["marketplace"])
    app.include_router(platforms.router, tags=["platforms"])
    app.include_router(skills.router, tags=["skills"])
    app.include_router(plugins.router, tags=["plugins"])
    app.include_router(platform_tools.router, tags=["platform-tools"])
    app.include_router(work.router, tags=["work"])
    app.include_router(scripts.router, tags=["scripts"])
    app.include_router(executions.router, tags=["executions"])
    app.include_router(admin_executions.router, tags=["admin-executions"])
    app.include_router(setup.router, prefix="/api", tags=["setup"])
    app.include_router(telemetry.router, prefix="/api", tags=["telemetry"])
    app.include_router(rooms.router, tags=["rooms"])
    app.include_router(room_tasks.router, tags=["room-tasks"])
    app.include_router(room_asset_router, tags=["room-assets"])
    app.include_router(chat_asset_router, tags=["chat-assets"])
    app.include_router(developer.router, tags=["developer"])
    app.include_router(openai_compat.router, tags=["openai-compat"])
    app.include_router(ws_router, tags=["websocket"])
    app.include_router(voice_ws_router, tags=["voice"])
    app.include_router(room_ws_router, tags=["room-websocket"])

    # Platform webhook routes
    app.include_router(wh_whatsapp.router, tags=["webhooks"])
    app.include_router(wh_teams.router, tags=["webhooks"])
    app.include_router(wh_line.router, tags=["webhooks"])
    app.include_router(wh_viber.router, tags=["webhooks"])
    app.include_router(wh_custom.router, tags=["webhooks"])

    # Check if frontend dist exists
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        # Mount static assets (js, css, etc.)
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/")
        async def serve_spa() -> FileResponse:
            """Serve the frontend SPA."""
            return FileResponse(
                FRONTEND_DIST / "index.html",
                headers={"Cache-Control": "no-cache, must-revalidate"},
            )

        # SPA fallback: serve index.html for non-API GET requests that don't
        # match any route. Using an exception handler instead of a catch-all
        # route avoids PARTIAL-match 405 interference with API routes.
        @app.exception_handler(StarletteHTTPException)
        async def _spa_or_http_error(
            request: Request, exc: StarletteHTTPException
        ) -> FileResponse | JSONResponse:
            # For 404s on non-API GET requests, serve the SPA shell
            if (
                exc.status_code == 404
                and request.method == "GET"
                and not request.url.path.startswith("/api/")
                and not request.url.path.startswith("/ws/")
            ):
                # Check if the path matches a real static file first
                file_path = FRONTEND_DIST / request.url.path.lstrip("/")
                if file_path.exists() and file_path.is_file():
                    headers = {}
                    if request.url.path.startswith("/assets/"):
                        headers["Cache-Control"] = "public, max-age=31536000, immutable"
                    return FileResponse(file_path, headers=headers)
                return FileResponse(
                    FRONTEND_DIST / "index.html",
                    headers={"Cache-Control": "no-cache, must-revalidate"},
                )
            # Everything else: standard JSON error
            return JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
            )
    else:

        @app.get("/")
        async def root() -> dict[str, str]:
            """Root endpoint with API info."""
            return {
                "name": "Cachibot API",
                "version": __version__,
                "docs": "/docs",
                "health": "/api/health",
            }

    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 5870,
    workspace: Path | None = None,
    reload: bool = False,
) -> None:
    """
    Run the Cachibot API server.

    Args:
        host: Server host
        port: Server port
        workspace: Workspace path
        reload: Enable auto-reload for development
    """
    os.environ["_CACHIBOT_PORT"] = str(port)

    if reload:
        # Reload mode requires an import string, not an app object
        uvicorn.run(
            "cachibot.api.server:app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=[str(Path(__file__).parent.parent)],
            log_level="info",
        )
    else:
        app = create_app(workspace=workspace)
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
        )


# For running with `uvicorn cachibot.api.server:app`
app = create_app()
