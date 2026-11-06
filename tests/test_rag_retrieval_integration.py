import os
import pytest
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.config import settings
from app.models import KnowledgeChunk
import app.services.rag.retrieval as retrieval


async def test_password_reset_question_retrieves_password_reset_document():
    load_dotenv()
    database_url = os.environ.get("TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    if not database_url.endswith("/ai_support_test"):
        pytest.fail("Integration test must use ai_support_test")

    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )

    test_source = "__test_rag_retrieval_integration__.md"

    try:
        model = SentenceTransformer(settings.embedding_model_name)

        documents = [
            (
                test_source,
                "To reset your password, open the login page, select "
                "Forgot password, enter your registered email address, "
                "and follow the reset link sent to your inbox.",
            ),
            (
                test_source,
                "If a customer wants a refund, contact the support team "
                "with the order reference and an explanation of the issue.",
            ),
        ]

        async with session_factory() as session:
            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.source == test_source)
            )

            for source, content in documents:
                embedding = model.encode(
                    content,
                    normalize_embeddings=True,
                ).tolist()

                session.add(
                    KnowledgeChunk(
                        source=source,
                        content=content,
                        embedding=embedding,
                    )
                )

            await session.commit()

        original_session_local = retrieval.AsyncSessionLocal
        original_model_getter = retrieval.get_embedding_model

        retrieval.AsyncSessionLocal = session_factory
        retrieval.get_embedding_model = lambda: model

        try:
            results = await retrieval.retrieve_knowledge(
                "How do I reset my password?",
                limit=2,
            )
        finally:
            retrieval.AsyncSessionLocal = original_session_local
            retrieval.get_embedding_model = original_model_getter

        assert results
        assert "reset your password" in results[0]["content"].lower()
        assert results[0]["similarity"] > 0.5

    finally:
        async with session_factory() as session:
            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.source == test_source)
            )
            await session.commit()

        await engine.dispose()
