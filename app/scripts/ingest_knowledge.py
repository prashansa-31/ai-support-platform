import asyncio
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sqlalchemy import delete, select

from app.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.models import KnowledgeChunk


KNOWLEDGE_DIR = Path("sample_knowledge")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def split_text(text: str) -> list[str]:
    """Split text into overlapping chunks, preserving word boundaries."""
    words = text.split()
    chunks = []
    current_words = []
    current_length = 0

    for word in words:
        added_length = len(word) + (1 if current_words else 0)

        if current_words and current_length + added_length > CHUNK_SIZE:
            chunk = " ".join(current_words)
            chunks.append(chunk)

            overlap_words = []
            overlap_length = 0

            for previous_word in reversed(current_words):
                extra_length = len(previous_word) + (1 if overlap_words else 0)
                if overlap_length + extra_length > CHUNK_OVERLAP:
                    break
                overlap_words.insert(0, previous_word)
                overlap_length += extra_length

            current_words = overlap_words
            current_length = len(" ".join(current_words))

        current_words.append(word)
        current_length = len(" ".join(current_words))

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


async def main() -> None:
    database = settings.database_url.split("/")[-1].split("?")[0]
    if database == "ai_support_test":
        raise RuntimeError(f"Refusing to ingest into unexpected database: {database}")

    documents = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not documents:
        raise RuntimeError(f"No Markdown documents found in {KNOWLEDGE_DIR}")

    records = []
    for document in documents:
        text = document.read_text(encoding="utf-8").strip()
        for chunk in split_text(text):
            records.append(
                {
                    "source": document.name,
                    "content": chunk,
                }
            )

    if not records:
        raise RuntimeError("No text chunks were generated.")

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(
        [record["content"] for record in records],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    if embeddings.shape != (len(records), 384):
        raise RuntimeError(f"Unexpected embedding shape: {embeddings.shape}")

    async with AsyncSessionLocal() as session:
        # Replace the existing ingested chunks from these source files.
        sources = sorted({record["source"] for record in records})
        await session.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.source.in_(sources))
        )

        session.add_all(
            [
                KnowledgeChunk(
                    source=record["source"],
                    content=record["content"],
                    embedding=embedding.tolist(),
                )
                for record, embedding in zip(records, embeddings)
            ]
        )
        await session.commit()

        result = await session.execute(
            select(KnowledgeChunk.source, KnowledgeChunk.id).where(
                KnowledgeChunk.source.in_(sources)
            )
        )
        stored = result.all()

    print(f"Documents processed: {len(documents)}")
    print(f"Chunks generated: {len(records)}")
    print(f"Chunks stored: {len(stored)}")
    print(f"Embedding dimensions: {embeddings.shape[1]}")
    for source in sources:
        count = sum(1 for row in stored if row.source == source)
        print(f"  {source}: {count} chunks")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
