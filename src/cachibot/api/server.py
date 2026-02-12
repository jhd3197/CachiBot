"""
FastAPI Server for Cachibot

Main application entry point with CORS and route registration.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cachibot import __version__
from cachibot.api.routes import (
    auth,
    bots,
    chat,
    chats,
    config,
    connections,
    contacts,
    creation,
    documents,
    health,
    instructions,
    knowledge,
    marketplace,
    models,
    plugins,
    providers,
    skills,
    update,
    work,
)
from cachibot.api.voice_websocket import router as voice_ws_router
from cachibot.api.websocket import router as ws_router
from cachibot.services.message_processor import get_message_processor
from cachibot.services.platform_manager import get_platform_manager
from cachibot.storage.database import close_db, init_db

# Find the frontend dist directory
# 1. Bundled in the package (pip install case): cachibot/frontend_dist/
_BUNDLED_DIST = Path(__file__).parent.parent / "frontend_dist"
# 2. Development repo (editable install / local dev): repo_root/frontend/dist/
_DEV_DIST = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"

FRONTEND_DIST = _BUNDLED_DIST if (_BUNDLED_DIST / "index.html").exists() else _DEV_DIST


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()

    # Set up message processor for platform connections
    platform_manager = get_platform_manager()
    message_processor = get_message_processor()
    platform_manager.set_message_processor(message_processor.process_message)

    # Reconnect platform adapters that were connected
    try:
        await platform_manager.reconnect_all()
    except Exception:
        pass  # Don't fail startup if reconnection fails

    yield

    # Shutdown
    # Disconnect all platform adapters
    await platform_manager.disconnect_all()
    await close_db()


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

    # CORS middleware
    origins = cors_origins or [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(models.router, prefix="/api", tags=["models"])
    app.include_router(providers.router, prefix="/api", tags=["providers"])
    app.include_router(config.router, prefix="/api", tags=["config"])
    app.include_router(update.router, prefix="/api", tags=["update"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(creation.router, prefix="/api", tags=["creation"])
    app.include_router(bots.router, tags=["bots"])
    app.include_router(chats.router, tags=["chats"])
    app.include_router(contacts.router, tags=["contacts"])
    app.include_router(connections.router, tags=["connections"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(instructions.router, tags=["instructions"])
    app.include_router(knowledge.router, tags=["knowledge"])
    app.include_router(marketplace.router, tags=["marketplace"])
    app.include_router(skills.router, tags=["skills"])
    app.include_router(plugins.router, tags=["plugins"])
    app.include_router(work.router, tags=["work"])
    app.include_router(ws_router, tags=["websocket"])
    app.include_router(voice_ws_router, tags=["voice"])

    # Check if frontend dist exists
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        # Mount static assets (js, css, etc.)
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/")
        async def serve_spa():
            """Serve the frontend SPA."""
            return FileResponse(FRONTEND_DIST / "index.html")

        @app.get("/{path:path}")
        async def serve_spa_routes(path: str):
            """Serve static files or fallback to index.html for SPA routing."""
            file_path = FRONTEND_DIST / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:

        @app.get("/")
        async def root():
            """Root endpoint with API info."""
            return {
                "name": "Cachibot API",
                "version": __version__,
                "docs": "/docs",
                "health": "/api/health",
            }

    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 6392,
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
    app = create_app(workspace=workspace)

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


# For running with `uvicorn cachibot.api.server:app`
app = create_app()
