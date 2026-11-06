import asyncio
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from app.db.session import AsyncSessionLocal, engine
from app.config import settings


MODEL_NAME = settings.embedding_model_name


async def main() -> None:
    question = input("Customer question: ").strip()
    if not question:
        print("Please enter a question.")
        return

    model = SentenceTransformer(MODEL_NAME)
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
        LIMIT 3
    """)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            query,
            {"embedding": str(embedding)},
        )
        rows = result.mappings().all()

    if not rows:
        print("No knowledge chunks found.")
        return

    print("\nMost relevant knowledge:")
    for rank, row in enumerate(rows, start=1):
        similarity = 1 - row["distance"]
        print(f"\n{rank}. Source: {row['source']}")
        print(f"   Cosine similarity: {similarity:.4f}")
        print(f"   Content: {row['content']}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
