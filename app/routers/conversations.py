from typing import Annotated
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy import func, or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    ConversationAssignmentUpdate,
    ConversationStatus,
    ConversationPriority,
)
from app.dependencies.conversations import get_accessible_conversation
from app.models.message import Message
from app.schemas.message import (
    MessageListResponse,
    MessageCreate,
    MessageResponse,
    AIAnswerResponse,
)
from app.services.rag.answer import answer_question

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Conversation:
    conversation = Conversation(
        user_id=current_user.id,
        title=payload.title,
        assigned_type="ai",
        status="open",
    )
    db.add(conversation)
    await db.flush()
    if payload.initial_message:
        first_message = Message(
            conversation_id=conversation.id,
            sender_id=current_user.id,
            role="customer",
            content=payload.initial_message,
            sequence_number=1,
            token_count=0,
        )
        db.add(first_message)
        await db.flush()
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.get(
    "",
    response_model=ConversationListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: ConversationStatus | None = Query(default=None),
    priority: ConversationPriority | None = Query(default=None),
    assigned_to_id: str | None = Query(default=None),
    unassigned: bool | None = Query(default=None),
) -> ConversationListResponse:
    filters = []
    if current_user.role == "customer":
        filters.append(Conversation.user_id == current_user.id)
    elif current_user.role == "support":
        filters.append(Conversation.assigned_to_id == current_user.id)
    elif current_user.role == "admin":
        # Admin can view all tickets, and optionally filter by assignee or unassigned status
        if unassigned is True:
            filters.append(Conversation.assigned_to_id.is_(None))
        elif assigned_to_id is not None:
            filters.append(Conversation.assigned_to_id == assigned_to_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role cannot access conversations",
        )

    # filters = [access_filter]
    if status is not None:
        filters.append(Conversation.status == status.value)
    if priority is not None:
        filters.append(Conversation.priority == priority.value)

    combined_filter = and_(*filters)

    total_result = await db.execute(
        select(func.count()).select_from(Conversation).where(combined_filter)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Conversation)
        .where(combined_filter)
        .order_by(
            Conversation.updated_at.desc(),
            Conversation.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    conversations = result.scalars().all()

    return ConversationListResponse(
        items=conversations,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
)
async def get_conversation(
    conversation: Annotated[
        Conversation,
        Depends(get_accessible_conversation),
    ],
) -> Conversation:
    return conversation


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_conversation_messages(
    conversation: Annotated[
        Conversation,
        Depends(get_accessible_conversation),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> MessageListResponse:
    message_filter = Message.conversation_id == conversation.id

    total_result = await db.execute(
        select(func.count()).select_from(Message).where(message_filter)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Message)
        .where(message_filter)
        .order_by(Message.sequence_number.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    messages = result.scalars().all()

    return MessageListResponse(
        items=messages,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation_message(
    payload: MessageCreate,
    conversation: Annotated[
        Conversation,
        Depends(get_accessible_conversation),
    ],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Message:
    # Determine the message role from the authenticated user.
    if current_user.role == "customer":
        message_role = "customer"
    elif current_user.role in {"support", "admin"}:
        message_role = "support"
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role cannot send messages",
        )

    # Lock this conversation row to safely assign sequence numbers.
    locked_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation.id).with_for_update()
    )
    locked_conversation = locked_result.scalar_one()

    # Find the next sequence number while holding the lock.
    sequence_result = await db.execute(
        select(func.max(Message.sequence_number)).where(
            Message.conversation_id == locked_conversation.id
        )
    )
    last_sequence = sequence_result.scalar_one()

    next_sequence = (last_sequence or 0) + 1

    message = Message(
        conversation_id=locked_conversation.id,
        sender_id=current_user.id,
        role=message_role,
        content=payload.content,
        sequence_number=next_sequence,
        token_count=0,
    )

    db.add(message)
    await db.flush()
    await db.refresh(message)

    return message


@router.post(
    "/{conversation_id}/ask",
    response_model=AIAnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ask_ai(
    payload: MessageCreate,
    conversation: Annotated[
        Conversation,
        Depends(get_accessible_conversation),
    ],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIAnswerResponse:
    if current_user.role != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can ask the AI assistant",
        )
    # Check if a human agent has already taken over
    # possibility of converting ai chat to human-human chat window?
    if getattr(conversation, "assigned_type", "ai") == "human":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ticket has been assigned to a human support agent. Please send regular messages.",
        )
    # Fetch recent conversation history for context before adding the new question
    locked_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation.id).with_for_update()
    )
    locked_conversation = locked_result.scalar_one()
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == locked_conversation.id)
        .order_by(Message.sequence_number.asc())
        .limit(10)
    )
    past_messages = history_result.scalars().all()
    history = [{"role": msg.role, "content": msg.content} for msg in past_messages]
    sequence_result = await db.execute(
        select(func.max(Message.sequence_number)).where(
            Message.conversation_id == locked_conversation.id
        )
    )
    last_sequence = sequence_result.scalar_one()
    question_message = Message(
        conversation_id=locked_conversation.id,
        sender_id=current_user.id,
        role="customer",
        content=payload.content,
        sequence_number=(last_sequence or 0) + 1,
        token_count=0,
    )
    db.add(question_message)
    await db.flush()
    await db.refresh(question_message)
    await db.commit()
    try:
        if history:  # Old conversation
            rag_answer = await answer_question(
                question=payload.content,
                conversation_history=history,
            )
        else:  # New conversation
            rag_answer = await answer_question(payload.content)
        answer_text = str(rag_answer)
        sources = getattr(rag_answer, "sources", [])
        has_knowledge = getattr(rag_answer, "has_knowledge", True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "AI answer generation failed. "
                "Your question was saved; please try again."
            ),
        ) from exc
    # save AI reply with metadata
    locked_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation.id).with_for_update()
    )
    locked_conversation = locked_result.scalar_one()
    sequence_result = await db.execute(
        select(func.max(Message.sequence_number)).where(
            Message.conversation_id == locked_conversation.id
        )
    )
    last_sequence = sequence_result.scalar_one()
    answer_message = Message(
        conversation_id=locked_conversation.id,
        sender_id=None,
        role="assistant",
        content=answer_text,
        sequence_number=(last_sequence or 0) + 1,
        token_count=0,
        metadata_json={
            "sources": sources,
            "has_knowledge": has_knowledge,
        },
    )
    db.add(answer_message)
    await db.flush()
    await db.refresh(answer_message)
    await db.commit()
    return AIAnswerResponse(
        question=question_message,
        answer=answer_message,
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
)
async def update_conversation(
    payload: ConversationUpdate,
    conversation: Annotated[
        Conversation,
        Depends(get_accessible_conversation),
    ],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Conversation:
    # Reject empty update requests.
    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )

    # Only support agents and admins may update these fields.
    if current_user.role not in {"support", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to update this conversation",
        )

    # Support agents may update only conversations assigned to them.
    if (
        current_user.role == "support"
        and conversation.assigned_to_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update conversations assigned to you",
        )

    # Apply only the fields supplied in the request.
    for field, value in updates.items():
        setattr(conversation, field, value.value)

    await db.flush()
    await db.refresh(conversation)

    return conversation


@router.patch(
    "/{conversation_id}/assignment",
    response_model=ConversationResponse,
)
async def update_conversation_assignment(
    conversation_id: str,
    payload: ConversationAssignmentUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can assign conversations",
        )

    # conversation = await get_accessible_conversation(
    #     conversation_id=conversation_id,
    #     current_user=current_user,
    #     db=db,
    # )
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if payload.assigned_to_id is not None:
        result = await db.execute(select(User).where(User.id == payload.assigned_to_id))
        support_agent = result.scalar_one_or_none()

        if (
            support_agent is None
            or support_agent.role != "support"
            or not support_agent.is_active
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Assigned user must be an active support agent",
            )

    conversation.assigned_to_id = payload.assigned_to_id

    await db.commit()
    await db.refresh(conversation)

    return conversation
