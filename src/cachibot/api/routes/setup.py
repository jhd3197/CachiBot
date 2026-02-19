"""Setup/onboarding API endpoints for database and SMTP configuration."""

import asyncio
import logging
import smtplib
from typing import Any
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, status

from cachibot.api.auth import get_current_user, get_current_user_optional
from cachibot.models.auth import User
from cachibot.models.setup import (
    DatabaseSetupRequest,
    DatabaseStatusResponse,
    DatabaseTestRequest,
    DatabaseTestResponse,
    SmtpSetupRequest,
    SmtpStatusResponse,
    SmtpTestRequest,
    SmtpTestResponse,
)
from cachibot.storage.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# DATABASE
# =============================================================================


@router.get("/setup/database/status", response_model=DatabaseStatusResponse)
async def database_status(
    user: User = Depends(get_current_user),
) -> DatabaseStatusResponse:
    """Get current database configuration status."""
    from cachibot.config import Config

    config = Config.load()
    url = config.database.url

    if url and "postgresql" in url:
        db_type = "postgresql"
    else:
        db_type = "sqlite"

    return DatabaseStatusResponse(
        db_type=db_type,
        url_configured=bool(url),
    )


@router.post("/setup/database/test", response_model=DatabaseTestResponse)
async def test_database(
    req: DatabaseTestRequest,
    user: User = Depends(get_current_user),
) -> DatabaseTestResponse:
    """Test a PostgreSQL database connection."""
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        password = quote_plus(req.password) if req.password else ""
        url = (
            f"postgresql+asyncpg://{quote_plus(req.username)}:{password}"
            f"@{req.host}:{req.port}/{quote_plus(req.database)}"
        )

        engine = create_async_engine(url, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT version()"))
                version = result.scalar() or ""
        finally:
            await engine.dispose()

        return DatabaseTestResponse(
            success=True,
            message="Connection successful",
            db_version=str(version),
        )
    except Exception as exc:
        return DatabaseTestResponse(
            success=False,
            message=str(exc),
        )


@router.post("/setup/database/save", response_model=DatabaseStatusResponse)
async def save_database(
    req: DatabaseSetupRequest,
    user: User = Depends(get_current_user),
) -> DatabaseStatusResponse:
    """Save database configuration to ~/.cachibot.toml."""
    from cachibot.config import Config

    config = Config.load()

    if req.db_type == "sqlite":
        config.database.url = ""
    else:
        password = quote_plus(req.password) if req.password else ""
        config.database.url = (
            f"postgresql+asyncpg://{quote_plus(req.username)}:{password}"
            f"@{req.host}:{req.port}/{quote_plus(req.database)}"
        )

    config.save_database_config()

    return DatabaseStatusResponse(
        db_type=req.db_type,
        url_configured=bool(config.database.url),
        restart_required=req.db_type == "postgresql",
    )


# =============================================================================
# SMTP
# =============================================================================


@router.get("/setup/smtp/status", response_model=SmtpStatusResponse)
async def smtp_status(
    user: User = Depends(get_current_user),
) -> SmtpStatusResponse:
    """Get current SMTP configuration status."""
    from cachibot.config import Config

    config = Config.load()

    return SmtpStatusResponse(
        configured=bool(config.smtp.host),
        host=config.smtp.host,
        port=config.smtp.port,
        from_address=config.smtp.from_address,
        use_tls=config.smtp.use_tls,
    )


def _test_smtp_sync(
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
    from_address: str,
    send_test_to: str,
) -> SmtpTestResponse:
    """Synchronous SMTP test (run in thread)."""
    try:
        # Port 465 = implicit SSL, others = STARTTLS
        server: smtplib.SMTP | smtplib.SMTP_SSL
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        try:
            # Skip login if no credentials (open relay)
            if username:
                server.login(username, password)

            # Optionally send a test email
            if send_test_to and from_address:
                from email.mime.text import MIMEText

                msg = MIMEText("This is a test email from CachiBot setup.")
                msg["Subject"] = "CachiBot SMTP Test"
                msg["From"] = from_address
                msg["To"] = send_test_to
                server.sendmail(from_address, [send_test_to], msg.as_string())
                return SmtpTestResponse(
                    success=True,
                    message=f"Connection successful — test email sent to {send_test_to}",
                )

            return SmtpTestResponse(
                success=True,
                message="SMTP connection and authentication successful",
            )
        finally:
            server.quit()
    except smtplib.SMTPAuthenticationError:
        return SmtpTestResponse(
            success=False,
            message="Authentication failed — check username and password",
        )
    except Exception as exc:
        return SmtpTestResponse(success=False, message=str(exc))


@router.post("/setup/smtp/test", response_model=SmtpTestResponse)
async def test_smtp(
    req: SmtpTestRequest,
    user: User = Depends(get_current_user),
) -> SmtpTestResponse:
    """Test an SMTP connection (and optionally send a test email)."""
    return await asyncio.to_thread(
        _test_smtp_sync,
        req.host,
        req.port,
        req.username,
        req.password,
        req.use_tls,
        req.from_address,
        req.send_test_to,
    )


@router.post("/setup/smtp/save", response_model=SmtpStatusResponse)
async def save_smtp(
    req: SmtpSetupRequest,
    user: User = Depends(get_current_user),
) -> SmtpStatusResponse:
    """Save SMTP configuration to ~/.cachibot.toml."""
    from cachibot.config import Config

    config = Config.load()
    config.smtp.host = req.host
    config.smtp.port = req.port
    config.smtp.username = req.username
    config.smtp.password = req.password
    config.smtp.from_address = req.from_address
    config.smtp.use_tls = req.use_tls
    config.save_smtp_config()

    return SmtpStatusResponse(
        configured=bool(req.host),
        host=req.host,
        port=req.port,
        from_address=req.from_address,
        use_tls=req.use_tls,
    )


# =============================================================================
# LEGACY DATABASE UPGRADE
# =============================================================================


@router.post("/setup/upgrade/reset")
async def reset_legacy_database(
    user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """Reset a legacy V1 database by backing it up and creating a fresh one.

    Requires authentication when users exist; unauthenticated only during
    first-time setup (no users in the database).
    """
    import cachibot.storage.db as db_mod

    user_repo = UserRepository()
    if await user_repo.get_user_count() > 0 and user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication required",
        )

    if not db_mod.legacy_db_detected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No legacy database detected",
        )

    backup_path = await db_mod.reset_database()
    return {"status": "reset", "backup_path": backup_path}


@router.post("/setup/upgrade/keep")
async def keep_legacy_database(
    user: User | None = Depends(get_current_user_optional),
) -> dict[str, str]:
    """Keep the legacy V1 database and clear the detection flag for this session.

    Requires authentication when users exist; unauthenticated only during
    first-time setup (no users in the database).
    """
    import cachibot.storage.db as db_mod

    user_repo = UserRepository()
    if await user_repo.get_user_count() > 0 and user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication required",
        )

    if not db_mod.legacy_db_detected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No legacy database detected",
        )

    db_mod.legacy_db_detected = False
    return {"status": "kept"}
