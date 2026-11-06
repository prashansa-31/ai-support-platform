from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.conversation import Conversation
from app.models.user import User


async def get_accessible_conversation(
    conversation_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Conversation:
    query = select(Conversation).where(Conversation.id == conversation_id)

    if current_user.role == "customer":
        query = query.where(Conversation.user_id == current_user.id)

    elif current_user.role == "support":
        query = query.where(Conversation.assigned_to_id == current_user.id)

    elif current_user.role == "admin":
        # Admins have supervisory access to view all conversations
        pass

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role cannot access conversations",
        )

    result = await db.execute(query)
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation
