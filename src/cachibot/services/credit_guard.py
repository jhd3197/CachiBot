"""
Credit Guard — checks and deducts credits for automation execution.
"""

import logging

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Raised when a user doesn't have enough credits."""

    pass


class CreditGuard:
    """Checks credit balance before execution and deducts after."""

    async def check_before_execution(
        self, user_id: str, estimated_cost: float = 0.0
    ) -> bool:
        """Check if user has sufficient credits.

        Returns True if the user has credits (or if credit system is not enabled).
        Raises InsufficientCreditsError if balance is insufficient.
        """
        try:
            from cachibot.storage.user_repository import UserRepository

            user_repo = UserRepository()
            user = await user_repo.get(user_id)
            if not user:
                # If user not found, allow (self-hosted without user system)
                return True

            credit_balance = getattr(user, "credit_balance", None)
            if credit_balance is None:
                # Credit system not enabled
                return True

            if credit_balance < estimated_cost:
                raise InsufficientCreditsError(
                    f"Insufficient credits: {credit_balance:.4f} available, "
                    f"{estimated_cost:.4f} estimated"
                )
            return True
        except InsufficientCreditsError:
            raise
        except Exception:
            # If credit system fails, allow execution (fail-open for self-hosted)
            logger.debug("Credit check skipped: credit system unavailable")
            return True

    async def deduct_after_execution(
        self, user_id: str, actual_cost: float
    ) -> None:
        """Deduct actual cost after execution.

        If balance hits zero, pauses all user automations.
        """
        if actual_cost <= 0:
            return

        try:
            from cachibot.storage.user_repository import UserRepository

            user_repo = UserRepository()
            user = await user_repo.get(user_id)
            if not user:
                return

            credit_balance = getattr(user, "credit_balance", None)
            if credit_balance is None:
                return

            new_balance = credit_balance - actual_cost
            # Update balance (if the method exists)
            if hasattr(user_repo, "update_credit_balance"):
                await user_repo.update_credit_balance(user_id, new_balance)

            if new_balance <= 0:
                logger.warning(
                    "User %s credit balance exhausted after deducting %.4f",
                    user_id,
                    actual_cost,
                )
                await self._pause_user_automations(
                    user_id, reason="insufficient credits"
                )
        except Exception:
            logger.debug("Credit deduction skipped for user %s", user_id)

    async def _pause_user_automations(
        self, user_id: str, reason: str
    ) -> None:
        """Pause all automations for a user when credits are exhausted."""
        try:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            ws = get_ws_manager()
            msg = WSMessage.error(
                f"Automations paused: {reason}",
                code="credits_exhausted",
            )
            await ws.broadcast(msg)
        except Exception:
            logger.debug("Could not notify about paused automations")
