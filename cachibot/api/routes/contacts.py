"""
Contacts API Routes

CRUD endpoints for managing bot contacts.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cachibot.api.auth import require_bot_access, require_bot_access_level
from cachibot.models.auth import User
from cachibot.models.capabilities import Contact
from cachibot.models.group import BotAccessLevel
from cachibot.storage.repository import ContactsRepository

router = APIRouter(prefix="/api/bots/{bot_id}/contacts", tags=["contacts"])

# Repository instance
repo = ContactsRepository()


# Request/Response models
class ContactCreate(BaseModel):
    """Request body for creating a contact."""

    name: str
    details: str | None = None


class ContactUpdate(BaseModel):
    """Request body for updating a contact."""

    name: str
    details: str | None = None


class ContactResponse(BaseModel):
    """Response model for a contact."""

    id: str
    bot_id: str
    name: str
    details: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_contact(cls, contact: Contact) -> "ContactResponse":
        return cls(
            id=contact.id,
            bot_id=contact.bot_id,
            name=contact.name,
            details=contact.details,
            created_at=contact.created_at.isoformat(),
            updated_at=contact.updated_at.isoformat(),
        )


@router.get("")
async def list_contacts(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[ContactResponse]:
    """Get all contacts for a bot."""
    contacts = await repo.get_contacts_by_bot(bot_id)
    return [ContactResponse.from_contact(c) for c in contacts]


@router.post("", status_code=201)
async def create_contact(
    bot_id: str,
    body: ContactCreate,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> ContactResponse:
    """Create a new contact for a bot."""
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Contact name is required")

    now = datetime.utcnow()
    contact = Contact(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        name=body.name.strip(),
        details=body.details,
        created_at=now,
        updated_at=now,
    )
    await repo.save_contact(contact)
    return ContactResponse.from_contact(contact)


@router.get("/{contact_id}")
async def get_contact(
    bot_id: str,
    contact_id: str,
    user: User = Depends(require_bot_access),
) -> ContactResponse:
    """Get a specific contact."""
    contact = await repo.get_contact(contact_id)
    if contact is None or contact.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ContactResponse.from_contact(contact)


@router.put("/{contact_id}")
async def update_contact(
    bot_id: str,
    contact_id: str,
    body: ContactUpdate,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> ContactResponse:
    """Update an existing contact."""
    contact = await repo.get_contact(contact_id)
    if contact is None or contact.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Contact not found")

    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Contact name is required")

    contact.name = body.name.strip()
    contact.details = body.details
    contact.updated_at = datetime.utcnow()

    await repo.update_contact(contact)
    return ContactResponse.from_contact(contact)


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(
    bot_id: str,
    contact_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> None:
    """Delete a contact."""
    contact = await repo.get_contact(contact_id)
    if contact is None or contact.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Contact not found")

    await repo.delete_contact(contact_id)
