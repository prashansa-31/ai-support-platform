from unittest.mock import AsyncMock, patch
from tests.test_conversations import (
    register_and_login,
    auth_headers,
    configure_support_agent,
)
import asyncio
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.models import Message


def create_customer_conversation(client, email: str) -> tuple[str, str]:  # helper fn
    token = register_and_login(client, email)
    response = client.post(
        "/api/v1/conversations",
        json={"title": "AI assistant test"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return token, response.json()["id"]


def test_ask_ai_returns_question_and_answer(client):
    token, conversation_id = create_customer_conversation(
        client, "rag_api_success@example.com"
    )
    expected_answer = "Open the login page and select Forgot password."

    with patch(
        "app.routers.conversations.answer_question",
        new_callable=AsyncMock,
        return_value=expected_answer,
    ) as mock_answer:
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/ask",
            json={"content": "How do I reset my password?"},
            headers=auth_headers(token),
        )

    assert response.status_code == 201
    data = response.json()
    assert data["question"]["content"] == "How do I reset my password?"
    assert data["question"]["role"] == "customer"
    assert data["answer"]["content"] == expected_answer
    assert data["answer"]["role"] == "assistant"
    mock_answer.assert_awaited_once_with("How do I reset my password?")


def test_ask_ai_returns_502_when_generation_fails(client):
    token, conversation_id = create_customer_conversation(
        client, "rag_api_failure@example.com"
    )

    with patch(
        "app.routers.conversations.answer_question",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Simulated AI provider failure"),
    ) as mock_answer:
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/ask",
            json={"content": "Where is my order?"},
            headers=auth_headers(token),
        )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "AI answer generation failed. Your question was saved; please try again."
    )
    mock_answer.assert_awaited_once_with("Where is my order?")


def test_ask_ai_rejects_unauthenticated_request(client):
    response = client.post(
        "/api/v1/conversations/00000000-0000-0000-0000-000000000000/ask",
        json={"content": "How do I reset my password?"},
    )

    assert response.status_code == 401


def test_ask_ai_rejects_support_agent(client):
    email = "rag_api_support@example.com"
    token, conversation_id = create_customer_conversation(client, email)

    # Promote the user to support and assign the conversation.
    configure_support_agent(email, conversation_id)

    # Log in again to obtain a token reflecting the updated role.
    token = register_and_login(client, email, register_flag=False)

    with patch(
        "app.routers.conversations.answer_question",
        new_callable=AsyncMock,
    ) as mock_answer:
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/ask",
            json={"content": "How do I reset my password?"},
            headers=auth_headers(token),
        )

    assert response.status_code == 403
    assert response.json()["detail"] == ("Only customers can ask the AI assistant")
    mock_answer.assert_not_awaited()


def get_conversation_messages(conversation_id: str) -> list[dict]:
    async def fetch_messages():
        engine = create_async_engine(
            os.environ["TEST_DATABASE_URL"],
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with session_factory() as session:
                result = await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.sequence_number)
                )
                messages = result.scalars().all()

                return [
                    {"role": message.role, "content": message.content}
                    for message in messages
                ]
        finally:
            await engine.dispose()

    return asyncio.run(fetch_messages())


def test_ask_ai_preserves_question_when_generation_fails(client):
    token, conversation_id = create_customer_conversation(
        client, "rag_api_persistence@example.com"
    )
    question = "Where is my order?"

    with patch(
        "app.routers.conversations.answer_question",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Simulated AI failure"),
    ):
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/ask",
            json={"content": question},
            headers=auth_headers(token),
        )

    assert response.status_code == 502

    messages = get_conversation_messages(conversation_id)

    assert any(
        message["role"] == "customer" and message["content"] == question
        for message in messages
    )

    assert not any(
        message["role"] == "assistant" and message["content"] == question
        for message in messages
    )
