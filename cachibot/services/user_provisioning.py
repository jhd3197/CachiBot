"""
User Provisioning Service

Handles find-or-create logic for users coming from the CachiBot website
via the auth bridge (cloud deploy mode).
"""

import logging
import uuid
from datetime import datetime, timezone

from cachibot.models.auth import UserInDB, UserRole
from cachibot.storage.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UserProvisioningService:
    """Provisions V2 platform users from website identity."""

    def __init__(self) -> None:
        self._repo = UserRepository()

    async def provision_from_website(
        self,
        email: str,
        website_user_id: int,
        tier: str = "free",
        credits: float = 0.0,
        is_admin: bool = False,
    ) -> UserInDB:
        """Find or create a V2 user from website identity.

        On each call, mutable fields (tier, credits, website_user_id) are
        synced from the website so they stay up-to-date.

        Args:
            email: User's email from the website.
            website_user_id: The website's INT user ID.
            tier: User tier from the website.
            credits: Credit balance from the website.
            is_admin: Whether the user is an admin on the website.

        Returns:
            The provisioned (or updated) UserInDB.
        """
        user = await self._repo.get_user_by_email(email.lower())

        if user:
            # Update mutable fields (tier/credits may have changed on website)
            await self._repo.update_website_fields(
                user.id,
                website_user_id=website_user_id,
                tier=tier,
                credit_balance=credits,
            )
            # Re-fetch to get updated fields
            updated = await self._repo.get_user_by_id(user.id)
            if updated:
                return updated
            return user

        # Create new user (no password — cloud users auth via website)
        new_user = UserInDB(
            id=str(uuid.uuid4()),
            email=email.lower(),
            username=email.split("@")[0] + "_" + str(uuid.uuid4())[:4],
            password_hash="!cloud-user-no-password",  # Sentinel, never matches bcrypt
            role=UserRole.ADMIN if is_admin else UserRole.USER,
            is_active=True,
            is_verified=True,
            website_user_id=website_user_id,
            tier=tier,
            credit_balance=credits,
            created_at=datetime.now(timezone.utc),
        )

        await self._repo.create_user(new_user)
        return new_user
