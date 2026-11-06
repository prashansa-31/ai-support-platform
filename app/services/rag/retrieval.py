from sqlalchemy import text
from app.config import settings
from app.db.session import AsyncSessionLocal
import os

os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
from sentence_transformers import SentenceTransformer


MODEL_NAME = settings.embedding_model_name

# Load the embedding model once, rather than for every question.
_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(MODEL_NAME)

    return _embedding_model


async def retrieve_knowledge(
    question: str,
    limit: int = 3,
) -> list[dict]:
    """Return the most relevant knowledge chunks for a question."""

    if not question.strip():
        raise ValueError("Question cannot be empty")

    if limit < 1:
        raise ValueError("Limit must be at least 1")

    model = get_embedding_model()
    embedding = model.encode(
        question,
        normalize_embeddings=True,
    ).tolist()

    query = text("""
        SELECT
            source,
            content,
            embedding <=> CAST(:embedding AS vector) AS distance
        FROM knowledge_chunks
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            query,
            {
                "embedding": str(embedding),
                "limit": limit,
            },
        )
        rows = result.mappings().all()

    return [
        {
            "source": row["source"],
            "content": row["content"],
            "similarity": 1 - float(row["distance"]),
        }
        for row in rows
    ]
