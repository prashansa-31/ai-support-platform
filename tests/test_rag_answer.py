from unittest.mock import AsyncMock, patch
import pytest
from app.services.rag import answer as rag_answer


async def test_answer_question_retrieves_context_and_generates_answer():
    retrieved_chunks = [
        {
            "source": "password_reset.md",
            "content": "Open the login page and select Forgot password.",
            "similarity": 0.8,
        }
    ]

    expected_answer = (
        "Open the login page, select Forgot password, "
        "and follow the reset instructions."
    )

    with (
        patch(
            "app.services.rag.answer.retrieve_knowledge",
            new_callable=AsyncMock,
            return_value=retrieved_chunks,
        ) as mock_retrieve,
        patch(
            "app.services.rag.answer.generate_answer",
            new_callable=AsyncMock,
            return_value=expected_answer,
        ) as mock_generate,
    ):
        answer = await rag_answer.answer_question("How do I reset my password?")

    assert answer == expected_answer
    mock_retrieve.assert_awaited_once_with(
        "How do I reset my password?",
        limit=3,
    )
    mock_generate.assert_awaited_once_with(
        question="How do I reset my password?",
        context_chunks=[
            "Source: password_reset.md\nOpen the login page and select Forgot password."
        ],
    )


async def test_answer_question_returns_fallback_when_no_chunks_found():
    with (
        patch(
            "app.services.rag.answer.retrieve_knowledge",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_retrieve,
        patch(
            "app.services.rag.answer.generate_answer",
            new_callable=AsyncMock,
        ) as mock_generate,
    ):
        answer = await rag_answer.answer_question("Where is my order?")

    assert answer == (
        "I couldn't find relevant information in the available "
        "support documentation. Please contact support for help."
    )
    mock_retrieve.assert_awaited_once_with(
        "Where is my order?",
        limit=3,
    )
    mock_generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_answer_uses_retrieved_context(monkeypatch):
    async def fake_retrieve_knowledge(question, limit=3):
        return [
            {
                "source": "refund_policy.md",
                "content": (
                    "Refund eligibility depends on the product or service "
                    "and applicable terms. Support must review each request."
                ),
                "similarity": 0.9,
            }
        ]

    async def fake_generate_answer(question, context_chunks):
        assert any("refund_policy.md" in chunk for chunk in context_chunks)
        return (
            "Refunds are not guaranteed. Support must review your request "
            "before confirming eligibility."
        )

    monkeypatch.setattr(rag_answer, "retrieve_knowledge", fake_retrieve_knowledge)
    monkeypatch.setattr(rag_answer, "generate_answer", fake_generate_answer)

    answer = await rag_answer.answer_question("Can you guarantee my refund?")

    assert "not guaranteed" in answer.lower()
    assert "review" in answer.lower()


@pytest.mark.asyncio
async def test_answer_does_not_invent_refund_deadline(monkeypatch):
    async def fake_retrieve_knowledge(question, limit=3):
        return [
            {
                "source": "refund_policy.md",
                "content": (
                    "The documentation does not define a specific "
                    "refund window or deadline."
                ),
                "similarity": 0.9,
            }
        ]

    async def fake_generate_answer(question, context_chunks):
        return "The documentation does not specify a refund deadline."

    monkeypatch.setattr(rag_answer, "retrieve_knowledge", fake_retrieve_knowledge)
    monkeypatch.setattr(rag_answer, "generate_answer", fake_generate_answer)

    answer = await rag_answer.answer_question(
        "What is the exact refund deadline in days?"
    )

    assert "deadline" in answer.lower()
    assert any(
        phrase in answer.lower()
        for phrase in ("does not specify", "does not define", "not specified")
    )


@pytest.mark.asyncio
async def test_answer_abstains_when_no_context_is_retrieved(monkeypatch):
    async def fake_retrieve_knowledge(question, limit=3):
        return []

    async def unexpected_generate_answer(question, context_chunks):
        pytest.fail("Generation should not run when no chunks are retrieved")

    monkeypatch.setattr(rag_answer, "retrieve_knowledge", fake_retrieve_knowledge)
    monkeypatch.setattr(rag_answer, "generate_answer", unexpected_generate_answer)

    answer = await rag_answer.answer_question("What is the company's CEO's name?")

    assert "couldn't find relevant information" in answer.lower()
