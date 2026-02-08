"""
Python sandbox plugin — sandboxed python_execute tool with risk analysis.
"""

from prompture import ApprovalRequired, analyze_python
from prompture import RiskLevel as PromptureRiskLevel
from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import ConfigParam, RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class PythonSandboxPlugin(CachibotPlugin):
    """Provides the python_execute tool with AST risk analysis."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("python_sandbox", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="python_sandbox",
            display_name="Code Execution",
            icon="code",
            group="Core",
            requires=PluginRequirements(filesystem=True),
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(
            name="python_execute",
            description="Execute Python code safely in a sandbox. "
            "Use this to run Python scripts, calculations, data processing, "
            "or any Python code. The code runs in an isolated environment "
            "with restricted imports and filesystem access.",
            category="code",
            tags=["python", "execute", "sandbox"],
            side_effects=True,
            requires_filesystem=True,
            display_name="Execute Python",
            icon="code",
            risk_level=RiskLevel.DANGEROUS,
            config_params=[
                ConfigParam(
                    name="timeoutSeconds",
                    display_name="Timeout",
                    type="number",
                    default=30,
                    min=5,
                    max=120,
                    step=5,
                    unit="seconds",
                ),
                ConfigParam(
                    name="maxOutputLength",
                    display_name="Max Output Length",
                    type="number",
                    default=10000,
                    min=1000,
                    max=50000,
                    step=1000,
                    unit="chars",
                ),
            ],
        )
        def python_execute(code: str) -> str:
            """Execute Python code safely in a sandbox.

            Args:
                code: Python code to execute

            Returns:
                Output from the code execution (stdout + return value)
            """
            # Analyze code first
            analysis = analyze_python(code)

            if analysis.risk_level in (PromptureRiskLevel.HIGH, PromptureRiskLevel.CRITICAL):
                raise ApprovalRequired(
                    tool_name="python_execute",
                    action=f"Execute {analysis.risk_level.value}-risk Python code",
                    details={
                        "code": code,
                        "risk_level": analysis.risk_level.value,
                        "reasons": analysis.risk.reasons,
                        "imports": list(analysis.features.imports),
                    },
                )

            result = ctx.sandbox.execute(code)

            # Get max output length from tool_configs or use default
            max_output_length = 10000
            if "python_execute" in ctx.tool_configs:
                py_cfg = ctx.tool_configs["python_execute"]
                max_output_length = py_cfg.get("maxOutputLength", max_output_length)

            if result.success:
                output = result.output.strip() if result.output else ""
                if result.return_value is not None:
                    if output:
                        output += f"\n\nReturn value: {result.return_value}"
                    else:
                        output = f"Return value: {result.return_value}"
                if len(output) > max_output_length:
                    output = output[:max_output_length]
                    output += f"\n\n... (output truncated at {max_output_length} chars)"
                return output or "Code executed successfully (no output)"
            else:
                return f"Error: {result.error}"

        return {"python_execute": python_execute.__skill__}

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map
