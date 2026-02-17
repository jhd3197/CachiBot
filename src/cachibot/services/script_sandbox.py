"""
Script Sandbox — automation-specific wrapper around Tukuy's PythonSandbox.

Provides stricter import restrictions and auto-deny for approval requests
in unattended execution mode.
"""

import asyncio
import io
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Stricter than interactive mode — no archive modules
AUTOMATION_ALLOWED_IMPORTS = [
    "json", "csv", "re", "string", "textwrap",
    "math", "statistics", "decimal", "fractions", "random",
    "collections", "itertools", "functools", "operator",
    "datetime", "time", "calendar",
    "dataclasses", "enum", "typing",
    "copy", "pprint", "bisect", "heapq",
    "base64", "hashlib", "hmac",
]

AUTOMATION_ALLOWED_IMPORTS_SET = set(AUTOMATION_ALLOWED_IMPORTS)


@dataclass
class AutomationResourceLimits:
    """Resource limits for automation execution."""

    max_cpu_seconds: float = 30.0
    max_memory_bytes: int = 256 * 1024 * 1024  # 256 MB
    max_output_bytes: int = 1024 * 1024  # 1 MB
    max_output_chars: int = 10_000
    max_agent_iterations: int = 10
    max_wall_seconds: float = 300.0  # 5 minutes


@dataclass
class ScriptExecutionResult:
    """Result of a script execution."""

    success: bool
    output: str | None = None
    error: str | None = None
    exit_code: int = 0
    duration_ms: int = 0


@dataclass
class ScriptSandbox:
    """Automation-specific sandbox wrapping Tukuy's PythonSandbox."""

    bot_id: str
    timeout_seconds: int = 300
    max_memory_mb: int = 256
    allowed_imports: list[str] = field(default_factory=list)
    resource_limits: AutomationResourceLimits = field(
        default_factory=AutomationResourceLimits
    )

    async def execute(
        self,
        source_code: str,
        context: dict | None = None,
    ) -> ScriptExecutionResult:
        """Execute a script in the sandbox with automation restrictions."""
        import time

        start = time.monotonic()

        # Merge allowed imports: automation defaults + script-specific
        allowed = list(AUTOMATION_ALLOWED_IMPORTS_SET | set(self.allowed_imports))

        try:
            from tukuy import PythonSandbox

            sandbox = PythonSandbox(
                allowed_imports=allowed,
                timeout_seconds=min(
                    self.timeout_seconds,
                    int(self.resource_limits.max_wall_seconds),
                ),
            )

            # Pre-inject StringIO and context into globals
            exec_globals: dict = {}
            exec_globals["StringIO"] = io.StringIO
            exec_globals["__context__"] = context or {}
            exec_globals["params"] = (context or {}).get("params", {})

            # Capture stdout
            stdout_capture = io.StringIO()

            result = sandbox.execute(
                source_code,
                extra_globals=exec_globals,
                stdout=stdout_capture,
            )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            output = stdout_capture.getvalue()

            # Truncate output if too large
            if len(output) > self.resource_limits.max_output_chars:
                output = output[: self.resource_limits.max_output_chars] + "\n... (truncated)"

            if result.success:
                return ScriptExecutionResult(
                    success=True,
                    output=output or str(result.result),
                    exit_code=0,
                    duration_ms=elapsed_ms,
                )
            else:
                return ScriptExecutionResult(
                    success=False,
                    output=output,
                    error=result.error or "Unknown error",
                    exit_code=1,
                    duration_ms=elapsed_ms,
                )

        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return ScriptExecutionResult(
                success=False,
                error=f"Script timed out after {self.timeout_seconds}s",
                exit_code=124,
                duration_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return ScriptExecutionResult(
                success=False,
                error=str(exc),
                exit_code=1,
                duration_ms=elapsed_ms,
            )


def validate_script_before_save(code: str) -> "ScriptValidationResult":
    """Validate a script before saving (static analysis).

    Uses Tukuy's analyze_python() for risk assessment and import checking.
    """
    from cachibot.models.automations import ScriptValidationResult

    try:
        from tukuy.sandbox.analysis import analyze_python
    except ImportError:
        # If analysis not available, allow with warning
        return ScriptValidationResult(
            allowed=True,
            warnings=["Static analysis unavailable — skipped"],
        )

    try:
        analysis = analyze_python(code)
    except Exception as exc:
        return ScriptValidationResult(
            allowed=False,
            reason=f"Analysis failed: {exc}",
        )

    # 1. Syntax check
    if not analysis.syntax_valid:
        return ScriptValidationResult(
            allowed=False,
            reason=f"Syntax error: {analysis.syntax_error}",
        )

    # 2. Risk assessment
    risk_level = getattr(analysis, "risk_level", None)
    if risk_level and risk_level.value in ("high", "critical"):
        reasons = getattr(analysis.risk, "reasons", []) if hasattr(analysis, "risk") else []
        return ScriptValidationResult(
            allowed=False,
            reason=f"{risk_level.value}-risk code: {', '.join(reasons)}",
            risk_level=risk_level.value,
        )

    # 3. Import check
    warnings = []
    features = getattr(analysis, "features", None)
    if features:
        for imp in getattr(features, "imports", []):
            if imp not in AUTOMATION_ALLOWED_IMPORTS_SET:
                return ScriptValidationResult(
                    allowed=False,
                    reason=f"Import '{imp}' not allowed in automation scripts",
                )

        # 4. No dynamic execution
        if getattr(features, "exec_eval_usage", False):
            return ScriptValidationResult(
                allowed=False,
                reason="exec/eval/compile not allowed in automation scripts",
            )

    return ScriptValidationResult(
        allowed=True,
        risk_level=risk_level.value if risk_level else None,
        warnings=warnings,
    )
