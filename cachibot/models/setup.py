"""Pydantic models for the setup/onboarding endpoints."""

from pydantic import BaseModel

# ---------- Database ----------


class DatabaseTestRequest(BaseModel):
    """Test a PostgreSQL connection."""

    host: str = "localhost"
    port: int = 5432
    database: str = "cachibot"
    username: str = "postgres"
    password: str = ""


class DatabaseTestResponse(BaseModel):
    """Result of a database connection test."""

    success: bool
    message: str
    db_version: str = ""


class DatabaseSetupRequest(BaseModel):
    """Save database configuration."""

    db_type: str = "sqlite"  # "sqlite" or "postgresql"
    host: str = "localhost"
    port: int = 5432
    database: str = "cachibot"
    username: str = "postgres"
    password: str = ""


class DatabaseStatusResponse(BaseModel):
    """Current database configuration status."""

    db_type: str  # "sqlite" or "postgresql"
    url_configured: bool
    restart_required: bool = False


# ---------- SMTP ----------


class SmtpTestRequest(BaseModel):
    """Test an SMTP connection."""

    host: str
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    send_test_to: str = ""  # Optional: send a test email to this address
    from_address: str = ""


class SmtpTestResponse(BaseModel):
    """Result of an SMTP connection test."""

    success: bool
    message: str


class SmtpSetupRequest(BaseModel):
    """Save SMTP configuration."""

    host: str
    port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""
    use_tls: bool = True


class SmtpStatusResponse(BaseModel):
    """Current SMTP configuration status."""

    configured: bool
    host: str = ""
    port: int = 587
    from_address: str = ""
    use_tls: bool = True
