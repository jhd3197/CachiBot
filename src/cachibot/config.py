"""
Cachibot Configuration

Handles loading and managing configuration from files and environment.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Try to import tomllib (Python 3.11+) or tomli as fallback
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


# Default safe imports for the sandbox
DEFAULT_ALLOWED_IMPORTS = [
    # Data handling
    "json",
    "csv",
    "xml",
    "html",
    # Text processing
    "re",
    "string",
    "textwrap",
    # Math and data
    "math",
    "statistics",
    "decimal",
    "fractions",
    "random",
    "collections",
    "itertools",
    "functools",
    # Date/time
    "datetime",
    "time",
    "calendar",
    # Data structures
    "dataclasses",
    "enum",
    "typing",
    # Utilities
    "copy",
    "pprint",
    "operator",
    "bisect",
    "heapq",
    # Encoding
    "base64",
    "hashlib",
    "hmac",
    # Compression (read-only)
    "gzip",
    "zipfile",
    "tarfile",
]


@dataclass
class AgentConfig:
    """Agent behavior configuration."""

    # Default to Kimi K2.5 via Moonshot
    model: str = "moonshot/kimi-k2.5"
    # Cheap/fast model for utility tasks (name gen, questions).
    # Falls back to main model if empty.
    utility_model: str = ""
    max_iterations: int = 20
    approve_actions: bool = False
    temperature: float = 0.6  # Moonshot recommends 0.6 for instant mode
    max_tokens: int = 4096  # Max output tokens per LLM call
    max_tool_result_length: int = 2000  # Truncate large tool results sent to the LLM


@dataclass
class SandboxConfig:
    """Python sandbox configuration."""

    allowed_imports: list[str] = field(default_factory=lambda: DEFAULT_ALLOWED_IMPORTS.copy())
    timeout_seconds: int = 30
    max_output_length: int = 10000


@dataclass
class WorkspaceConfig:
    """Workspace and security configuration."""

    allowed_paths: list[str] = field(default_factory=lambda: ["."])
    ignore_patterns: list[str] = field(
        default_factory=lambda: [
            "node_modules",
            ".git",
            "__pycache__",
            "*.pyc",
            ".env",
            "venv",
            ".venv",
        ]
    )


@dataclass
class DisplayConfig:
    """Display and output configuration."""

    show_thinking: bool = True
    show_cost: bool = True
    style: str = "detailed"  # "detailed" or "compact"


@dataclass
class KnowledgeConfig:
    """Knowledge base / RAG pipeline configuration."""

    chunk_size: int = 500  # Target words per chunk
    chunk_overlap: int = 50  # Overlap words between chunks
    top_k: int = 3  # Max document chunks returned per query
    min_similarity: float = 0.3  # Minimum cosine similarity threshold
    embedding_model: str = "BAAI/bge-small-en-v1.5"  # fastembed model name
    max_history_messages: int = 10  # Context history limit


@dataclass
class AuthConfig:
    """Authentication configuration."""

    jwt_secret: str = ""  # Required - set via CACHIBOT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


@dataclass
class PlatformConfig:
    """Platform deployment configuration for website ↔ V2 auth bridge."""

    deploy_mode: str = "selfhosted"  # "selfhosted" or "cloud"
    website_jwt_secret: str = ""  # Shared secret for platform launch tokens
    website_url: str = ""  # e.g. "https://cachibot.ai"


@dataclass
class DatabaseConfig:
    """Database configuration for PostgreSQL."""

    url: str = "postgresql+asyncpg://cachibot:cachibot@localhost:5433/cachibot"
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600  # seconds
    echo: bool = False

    def get_url(self) -> str:
        """Get the database URL with automatic protocol conversion.

        Converts postgres:// and postgresql:// to postgresql+asyncpg://
        for SQLAlchemy async compatibility.
        """
        url = self.url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@dataclass
class Config:
    """
    Main configuration container for Cachibot.

    Loads configuration from (in order of precedence):
    1. Explicit parameters
    2. Workspace cachibot.toml
    3. User's ~/.cachibot.toml
    4. Environment variables
    5. Defaults
    """

    agent: AgentConfig = field(default_factory=AgentConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    platform: PlatformConfig = field(default_factory=PlatformConfig)

    # Runtime paths
    workspace_path: Path = field(default_factory=Path.cwd)
    config_path: Path | None = None

    @classmethod
    def load(
        cls,
        workspace: Path | str | None = None,
        config_file: Path | str | None = None,
    ) -> "Config":
        """
        Load configuration from files and environment.

        Args:
            workspace: Working directory for the agent
            config_file: Explicit config file path (optional)

        Returns:
            Loaded Config instance
        """
        config = cls()

        # Set workspace
        if workspace:
            config.workspace_path = Path(workspace).resolve()
        else:
            config.workspace_path = Path.cwd()

        # Load from environment
        config._load_from_env()

        # Load from user config (~/.cachibot.toml)
        user_config = Path.home() / ".cachibot.toml"
        if user_config.exists():
            config._load_from_file(user_config)

        # Load from workspace config
        workspace_config = config.workspace_path / "cachibot.toml"
        if workspace_config.exists():
            config._load_from_file(workspace_config)

        # Load from explicit config file (highest precedence)
        if config_file:
            config_path = Path(config_file)
            if config_path.exists():
                config._load_from_file(config_path)
                config.config_path = config_path

        # Backward compatibility: warn if legacy SQLite database exists
        sqlite_path = Path.home() / ".cachibot" / "cachibot.db"
        if sqlite_path.exists():
            logger.warning(
                "Legacy SQLite database found at %s. "
                "Run 'python scripts/migrate_sqlite_to_postgres.py' to migrate your data to "
                "PostgreSQL. The SQLite file will not be used by default.",
                sqlite_path,
            )

        return config

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""

        # Model selection
        if model := os.getenv("CACHIBOT_MODEL"):
            self.agent.model = model

        # Utility model (cheap/fast for name gen, questions, etc.)
        if utility_model := os.getenv("CACHIBOT_UTILITY_MODEL"):
            self.agent.utility_model = utility_model

        # Approval mode
        if os.getenv("CACHIBOT_APPROVE", "").lower() in ("1", "true", "yes"):
            self.agent.approve_actions = True

        # Max iterations
        if max_iter := os.getenv("CACHIBOT_MAX_ITERATIONS"):
            try:
                self.agent.max_iterations = int(max_iter)
            except ValueError:
                pass

        # Temperature
        if temp := os.getenv("CACHIBOT_TEMPERATURE"):
            try:
                self.agent.temperature = float(temp)
            except ValueError:
                pass

        # Max tokens
        if max_tok := os.getenv("CACHIBOT_MAX_TOKENS"):
            try:
                self.agent.max_tokens = int(max_tok)
            except ValueError:
                pass

        # Sandbox timeout
        if timeout := os.getenv("CACHIBOT_SANDBOX_TIMEOUT"):
            try:
                self.sandbox.timeout_seconds = int(timeout)
            except ValueError:
                pass

        # Database URL (highest priority override)
        if database_url := os.getenv("DATABASE_URL"):
            self.database.url = database_url

        # Auth settings
        if jwt_secret := os.getenv("CACHIBOT_JWT_SECRET"):
            self.auth.jwt_secret = jwt_secret
        if jwt_algo := os.getenv("CACHIBOT_JWT_ALGORITHM"):
            self.auth.jwt_algorithm = jwt_algo
        if expire_mins := os.getenv("CACHIBOT_ACCESS_TOKEN_EXPIRE_MINUTES"):
            try:
                self.auth.access_token_expire_minutes = int(expire_mins)
            except ValueError:
                pass
        if expire_days := os.getenv("CACHIBOT_REFRESH_TOKEN_EXPIRE_DAYS"):
            try:
                self.auth.refresh_token_expire_days = int(expire_days)
            except ValueError:
                pass

        # Platform settings
        if deploy_mode := os.getenv("CACHIBOT_DEPLOY_MODE"):
            self.platform.deploy_mode = deploy_mode
        if website_jwt_secret := os.getenv("CACHIBOT_WEBSITE_JWT_SECRET"):
            self.platform.website_jwt_secret = website_jwt_secret
        if website_url := os.getenv("CACHIBOT_WEBSITE_URL"):
            self.platform.website_url = website_url

    def _load_from_file(self, path: Path) -> None:
        """Load configuration from a TOML file."""

        if tomllib is None:
            # Can't parse TOML, skip
            return

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return

        self._apply_dict(data)

    def _apply_dict(self, data: dict[str, Any]) -> None:
        """Apply a configuration dictionary."""

        if agent_data := data.get("agent"):
            if "model" in agent_data:
                self.agent.model = agent_data["model"]
            if "max_iterations" in agent_data:
                self.agent.max_iterations = agent_data["max_iterations"]
            if "approve_actions" in agent_data:
                self.agent.approve_actions = agent_data["approve_actions"]
            if "temperature" in agent_data:
                self.agent.temperature = agent_data["temperature"]
            if "max_tokens" in agent_data:
                self.agent.max_tokens = agent_data["max_tokens"]
            if "utility_model" in agent_data:
                self.agent.utility_model = agent_data["utility_model"]

        if sandbox_data := data.get("sandbox"):
            if "allowed_imports" in sandbox_data:
                self.sandbox.allowed_imports = sandbox_data["allowed_imports"]
            if "timeout_seconds" in sandbox_data:
                self.sandbox.timeout_seconds = sandbox_data["timeout_seconds"]
            if "max_output_length" in sandbox_data:
                self.sandbox.max_output_length = sandbox_data["max_output_length"]

        if workspace_data := data.get("workspace"):
            if "allowed_paths" in workspace_data:
                self.workspace.allowed_paths = workspace_data["allowed_paths"]
            if "ignore_patterns" in workspace_data:
                self.workspace.ignore_patterns = workspace_data["ignore_patterns"]

        if display_data := data.get("display"):
            if "show_thinking" in display_data:
                self.display.show_thinking = display_data["show_thinking"]
            if "show_cost" in display_data:
                self.display.show_cost = display_data["show_cost"]
            if "style" in display_data:
                self.display.style = display_data["style"]

        if knowledge_data := data.get("knowledge"):
            if "chunk_size" in knowledge_data:
                self.knowledge.chunk_size = knowledge_data["chunk_size"]
            if "chunk_overlap" in knowledge_data:
                self.knowledge.chunk_overlap = knowledge_data["chunk_overlap"]
            if "top_k" in knowledge_data:
                self.knowledge.top_k = knowledge_data["top_k"]
            if "min_similarity" in knowledge_data:
                self.knowledge.min_similarity = knowledge_data["min_similarity"]
            if "embedding_model" in knowledge_data:
                self.knowledge.embedding_model = knowledge_data["embedding_model"]
            if "max_history_messages" in knowledge_data:
                self.knowledge.max_history_messages = knowledge_data["max_history_messages"]

        if auth_data := data.get("auth"):
            if "jwt_secret" in auth_data:
                self.auth.jwt_secret = auth_data["jwt_secret"]
            if "jwt_algorithm" in auth_data:
                self.auth.jwt_algorithm = auth_data["jwt_algorithm"]
            if "access_token_expire_minutes" in auth_data:
                self.auth.access_token_expire_minutes = auth_data["access_token_expire_minutes"]
            if "refresh_token_expire_days" in auth_data:
                self.auth.refresh_token_expire_days = auth_data["refresh_token_expire_days"]

        if platform_data := data.get("platform"):
            if "deploy_mode" in platform_data:
                self.platform.deploy_mode = platform_data["deploy_mode"]
            if "website_jwt_secret" in platform_data:
                self.platform.website_jwt_secret = platform_data["website_jwt_secret"]
            if "website_url" in platform_data:
                self.platform.website_url = platform_data["website_url"]

        if db_data := data.get("database"):
            if "url" in db_data:
                self.database.url = db_data["url"]
            if "pool_size" in db_data:
                self.database.pool_size = db_data["pool_size"]
            if "max_overflow" in db_data:
                self.database.max_overflow = db_data["max_overflow"]
            if "pool_recycle" in db_data:
                self.database.pool_recycle = db_data["pool_recycle"]
            if "echo" in db_data:
                self.database.echo = db_data["echo"]

    def is_path_allowed(self, path: Path | str) -> bool:
        """
        Check if a path is within the allowed workspace.

        Security measure to prevent the agent from accessing
        files outside the designated workspace.

        Args:
            path: Path to check

        Returns:
            True if path is allowed, False otherwise
        """
        target = Path(path).resolve()
        workspace = self.workspace_path.resolve()

        # Check if path is within workspace
        try:
            target.relative_to(workspace)
            return True
        except ValueError:
            return False

    def should_ignore(self, path: Path | str) -> bool:
        """
        Check if a path matches ignore patterns.

        Args:
            path: Path to check

        Returns:
            True if path should be ignored
        """
        from fnmatch import fnmatch

        path_str = str(path)
        name = Path(path).name

        for pattern in self.workspace.ignore_patterns:
            if fnmatch(name, pattern) or fnmatch(path_str, pattern):
                return True

        return False
