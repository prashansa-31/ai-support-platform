from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rag.generation import generate_answer


async def test_generate_answer_returns_stripped_response():
    mock_response = SimpleNamespace(
        text="  Open the login page and select Forgot password.  "
    )

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with (
        patch(
            "app.services.rag.generation.settings.gemini_api_key",
            "test-api-key",
        ),
        patch(
            "app.services.rag.generation.genai.Client",
            return_value=mock_client,
        ),
    ):
        answer = await generate_answer(
            question="How do I reset my password?",
            context_chunks=["Open the login page and select Forgot password."],
        )

    assert answer == "Open the login page and select Forgot password."
    mock_client.aio.models.generate_content.assert_awaited_once()


async def test_generate_answer_rejects_missing_api_key():
    with patch(
        "app.services.rag.generation.settings.gemini_api_key",
        "",
    ):
        with pytest.raises(
            RuntimeError,
            match="GEMINI_API_KEY is not configured",
        ):
            await generate_answer(
                question="How do I reset my password?",
                context_chunks=["Password reset instructions."],
            )


async def test_generate_answer_rejects_empty_question():
    with (
        patch(
            "app.services.rag.generation.settings.gemini_api_key",
            "test-api-key",
        ),
        pytest.raises(ValueError, match="Question cannot be empty"),
    ):
        await generate_answer(
            question="   ",
            context_chunks=["Some documentation."],
        )


async def test_generate_answer_returns_fallback_for_empty_context():
    with patch(
        "app.services.rag.generation.settings.gemini_api_key",
        "test-api-key",
    ):
        answer = await generate_answer(
            question="How do I reset my password?",
            context_chunks=[],
        )

    assert answer == (
        "I couldn't find relevant information in the available support documentation."
    )


async def test_generate_answer_rejects_empty_provider_response():
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        return_value=SimpleNamespace(text="   ")
    )

    with (
        patch(
            "app.services.rag.generation.settings.gemini_api_key",
            "test-api-key",
        ),
        patch(
            "app.services.rag.generation.genai.Client",
            return_value=mock_client,
        ),
        pytest.raises(RuntimeError, match="Gemini returned an empty response"),
    ):
        await generate_answer(
            question="How do I reset my password?",
            context_chunks=["Password reset instructions."],
        )
