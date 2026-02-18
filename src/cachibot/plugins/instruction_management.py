"""
Instruction Management plugin — CRUD skills for custom instructions.

Gives bots the ability to create, edit, list, read, and test
their own LLM-powered instructions at runtime.
"""

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class InstructionManagementPlugin(CachibotPlugin):
    """Provides tools for bots to manage their custom instructions."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("instruction_management", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="instruction_management",
            display_name="Instruction Management",
            description="Create, edit, and manage custom LLM-powered instructions.",
            icon="wand",
            group="Instructions",
        )

    def _get_bot_id(self) -> str | None:
        return self.ctx.bot_id

    def _build_skills(self) -> dict[str, Skill]:
        get_bot_id = self._get_bot_id

        @skill(
            name="instruction_create",
            description=(
                "Create a new custom instruction (LLM-powered tool). "
                "Define a prompt template with {variable} placeholders, "
                "output format, and optional model hints."
            ),
            category="instructions",
            tags=["instructions", "create", "llm"],
            is_async=True,
            side_effects=True,
            display_name="Create Instruction",
            icon="plus-circle",
            risk_level=RiskLevel.MODERATE,
        )
        async def instruction_create(
            name: str,
            prompt: str,
            description: str = "",
            output_format: str = "text",
            system_prompt: str = "",
            model_hint: str = "",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            input_variables: list[str] | None = None,
            few_shot_examples: list[dict] | None = None,
            category: str = "custom",
            tags: list[str] | None = None,
        ) -> str:
            """Create a new custom instruction.

            Args:
                name: Unique name for the instruction (e.g. "summarize_email")
                prompt: Prompt template with {variable} placeholders
                description: Human-readable description
                output_format: One of: text, json, list, markdown
                system_prompt: Optional system prompt for the LLM
                model_hint: Optional model to use (e.g. "openai/gpt-4o")
                temperature: LLM temperature (0.0-2.0)
                max_tokens: Maximum tokens in the response
                input_variables: List of variable names in the prompt template
                few_shot_examples: List of {input, output} examples
                category: Category for organization
                tags: Tags for filtering

            Returns:
                JSON with the created instruction details
            """
            import json
            import re

            from cachibot.storage.instruction_repository import InstructionRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                # Auto-extract input variables from template if not provided
                if not input_variables:
                    input_variables = list(dict.fromkeys(re.findall(r"\{(\w+)\}", prompt)))

                repo = InstructionRepository()

                # Check for duplicate name
                existing = await repo.get_by_name(bot_id, name)
                if existing:
                    return f"Error: An instruction named '{name}' already exists"

                data = {
                    "name": name,
                    "prompt": prompt,
                    "description": description or None,
                    "output_format": output_format,
                    "system_prompt": system_prompt or None,
                    "model_hint": model_hint or None,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "input_variables": input_variables,
                    "few_shot_examples": few_shot_examples,
                    "category": category,
                    "tags": tags or [],
                }

                record = await repo.create(data, bot_id, author=f"bot:{bot_id}")

                return json.dumps(
                    {
                        "id": record.id,
                        "name": record.name,
                        "description": record.description,
                        "input_variables": record.input_variables,
                        "output_format": record.output_format,
                        "version": record.version,
                        "message": f"Instruction '{name}' created successfully",
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error creating instruction: {e}"

        @skill(
            name="instruction_edit",
            description=(
                "Edit an existing custom instruction. "
                "Changes create a new version for rollback support."
            ),
            category="instructions",
            tags=["instructions", "edit", "update"],
            is_async=True,
            side_effects=True,
            display_name="Edit Instruction",
            icon="edit",
            risk_level=RiskLevel.MODERATE,
        )
        async def instruction_edit(
            instruction_id_or_name: str,
            new_prompt: str = "",
            new_description: str = "",
            new_system_prompt: str = "",
            new_output_format: str = "",
            new_model_hint: str = "",
            new_temperature: float | None = None,
            new_max_tokens: int | None = None,
            commit_message: str = "",
        ) -> str:
            """Edit an existing instruction.

            Args:
                instruction_id_or_name: The instruction ID or name to edit
                new_prompt: Updated prompt template (empty = no change)
                new_description: Updated description (empty = no change)
                new_system_prompt: Updated system prompt (empty = no change)
                new_output_format: Updated output format (empty = no change)
                new_model_hint: Updated model hint (empty = no change)
                new_temperature: Updated temperature (None = no change)
                new_max_tokens: Updated max tokens (None = no change)
                commit_message: Description of the changes

            Returns:
                JSON with the updated instruction details
            """
            import json

            from cachibot.storage.instruction_repository import InstructionRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                repo = InstructionRepository()

                # Resolve by name or ID
                record = await repo.get(instruction_id_or_name)
                if not record or record.bot_id != bot_id:
                    record = await repo.get_by_name(bot_id, instruction_id_or_name)
                if not record:
                    return f"Error: Instruction '{instruction_id_or_name}' not found"

                changes = {}
                if new_prompt:
                    changes["prompt"] = new_prompt
                if new_description:
                    changes["description"] = new_description
                if new_system_prompt:
                    changes["system_prompt"] = new_system_prompt
                if new_output_format:
                    changes["output_format"] = new_output_format
                if new_model_hint:
                    changes["model_hint"] = new_model_hint
                if new_temperature is not None:
                    changes["temperature"] = new_temperature
                if new_max_tokens is not None:
                    changes["max_tokens"] = new_max_tokens

                if not changes:
                    return "No changes specified"

                updated = await repo.update(
                    record.id,
                    changes,
                    author=f"bot:{bot_id}",
                    commit_message=commit_message or None,
                )

                if not updated:
                    return "Error: Failed to update instruction"

                return json.dumps(
                    {
                        "id": updated.id,
                        "name": updated.name,
                        "version": updated.version,
                        "message": f"Instruction '{updated.name}' updated to v{updated.version}",
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error editing instruction: {e}"

        @skill(
            name="instruction_read",
            description="Read the full details of a custom instruction including its template.",
            category="instructions",
            tags=["instructions", "read", "details"],
            is_async=True,
            idempotent=True,
            display_name="Read Instruction",
            icon="eye",
            risk_level=RiskLevel.SAFE,
        )
        async def instruction_read(instruction_id_or_name: str) -> str:
            """Read the full details of an instruction.

            Args:
                instruction_id_or_name: The instruction ID or name

            Returns:
                JSON with full instruction details
            """
            import json

            from cachibot.storage.instruction_repository import InstructionRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                repo = InstructionRepository()

                record = await repo.get(instruction_id_or_name)
                if not record or record.bot_id != bot_id:
                    record = await repo.get_by_name(bot_id, instruction_id_or_name)
                if not record:
                    return f"Error: Instruction '{instruction_id_or_name}' not found"

                return json.dumps(
                    {
                        "id": record.id,
                        "name": record.name,
                        "description": record.description,
                        "prompt": record.prompt,
                        "system_prompt": record.system_prompt,
                        "output_format": record.output_format,
                        "model_hint": record.model_hint,
                        "temperature": record.temperature,
                        "max_tokens": record.max_tokens,
                        "input_variables": record.input_variables,
                        "few_shot_examples": record.few_shot_examples,
                        "version": record.version,
                        "is_active": record.is_active,
                        "category": record.category,
                        "tags": record.tags,
                        "created_at": record.created_at.isoformat(),
                        "updated_at": record.updated_at.isoformat(),
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error reading instruction: {e}"

        @skill(
            name="instruction_list",
            description="List all instructions available to this bot (both built-in and custom).",
            category="instructions",
            tags=["instructions", "list"],
            is_async=True,
            idempotent=True,
            display_name="List Instructions",
            icon="list",
            risk_level=RiskLevel.SAFE,
        )
        async def instruction_list() -> str:
            """List all instructions for this bot.

            Returns:
                JSON list of instructions with name, description, type, and status
            """
            import json

            from cachibot.storage.instruction_repository import InstructionRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                repo = InstructionRepository()
                records = await repo.get_by_bot(bot_id)

                result = []
                for r in records:
                    result.append(
                        {
                            "id": r.id,
                            "name": r.name,
                            "description": r.description,
                            "output_format": r.output_format,
                            "version": r.version,
                            "is_active": r.is_active,
                            "category": r.category,
                            "type": "custom",
                        }
                    )

                if not result:
                    return "No custom instructions found. Use instruction_create to make one."

                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing instructions: {e}"

        @skill(
            name="instruction_test",
            description=(
                "Test a custom instruction with sample input. "
                "Executes the instruction and returns the LLM output."
            ),
            category="instructions",
            tags=["instructions", "test", "dry-run"],
            is_async=True,
            requires_network=True,
            display_name="Test Instruction",
            icon="play",
            risk_level=RiskLevel.MODERATE,
        )
        async def instruction_test(
            instruction_id_or_name: str,
            sample_input: str = "",
        ) -> str:
            """Test an instruction with sample input.

            Args:
                instruction_id_or_name: The instruction ID or name to test
                sample_input: JSON string mapping variable names to values,
                    e.g. '{"text": "Hello world"}'

            Returns:
                The instruction output or error message
            """
            import json

            from tukuy import SkillContext
            from tukuy.instruction import Instruction, InstructionDescriptor

            from cachibot.storage.instruction_repository import InstructionRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                repo = InstructionRepository()

                record = await repo.get(instruction_id_or_name)
                if not record or record.bot_id != bot_id:
                    record = await repo.get_by_name(bot_id, instruction_id_or_name)
                if not record:
                    return f"Error: Instruction '{instruction_id_or_name}' not found"

                # Parse sample input
                try:
                    if sample_input:
                        variables = json.loads(sample_input)
                    else:
                        variables = {}
                except json.JSONDecodeError:
                    # Try treating the whole thing as the value for the first variable
                    if record.input_variables:
                        variables = {record.input_variables[0]: sample_input}
                    else:
                        variables = {}

                # Build the instruction
                descriptor = InstructionDescriptor(
                    name=record.name,
                    description=record.description or "",
                    prompt=record.prompt,
                    system_prompt=record.system_prompt,
                    output_format=record.output_format,
                    model_hint=record.model_hint,
                    temperature=record.temperature,
                    max_tokens=record.max_tokens,
                    few_shot_examples=record.few_shot_examples,
                )
                instr = Instruction(descriptor=descriptor, fn=None)

                # Build context with llm_backend
                try:
                    from prompture.bridges import create_tukuy_backend

                    from cachibot.config import Config

                    config = Config.load()
                    model = record.model_hint or config.agent.model or "openai/gpt-4o"
                    backend = create_tukuy_backend(model)
                    ctx = SkillContext(config={"llm_backend": backend})
                except Exception as e:
                    return f"Error: Could not create LLM backend for testing: {e}"

                # Execute
                result = await instr.ainvoke(context=ctx, **variables)

                if result.success:
                    output = result.value
                    meta = result.metadata or {}
                    return json.dumps(
                        {
                            "success": True,
                            "output": output,
                            "meta": {
                                "model": meta.get("model", "unknown"),
                                "prompt_tokens": meta.get("prompt_tokens", 0),
                                "completion_tokens": meta.get("completion_tokens", 0),
                            },
                        },
                        indent=2,
                        default=str,
                    )
                else:
                    return json.dumps(
                        {"success": False, "error": result.error},
                        indent=2,
                    )

            except Exception as e:
                return f"Error testing instruction: {e}"

        return {
            "instruction_create": instruction_create.__skill__,
            "instruction_edit": instruction_edit.__skill__,
            "instruction_read": instruction_read.__skill__,
            "instruction_list": instruction_list.__skill__,
            "instruction_test": instruction_test.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map
