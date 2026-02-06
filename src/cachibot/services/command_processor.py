"""
Command Processor Service

Handles BotFather-like slash commands for both web and platform interfaces.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from cachibot.models.bot import Bot
from cachibot.models.command import (
    BOT_TEMPLATES,
    COMMANDS,
    CommandDef,
    CommandResult,
    FlowState,
    FlowStepType,
)
from cachibot.storage.repository import BotRepository

logger = logging.getLogger(__name__)

# Flow timeout in minutes
FLOW_TIMEOUT_MINUTES = 5


class CommandProcessor:
    """
    Processes slash commands and manages multi-step flows.

    Handles command parsing, flow state management, and built-in command execution.
    """

    def __init__(self) -> None:
        self._commands: dict[str, CommandDef] = COMMANDS.copy()
        self._flows: dict[str, FlowState] = {}  # key: f"{user_id}:{chat_id}"
        self._bot_repo = BotRepository()

    @staticmethod
    def _flow_key(user_id: str, chat_id: str) -> str:
        """Generate a unique key for flow state storage."""
        return f"{user_id}:{chat_id}"

    def is_command(self, text: str) -> bool:
        """Check if the text is a command."""
        return text.strip().startswith("/")

    def has_active_flow(self, user_id: str, chat_id: str) -> bool:
        """Check if there's an active flow for this user/chat."""
        key = self._flow_key(user_id, chat_id)
        flow = self._flows.get(key)
        if flow is None:
            return False
        if flow.is_expired():
            del self._flows[key]
            return False
        return True

    def _parse_command(self, text: str) -> tuple[str, list[str]]:
        """Parse a command string into command name and arguments."""
        text = text.strip()
        if not text.startswith("/"):
            return "", []

        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1].split() if len(parts) > 1 else []
        return cmd, args

    def _start_flow(
        self, user_id: str, chat_id: str, command: str
    ) -> FlowState:
        """Start a new command flow."""
        key = self._flow_key(user_id, chat_id)
        flow = FlowState(
            user_id=user_id,
            chat_id=chat_id,
            command=command,
            current_step=0,
            collected_data={},
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=FLOW_TIMEOUT_MINUTES),
        )
        self._flows[key] = flow
        return flow

    def _cancel_flow(self, user_id: str, chat_id: str) -> None:
        """Cancel an active flow."""
        key = self._flow_key(user_id, chat_id)
        if key in self._flows:
            del self._flows[key]

    def _get_flow(self, user_id: str, chat_id: str) -> FlowState | None:
        """Get the active flow for a user/chat."""
        key = self._flow_key(user_id, chat_id)
        flow = self._flows.get(key)
        if flow and flow.is_expired():
            del self._flows[key]
            return None
        return flow

    async def process(
        self,
        text: str,
        platform: str,
        user_id: str,
        chat_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> CommandResult:
        """
        Process a command or continue an active flow.

        Args:
            text: The user's input text
            platform: "web" or platform name (telegram, discord)
            user_id: The user's ID
            chat_id: The chat/conversation ID
            metadata: Additional context (username, etc.)

        Returns:
            CommandResult with response and optional action
        """
        metadata = metadata or {}

        # Check for active flow first
        flow = self._get_flow(user_id, chat_id)

        # Handle cancel command - works anywhere
        if self.is_command(text):
            cmd, _ = self._parse_command(text)
            if cmd == "cancel":
                if flow:
                    self._cancel_flow(user_id, chat_id)
                    return CommandResult(
                        response="Operation cancelled. What would you like to do?",
                        is_flow_active=False,
                    )
                return CommandResult(
                    response="Nothing to cancel. Type /help to see available commands.",
                )

        # If there's an active flow, continue it
        if flow and not self.is_command(text):
            return await self._continue_flow(flow, text, platform, metadata)

        # Parse new command
        if not self.is_command(text):
            return CommandResult(
                response="I only respond to commands. Type /help to see what I can do.",
            )

        cmd, args = self._parse_command(text)

        # Check if command exists
        if cmd not in self._commands:
            return CommandResult(
                response=f"Unknown command: /{cmd}\nType /help to see available commands.",
            )

        command_def = self._commands[cmd]

        # Check platform restrictions
        is_web = platform == "web"
        if command_def.platform_only and is_web:
            return CommandResult(
                response=f"The /{cmd} command is only available on Telegram/Discord.",
            )
        if command_def.web_only and not is_web:
            return CommandResult(
                response=f"For /{cmd}, please use the web interface at your CachiBot URL.",
                action="redirect_web" if not is_web else None,
            )

        # Execute command
        return await self._execute_command(cmd, args, platform, user_id, chat_id, metadata)

    async def _execute_command(
        self,
        cmd: str,
        args: list[str],
        platform: str,
        user_id: str,
        chat_id: str,
        metadata: dict[str, Any],
    ) -> CommandResult:
        """Execute a specific command."""
        is_web = platform == "web"

        if cmd == "start":
            return self._handle_start(metadata)

        elif cmd == "help":
            return self._handle_help(is_web)

        elif cmd == "list":
            return await self._handle_list()

        elif cmd == "new":
            return self._handle_new(user_id, chat_id, is_web)

        elif cmd == "settings":
            return self._handle_settings(is_web)

        return CommandResult(
            response=f"Command /{cmd} is not implemented yet.",
        )

    def _handle_start(self, metadata: dict[str, Any]) -> CommandResult:
        """Handle the /start command."""
        username = metadata.get("first_name") or metadata.get("username") or "there"
        return CommandResult(
            response=(
                f"Hello {username}! I'm CachiBot, your AI assistant.\n\n"
                "Here's what you can do:\n"
                "/new - Create a new bot\n"
                "/list - See your bots\n"
                "/help - Show all commands\n\n"
                "Send me a message and I'll respond using your active bot!"
            ),
        )

    def _handle_help(self, is_web: bool) -> CommandResult:
        """Handle the /help command."""
        lines = ["Available commands:\n"]
        for name, cmd in self._commands.items():
            # Skip platform-only commands on web and vice versa
            if cmd.platform_only and is_web:
                continue
            if cmd.web_only and not is_web:
                continue
            if name == "cancel":
                continue  # Don't show cancel in help
            lines.append(f"/{name} - {cmd.description}")

        lines.append("\nType /cancel anytime to stop the current operation.")

        return CommandResult(
            response="\n".join(lines),
            action="show_help" if is_web else None,
        )

    async def _handle_list(self) -> CommandResult:
        """Handle the /list command."""
        try:
            bots = await self._bot_repo.get_all_bots()

            if not bots:
                return CommandResult(
                    response=(
                        "You don't have any bots yet!\n"
                        "Use /new to create your first bot."
                    ),
                )

            lines = ["Your bots:\n"]
            for i, bot in enumerate(bots, 1):
                desc = f" - {bot.description}" if bot.description else ""
                lines.append(f"{i}. {bot.name}{desc}")

            return CommandResult(
                response="\n".join(lines),
                data={"bots": [{"id": b.id, "name": b.name} for b in bots]},
            )

        except Exception as e:
            logger.error(f"Error listing bots: {e}")
            return CommandResult(
                response="Sorry, I couldn't retrieve your bots. Please try again.",
            )

    def _handle_new(self, user_id: str, chat_id: str, is_web: bool) -> CommandResult:
        """Handle the /new command."""
        if is_web:
            # On web, trigger the dialog
            return CommandResult(
                response="Opening bot creation...",
                action="open_dialog:create_bot",
            )

        # On platforms, start the conversational flow
        command_def = self._commands["new"]
        if not command_def.flow_steps:
            return CommandResult(response="Bot creation is not configured.")

        flow = self._start_flow(user_id, chat_id, "new")
        first_step = command_def.flow_steps[0]

        return CommandResult(
            response=first_step.prompt,
            is_flow_active=True,
        )

    def _handle_settings(self, is_web: bool) -> CommandResult:
        """Handle the /settings command."""
        if is_web:
            return CommandResult(
                response="Opening settings...",
                action="open_dialog:settings",
            )

        return CommandResult(
            response="Settings are available in the web interface. Visit your CachiBot URL to configure settings.",
        )

    async def _continue_flow(
        self,
        flow: FlowState,
        user_input: str,
        platform: str,
        metadata: dict[str, Any],
    ) -> CommandResult:
        """Continue an active command flow with user input."""
        command_def = self._commands.get(flow.command)
        if not command_def or not command_def.flow_steps:
            self._cancel_flow(flow.user_id, flow.chat_id)
            return CommandResult(
                response="Flow configuration error. Please try again with /new.",
            )

        # Get current step
        if flow.current_step >= len(command_def.flow_steps):
            self._cancel_flow(flow.user_id, flow.chat_id)
            return CommandResult(response="Flow completed.")

        current_step = command_def.flow_steps[flow.current_step]
        user_input = user_input.strip()

        # Handle skip for optional fields
        if current_step.optional and user_input.lower() == current_step.skip_keyword:
            flow.collected_data[current_step.field] = None
        elif current_step.type == FlowStepType.choice:
            # Parse choice input
            try:
                choice_num = int(user_input)
                if current_step.choices and 1 <= choice_num <= len(current_step.choices):
                    flow.collected_data[current_step.field] = current_step.choices[choice_num - 1]
                else:
                    return CommandResult(
                        response=f"Please enter a number between 1 and {len(current_step.choices or [])}.",
                        is_flow_active=True,
                    )
            except ValueError:
                # Try to match by name
                if current_step.choices:
                    matched = None
                    for choice in current_step.choices:
                        if user_input.lower() in choice.lower():
                            matched = choice
                            break
                    if matched:
                        flow.collected_data[current_step.field] = matched
                    else:
                        return CommandResult(
                            response=f"Please enter a number (1-{len(current_step.choices)}) or a valid option name.",
                            is_flow_active=True,
                        )
        else:
            # Text input
            if not user_input and not current_step.optional:
                return CommandResult(
                    response="Please provide a value or type /cancel to abort.",
                    is_flow_active=True,
                )
            flow.collected_data[current_step.field] = user_input

        # Move to next step
        flow.current_step += 1

        # Check if flow is complete
        if flow.current_step >= len(command_def.flow_steps):
            return await self._complete_flow(flow, platform, metadata)

        # Get next step prompt
        next_step = command_def.flow_steps[flow.current_step]
        # Format prompt with collected data
        prompt = next_step.prompt.format(**flow.collected_data)

        return CommandResult(
            response=prompt,
            is_flow_active=True,
        )

    async def _complete_flow(
        self,
        flow: FlowState,
        platform: str,
        metadata: dict[str, Any],
    ) -> CommandResult:
        """Complete a command flow and execute the final action."""
        # Clean up flow
        self._cancel_flow(flow.user_id, flow.chat_id)

        if flow.command == "new":
            return await self._create_bot_from_flow(flow, metadata)

        return CommandResult(
            response="Flow completed!",
        )

    async def _create_bot_from_flow(
        self,
        flow: FlowState,
        metadata: dict[str, Any],
    ) -> CommandResult:
        """Create a bot from the collected flow data."""
        data = flow.collected_data
        name = data.get("name", "New Bot")
        description = data.get("description")
        template_name = data.get("template", "General Assistant")

        # Get template
        template = BOT_TEMPLATES.get(template_name, BOT_TEMPLATES["General Assistant"])

        # Use template description if user skipped
        if not description:
            description = template["description"]

        try:
            # Create the bot
            now = datetime.utcnow()
            bot = Bot(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                icon="bot",
                color="#22c55e",
                model="moonshot/kimi-k2.5",
                systemPrompt=template["system_prompt"],
                capabilities={},
                createdAt=now,
                updatedAt=now,
            )

            await self._bot_repo.upsert_bot(bot)

            return CommandResult(
                response=(
                    f"Created '{name}'!\n\n"
                    f"Template: {template_name}\n"
                    f"Description: {description}\n\n"
                    f"Your bot is ready! Send a message to start chatting."
                ),
                data={"bot_id": bot.id, "bot_name": name},
            )

        except Exception as e:
            logger.error(f"Error creating bot: {e}")
            return CommandResult(
                response="Sorry, I couldn't create the bot. Please try again or use the web interface.",
            )


# Singleton instance
_command_processor: CommandProcessor | None = None


def get_command_processor() -> CommandProcessor:
    """Get the singleton command processor instance."""
    global _command_processor
    if _command_processor is None:
        _command_processor = CommandProcessor()
    return _command_processor
