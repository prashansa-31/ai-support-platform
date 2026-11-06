from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.services.rag.retrieval import retrieve_knowledge


async def test_retrieve_knowledge_rejects_empty_question():
    with pytest.raises(ValueError, match="Question cannot be empty"):
        await retrieve_knowledge("   ")


async def test_retrieve_knowledge_rejects_invalid_limit():
    with pytest.raises(ValueError, match="Limit must be at least 1"):
        await retrieve_knowledge("How do I reset my password?", limit=0)


async def test_retrieve_knowledge_returns_expected_results():
    # Mock the embedding model so no real model needs to load.
    mock_model = MagicMock()
    mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]

    # Simulate one row returned by the database.
    mock_row = {
        "source": "password_reset.md",
        "content": "Use the Forgot Password link to reset your password.",
        "distance": 0.15,
    }

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [mock_row]

    # Mock the async database session.
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    mock_session_context = MagicMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.rag.retrieval.get_embedding_model",
            return_value=mock_model,
        ),
        patch(
            "app.services.rag.retrieval.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
    ):
        results = await retrieve_knowledge(
            "How do I reset my password?",
            limit=3,
        )

    assert len(results) == 1
    assert results[0]["source"] == "password_reset.md"
    assert "Forgot Password" in results[0]["content"]
    assert results[0]["similarity"] == pytest.approx(0.85)
    mock_model.encode.assert_called_once_with(
        "How do I reset my password?",
        normalize_embeddings=True,
    )
    mock_session.execute.assert_awaited_once()


async def test_retrieve_knowledge_returns_empty_list_when_no_chunks_exist():
    mock_model = MagicMock()
    mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    mock_session_context = MagicMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.rag.retrieval.get_embedding_model",
            return_value=mock_model,
        ),
        patch(
            "app.services.rag.retrieval.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
    ):
        results = await retrieve_knowledge("How do I track my order?")

    assert results == []


async def test_retrieve_knowledge_returns_multiple_chunks():
    mock_model = MagicMock()
    mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]

    mock_rows = [
        {
            "source": "order_tracking.md",
            "content": "Track your order using the tracking link.",
            "distance": 0.10,
        },
        {
            "source": "refund_policy.md",
            "content": "Refund eligibility depends on the policy.",
            "distance": 0.25,
        },
    ]

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = mock_rows

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    mock_session_context = MagicMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.rag.retrieval.get_embedding_model",
            return_value=mock_model,
        ),
        patch(
            "app.services.rag.retrieval.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
    ):
        results = await retrieve_knowledge(
            "How do I track my order?",
            limit=2,
        )

    assert len(results) == 2
    assert results[0]["source"] == "order_tracking.md"
    assert results[0]["similarity"] == pytest.approx(0.90)
    assert results[1]["source"] == "refund_policy.md"
    assert results[1]["similarity"] == pytest.approx(0.75)
