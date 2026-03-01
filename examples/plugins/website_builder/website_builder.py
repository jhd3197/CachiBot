"""
Website builder plugin — generate full websites using AgentSite's
multi-agent pipeline (PM, Designer, Developer, Reviewer).

Integrates AgentSite as an embeddable component: no separate server,
no database, no frontend. The pipeline runs in-process and streams
progress events back to the chat via on_tool_output.
"""

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any

from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import ConfigParam, RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext

logger = logging.getLogger(__name__)

# AgentSite's output directory lives under ~/.cachibot/websites/
_WEBSITES_DIR = Path.home() / ".cachibot" / "websites"


class WebsiteBuilderPlugin(CachibotPlugin):
    """Provides website generation tools powered by AgentSite's agent pipeline."""

    _active_generations: dict[str, asyncio.Event] = {}

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("website_builder", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="website_builder",
            display_name="Website Builder",
            icon="globe",
            group="Creative",
            requires=PluginRequirements(network=True, filesystem=True),
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(
            name="build_website",
            description="Generate a complete website from a text description. "
            "Uses a multi-agent pipeline: PM plans the structure, Designer creates "
            "the visual style, Developer builds HTML/CSS/JS, and Reviewer ensures quality. "
            "Returns an inline preview of the generated website.",
            category="creative",
            tags=["website", "html", "css", "web", "builder", "frontend"],
            side_effects=True,
            requires_network=True,
            display_name="Build Website",
            icon="globe",
            risk_level=RiskLevel.MODERATE,
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Description of the website to generate. Be specific about "
                        "purpose, style, sections, and content.",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Name for the website project.",
                        "default": "My Website",
                    },
                    "style": {
                        "type": "string",
                        "description": "Visual style hints (e.g. 'dark theme', 'minimalist', "
                        "'colorful and playful'). Included in the prompt for the Designer agent.",
                        "default": "",
                    },
                    "pages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Page slugs to generate (default: all from site plan). "
                        "Example: ['index', 'about', 'contact']",
                    },
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
            config_params=[
                ConfigParam(
                    name="model",
                    display_name="Model",
                    description="LLM model for the generation pipeline agents.",
                    type="text",
                    default="",
                ),
                ConfigParam(
                    name="maxCost",
                    display_name="Max Cost",
                    description="Maximum cost in USD for the generation (0 = no limit).",
                    type="number",
                    default=0,
                    min=0,
                    max=50,
                    step=0.5,
                    unit="USD",
                ),
                ConfigParam(
                    name="budgetPolicy",
                    display_name="Budget Policy",
                    description="What to do when approaching the cost limit.",
                    type="select",
                    default="",
                    options=["", "hard_stop", "warn_and_continue", "degrade"],
                ),
                ConfigParam(
                    name="maxReviewIterations",
                    display_name="Review Iterations",
                    description="Maximum build+review cycles before accepting.",
                    type="number",
                    default=2,
                    min=1,
                    max=5,
                ),
                ConfigParam(
                    name="reviewThreshold",
                    display_name="Review Threshold",
                    description="Minimum review score (1-10) to approve without another cycle.",
                    type="number",
                    default=7,
                    min=1,
                    max=10,
                ),
            ],
        )
        async def build_website(
            prompt: str,
            project_name: str = "My Website",
            style: str = "",
            pages: list[str] | None = None,
        ) -> str:
            """Generate a complete website from a text description."""
            try:
                from agentsite.engine.component import GenerationConfig, generate_website, regenerate_page
            except ImportError:
                logger.error("AgentSite not installed")
                return (
                    "Error: AgentSite is not installed. "
                    "Install it with: pip install -e path/to/AgentSite"
                )

            # Build the full prompt
            full_prompt = prompt
            if style:
                full_prompt += f"\n\nVisual style: {style}"

            # Resolve config
            tool_cfg = ctx.tool_configs.get("build_website", {})
            model = tool_cfg.get("model", "") or ""
            if not model and ctx.bot_models:
                model = ctx.bot_models.get("default", "")
            if not model:
                model = "openai/gpt-4o"

            max_cost = tool_cfg.get("maxCost", 0) or None
            budget_policy = tool_cfg.get("budgetPolicy", "") or None
            max_review_iters = tool_cfg.get("maxReviewIterations") or None
            review_threshold = tool_cfg.get("reviewThreshold") or None

            # Resolve provider keys from environment
            import os

            provider_keys: dict[str, str] = {}
            for env_key, provider_name in [
                ("OPENAI_API_KEY", "openai"),
                ("ANTHROPIC_API_KEY", "claude"),
                ("GOOGLE_API_KEY", "google"),
                ("DEEPSEEK_API_KEY", "deepseek"),
                ("XAI_API_KEY", "xai"),
            ]:
                val = os.environ.get(env_key, "")
                if val:
                    provider_keys[provider_name] = val

            # Create cancellation token
            cancel_event = asyncio.Event()
            gen_id = f"build-{id(cancel_event)}"
            WebsiteBuilderPlugin._active_generations[gen_id] = cancel_event

            config = GenerationConfig(
                model=model,
                max_cost=max_cost,
                budget_policy=budget_policy,
                provider_keys=provider_keys or None,
                max_review_iterations=int(max_review_iters) if max_review_iters else None,
                review_threshold=int(review_threshold) if review_threshold else None,
                cancel_event=cancel_event,
            )

            # Set up streaming progress via on_tool_output
            _emit = _build_progress_emitter(ctx)

            if _emit:
                await _emit("Starting website generation pipeline...")

            # Build the event bridge
            async def on_event(event: Any) -> None:
                if not _emit:
                    return
                msg = _format_event(event)
                if msg:
                    await _emit(msg)

            # Run the pipeline
            output_dir = _WEBSITES_DIR
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                result = await generate_website(
                    full_prompt,
                    output_dir=output_dir,
                    config=config,
                    on_event=on_event,
                    project_name=project_name,
                    slug="index",
                )

                if not result.success and not result.files:
                    error_msg = result.error or "Unknown error"
                    return f"Error: Website generation failed: {error_msg}"

                # Multi-page support: generate additional pages beyond index
                extra_pages = [p for p in (pages or []) if p != "index"]
                for page_slug in extra_pages:
                    if cancel_event.is_set():
                        break
                    if _emit:
                        await _emit(f"Generating page: {page_slug}...")
                    page_result = await regenerate_page(
                        f"Build the '{page_slug}' page based on the site plan.",
                        output_dir=output_dir,
                        project_id=result.project_id,
                        slug=page_slug,
                        config=config,
                        on_event=on_event,
                    )
                    if _emit and page_result.success:
                        await _emit(f"[done] Page '{page_slug}' generated ({len(page_result.files)} files)")

                # Build the response
                response = _build_response(result, partial=not result.success)
                response += f"\n\n*Generation ID: `{gen_id}`*"
                return response
            finally:
                WebsiteBuilderPlugin._active_generations.pop(gen_id, None)

        @skill(
            name="iterate_website",
            description="Iterate on a previously generated website with feedback or changes. "
            "Creates a new version while preserving the original.",
            category="creative",
            tags=["website", "iterate", "update", "redesign"],
            side_effects=True,
            requires_network=True,
            display_name="Iterate Website",
            icon="arrows-clockwise",
            risk_level=RiskLevel.MODERATE,
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What to change — feedback, new requirements, or a full redesign prompt.",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "The project ID from a previous build_website result.",
                    },
                },
                "required": ["prompt", "project_id"],
                "additionalProperties": False,
            },
        )
        async def iterate_website(prompt: str, project_id: str) -> str:
            """Iterate on an existing website with new instructions."""
            try:
                from agentsite.engine.component import GenerationConfig, load_project, regenerate_page
            except ImportError:
                return (
                    "Error: AgentSite is not installed. "
                    "Install it with: pip install -e path/to/AgentSite"
                )

            # Pre-load conversation context so the response includes history
            prior_state = load_project(_WEBSITES_DIR, project_id)
            if prior_state is None:
                return f"Error: Project `{project_id}` not found in {_WEBSITES_DIR}"

            # Build conversation context from prior messages
            conversation_context = ""
            if prior_state.messages:
                context_lines: list[str] = []
                for msg in prior_state.messages[-6:]:
                    role = "User" if msg.role == "user" else "Agent"
                    context_lines.append(f"{role}: {msg.content[:300]}")
                conversation_context = "\n".join(context_lines)

            # Resolve config (same logic as build_website)
            tool_cfg = ctx.tool_configs.get("build_website", {})
            model = tool_cfg.get("model", "") or ""
            if not model and ctx.bot_models:
                model = ctx.bot_models.get("default", "")
            if not model:
                model = "openai/gpt-4o"

            max_cost = tool_cfg.get("maxCost", 0) or None
            budget_policy = tool_cfg.get("budgetPolicy", "") or None
            max_review_iters = tool_cfg.get("maxReviewIterations") or None
            review_threshold_val = tool_cfg.get("reviewThreshold") or None

            import os

            provider_keys: dict[str, str] = {}
            for env_key, provider_name in [
                ("OPENAI_API_KEY", "openai"),
                ("ANTHROPIC_API_KEY", "claude"),
                ("GOOGLE_API_KEY", "google"),
                ("DEEPSEEK_API_KEY", "deepseek"),
                ("XAI_API_KEY", "xai"),
            ]:
                val = os.environ.get(env_key, "")
                if val:
                    provider_keys[provider_name] = val

            config = GenerationConfig(
                model=model,
                max_cost=max_cost,
                budget_policy=budget_policy,
                provider_keys=provider_keys or None,
                max_review_iterations=int(max_review_iters) if max_review_iters else None,
                review_threshold=int(review_threshold_val) if review_threshold_val else None,
                conversation_context=conversation_context,
            )

            _emit = _build_progress_emitter(ctx)
            if _emit:
                await _emit(f"Iterating on project {project_id}...")

            async def on_event(event: Any) -> None:
                if not _emit:
                    return
                msg = _format_event(event)
                if msg:
                    await _emit(msg)

            output_dir = _WEBSITES_DIR

            result = await regenerate_page(
                prompt,
                output_dir=output_dir,
                project_id=project_id,
                slug="index",
                config=config,
                on_event=on_event,
            )

            if not result.success and not result.files:
                error_msg = result.error or "Unknown error"
                return f"Error: Iteration failed: {error_msg}"

            response = _build_response(result, partial=not result.success)

            # Append conversation summary so the LLM knows what happened before
            if prior_state and prior_state.messages:
                msg_count = len(prior_state.messages)
                response += (
                    f"\n\n*This project now has {msg_count + 2} messages "
                    f"in its conversation history. "
                    f"Use `load_website` with project ID `{project_id}` "
                    f"to review the full history.*"
                )

            return response

        @skill(
            name="list_websites",
            description="List all previously generated website projects. "
            "Shows project name, model used, number of pages, number of conversation "
            "messages, and last activity timestamp. Use this to find a project ID "
            "before calling load_website or iterate_website.",
            category="creative",
            tags=["website", "list", "projects", "history"],
            side_effects=False,
            display_name="List Websites",
            icon="list",
            risk_level=RiskLevel.SAFE,
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        )
        async def list_websites() -> str:
            """List all website projects on disk."""
            try:
                from agentsite.engine.component import load_project
                from agentsite.engine.project_manager import ProjectManager
            except ImportError:
                return (
                    "Error: AgentSite is not installed. "
                    "Install it with: pip install -e path/to/AgentSite"
                )

            output_dir = _WEBSITES_DIR
            if not output_dir.exists():
                return "No website projects found. Use `build_website` to create one."

            pm = ProjectManager(base_dir=output_dir)
            project_ids = pm.list_projects()

            if not project_ids:
                return "No website projects found. Use `build_website` to create one."

            rows: list[str] = []
            for pid in project_ids:
                state = load_project(output_dir, pid)
                if state is None:
                    continue

                page_count = len(state.pages)
                msg_count = len(state.messages)
                last_ts = ""
                if state.messages:
                    last_ts = state.messages[-1].timestamp

                rows.append(
                    f"| `{pid}` | {state.name} | {state.model} "
                    f"| {page_count} | {msg_count} | {last_ts} |"
                )

            if not rows:
                return "No website projects found. Use `build_website` to create one."

            header = (
                "| Project ID | Name | Model | Pages | Messages | Last Activity |\n"
                "| --- | --- | --- | --- | --- | --- |"
            )
            return f"{header}\n" + "\n".join(rows)

        @skill(
            name="load_website",
            description="Load a previously generated website project's full state — "
            "conversation history, page files, design tokens, and site plan. "
            "Use this to restore context before iterating on an existing project, "
            "or to review what was built in a past session.",
            category="creative",
            tags=["website", "load", "restore", "resume", "history"],
            side_effects=False,
            display_name="Load Website",
            icon="folder-open",
            risk_level=RiskLevel.SAFE,
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "The project ID to load (from list_websites or a previous build_website result).",
                    },
                },
                "required": ["project_id"],
                "additionalProperties": False,
            },
        )
        async def load_website(project_id: str) -> str:
            """Load full project state from disk."""
            try:
                from agentsite.engine.component import load_project
            except ImportError:
                return (
                    "Error: AgentSite is not installed. "
                    "Install it with: pip install -e path/to/AgentSite"
                )

            state = load_project(_WEBSITES_DIR, project_id)
            if state is None:
                return f"Error: Project `{project_id}` not found."

            return _format_project_state(state)

        @skill(
            name="cancel_website",
            description="Cancel a running website generation. "
            "Use the generation ID from a build_website or iterate_website result.",
            category="creative",
            tags=["website", "cancel", "stop"],
            side_effects=True,
            display_name="Cancel Website Generation",
            icon="x-circle",
            risk_level=RiskLevel.SAFE,
            input_schema={
                "type": "object",
                "properties": {
                    "generation_id": {
                        "type": "string",
                        "description": "The generation ID from a running build_website or iterate_website.",
                    },
                },
                "required": ["generation_id"],
                "additionalProperties": False,
            },
        )
        async def cancel_website(generation_id: str) -> str:
            """Cancel a running website generation."""
            cancel_event = WebsiteBuilderPlugin._active_generations.get(generation_id)
            if cancel_event is None:
                return (
                    f"No active generation found with ID `{generation_id}`. "
                    "It may have already completed."
                )
            cancel_event.set()
            return f"Cancellation requested for generation `{generation_id}`. The pipeline will stop after the current phase completes."

        @skill(
            name="delete_website",
            description="Permanently delete a website project and all its files from disk.",
            category="creative",
            tags=["website", "delete", "remove", "cleanup"],
            side_effects=True,
            display_name="Delete Website",
            icon="trash",
            risk_level=RiskLevel.MODERATE,
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "The project ID to delete (from list_websites or a previous build_website result).",
                    },
                },
                "required": ["project_id"],
                "additionalProperties": False,
            },
        )
        async def delete_website(project_id: str) -> str:
            """Delete a website project from disk."""
            try:
                from agentsite.engine.component import delete_project
            except ImportError:
                return (
                    "Error: AgentSite is not installed. "
                    "Install it with: pip install -e path/to/AgentSite"
                )

            existed = delete_project(_WEBSITES_DIR, project_id)
            if existed:
                return f"Project `{project_id}` has been deleted."
            return f"Project `{project_id}` not found."

        return {
            "build_website": build_website.__skill__,
            "iterate_website": iterate_website.__skill__,
            "list_websites": list_websites.__skill__,
            "load_website": load_website.__skill__,
            "cancel_website": cancel_website.__skill__,
            "delete_website": delete_website.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Agent event messages — only emit the meaningful ones to avoid noise
_AGENT_LABELS: dict[str, str] = {
    "pm": "PM Agent (planning site structure)",
    "designer": "Designer Agent (creating visual style)",
    "developer": "Developer Agent (building HTML/CSS/JS)",
    "reviewer": "Reviewer Agent (quality review)",
    "markup": "Markup Agent (writing HTML)",
    "style": "Style Agent (writing CSS)",
    "script": "Script Agent (writing JavaScript)",
    "image": "Image Agent (generating images)",
    "copywriter": "Copywriter Agent (refining text)",
    "seo": "SEO Agent (optimizing for search)",
    "accessibility": "Accessibility Agent (WCAG compliance)",
    "animation": "Animation Agent (adding transitions)",
}


def _build_progress_emitter(ctx: PluginContext):
    """Build an async emitter that streams progress to the chat.

    Returns None if on_tool_output is not available.
    """
    if not ctx.on_tool_output:
        return None

    from prompture.integrations.tukuy_bridge import current_tool_call_id

    tool_id = current_tool_call_id.get()
    if not tool_id:
        return None

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None

    on_output = ctx.on_tool_output

    async def _emit(text: str) -> None:
        await on_output(tool_id, text)

    return _emit


def _format_event(event: Any) -> str | None:
    """Convert an AgentSite WSEvent into a human-readable progress line."""
    event_type = event.type
    agent = event.agent
    data = event.data

    if event_type == "agent_start":
        label = _AGENT_LABELS.get(agent, agent)
        return f"[start] {label}..."

    if event_type == "agent_complete":
        duration = data.get("duration_s")
        cost = data.get("cost", 0)
        suffix = ""
        if duration:
            suffix += f" ({duration}s"
            if cost:
                suffix += f", ${cost:.4f}"
            suffix += ")"
        label = _AGENT_LABELS.get(agent, agent)
        return f"[done] {label}{suffix}"

    if event_type == "file_written":
        path = data.get("path", "?")
        return f"[file] {path}"

    if event_type == "agent_error":
        msg = data.get("message", "unknown error")
        return f"[error] {agent}: {msg}"

    if event_type == "round_start":
        rd = data.get("round", "?")
        return f"[round] Build+Review cycle {rd}"

    if event_type == "pipeline_plan":
        agents = data.get("required_agents", [])
        names = [_AGENT_LABELS.get(a, a).split("(")[0].strip() for a in agents]
        return f"[plan] Pipeline: {' -> '.join(names)}"

    if event_type == "budget_exceeded":
        return f"[budget] {data.get('message', 'Budget exceeded')}"

    if event_type == "model_fallback":
        old = data.get("old_model", "?")
        new = data.get("new_model", "?")
        return f"[fallback] {old} -> {new}"

    if event_type == "site_plan_ready":
        sp = data.get("site_plan", {})
        page_names = [p.get("slug", p.get("title", "?")) for p in sp.get("pages", [])]
        agents = data.get("required_agents", [])
        agent_names = [_AGENT_LABELS.get(a, a).split("(")[0].strip() for a in agents]
        return (
            f"[plan] Site structure: {len(page_names)} pages "
            f"({', '.join(page_names)}), "
            f"agents: {' -> '.join(agent_names)}"
        )

    if event_type == "style_spec_ready":
        parsed = data.get("parsed", False)
        spec_text = data.get("style_spec", "")
        # Try to extract a few highlights
        bits: list[str] = []
        if parsed:
            try:
                import json as _json
                from prompture import clean_json_text
                spec_data = _json.loads(clean_json_text(spec_text))
                if spec_data.get("primary_color"):
                    bits.append(f"primary: {spec_data['primary_color']}")
                if spec_data.get("font_family"):
                    bits.append(f"font: {spec_data['font_family']}")
            except Exception:
                pass
        detail = f" ({', '.join(bits)})" if bits else ""
        return f"[design] Style spec created{detail}"

    if event_type == "review_feedback":
        score = data.get("score", "?")
        approved = data.get("approved", False)
        issues = data.get("issues", [])
        status = "Approved" if approved else "Needs revision"
        issue_note = f" Issues: {'; '.join(issues[:3])}" if issues else " Issues: none"
        return f"[review] Score: {score}/10 — {status}.{issue_note}"

    # Skip noisy events (text_delta, agent_step, tool_start/end, etc.)
    return None


def _build_response(result: Any, *, partial: bool = False) -> str:
    """Build the Markdown response from a GenerationResult."""
    parts: list[str] = []

    if partial:
        parts.append("Website partially generated (some agents encountered issues).")
    else:
        parts.append("Website generated successfully!")

    # Metadata
    meta: list[str] = []
    meta.append(f"Project: `{result.project_id}`")
    meta.append(f"Files: {', '.join(result.files)}")
    if result.usage:
        cost = result.usage.get("cost", 0) or result.usage.get("total_cost", 0) or 0
        if cost:
            meta.append(f"Cost: ${cost:.4f}")
    parts.append(f"*{' | '.join(meta)}*")

    if result.error:
        parts.append(f"\nNote: {result.error}")

    # Inline HTML preview as data URI
    html_content = result.files_content.get("index.html", "")
    if html_content:
        # Inline CSS/JS into the HTML if they're separate files
        html_content = _inline_assets(html_content, result.files_content)
        encoded = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
        parts.append("")
        parts.append(f"![Website Preview](data:text/html;base64,{encoded})")

    return "\n".join(parts)


def _format_project_state(state: Any) -> str:
    """Format a ProjectState into a rich Markdown summary for the LLM."""
    parts: list[str] = []

    parts.append(f"## {state.name}")
    parts.append(f"**Project ID:** `{state.project_id}`  ")
    parts.append(f"**Model:** {state.model}")

    # Style spec summary
    if state.style_spec:
        ss = state.style_spec
        style_bits: list[str] = []
        if hasattr(ss, "primary_color") and ss.primary_color:
            style_bits.append(f"Primary: {ss.primary_color}")
        if hasattr(ss, "font_family") and ss.font_family:
            style_bits.append(f"Font: {ss.font_family}")
        if hasattr(ss, "background_color") and ss.background_color:
            style_bits.append(f"Background: {ss.background_color}")
        if style_bits:
            parts.append(f"**Style:** {', '.join(style_bits)}")

    # Pages
    if state.pages:
        parts.append("")
        parts.append("### Pages")
        for page in state.pages:
            parts.append(
                f"- **{page.slug}** (v{page.latest_version}) — "
                f"{len(page.files)} files: {', '.join(page.files)}"
            )

    # Conversation history
    if state.messages:
        parts.append("")
        parts.append("### Conversation History")
        for msg in state.messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            # Truncate long messages for readability
            content = msg.content
            if len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"**{role_label}** ({msg.timestamp}):")
            parts.append(f"> {content}")
            parts.append("")

    # Inline preview of latest index page
    if state.pages:
        index_page = next((p for p in state.pages if p.slug == "index"), state.pages[0])
        html_content = index_page.files_content.get("index.html", "")
        if html_content:
            html_content = _inline_assets(html_content, index_page.files_content)
            encoded = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
            parts.append(f"![Website Preview](data:text/html;base64,{encoded})")

    return "\n".join(parts)


def _inline_assets(html: str, files: dict[str, str]) -> str:
    """Inline linked CSS and JS files into the HTML for self-contained preview.

    Replaces <link href="styles.css"> with <style>...</style> and
    <script src="script.js"> with <script>...</script>.
    """
    import re

    # Inline CSS: <link rel="stylesheet" href="styles.css">
    def _replace_css(match: re.Match) -> str:
        href = match.group("href")
        css = files.get(href)
        if css:
            return f"<style>\n{css}\n</style>"
        return match.group(0)

    html = re.sub(
        r'<link\s+[^>]*href="(?P<href>[^"]+\.css)"[^>]*/?>',
        _replace_css,
        html,
        flags=re.IGNORECASE,
    )

    # Inline JS: <script src="script.js"></script>
    def _replace_js(match: re.Match) -> str:
        src = match.group("src")
        js = files.get(src)
        if js:
            return f"<script>\n{js}\n</script>"
        return match.group(0)

    html = re.sub(
        r'<script\s+[^>]*src="(?P<src>[^"]+\.js)"[^>]*>\s*</script>',
        _replace_js,
        html,
        flags=re.IGNORECASE,
    )

    return html
