import pytest
import os
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
import app.services.rag.retrieval as retrieval


EVALUATION_CASES = [
    {
        "question": "I forgot my password. How can I reset it?",
        "expected_source": "password_reset.md",
    },
    {
        "question": "What should I do if my password reset email never arrives?",
        "expected_source": "password_reset.md",
    },
    {
        "question": "How can I check where my order is?",
        "expected_source": "order_tracking.md",
    },
    {
        "question": "My order has no tracking information. What should I do?",
        "expected_source": "order_tracking.md",
    },
    {
        "question": "How do I request a refund, and is it guaranteed?",
        "expected_source": "refund_policy.md",
    },
    {
        "question": "How long does a refund take, and what is the refund deadline?",
        "expected_source": "refund_policy.md",
    },
]


@pytest.mark.parametrize("case", EVALUATION_CASES)
# @pytest.mark.asyncio
async def test_retrieval_finds_expected_document(case):
    database_url = os.environ["TEST_DATABASE_URL"]

    assert database_url.endswith("/ai_support_test"), (
        "Evaluation must use the ai_support_test database"
    )

    engine = create_async_engine(database_url, poolclass=NullPool)
    test_session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    original_session_factory = retrieval.AsyncSessionLocal
    retrieval.AsyncSessionLocal = test_session_factory

    try:
        results = await retrieval.retrieve_knowledge(
            case["question"],
            limit=3,
        )

        assert results, f"No chunks retrieved for question: {case['question']}"

        relevant_ranks = [
            rank
            for rank, result in enumerate(results, start=1)
            if case["expected_source"] in result["source"]
        ]

        assert relevant_ranks, (
            f"Expected {case['expected_source']} for question "
            f"{case['question']!r}, but retrieved: "
            f"{[result['source'] for result in results]}"
        )

        reciprocal_rank = 1 / relevant_ranks[0]
        print(
            f"Expected source rank: {relevant_ranks[0]}, "
            f"Reciprocal rank: {reciprocal_rank:.2f}"
        )

    finally:
        retrieval.AsyncSessionLocal = original_session_factory
        await engine.dispose()
