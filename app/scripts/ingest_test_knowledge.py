import asyncio
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import KnowledgeChunk
from app.scripts.ingest_knowledge import split_text


KNOWLEDGE_DIR = Path("sample_knowledge")
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


async def main() -> None:
    from dotenv import load_dotenv
    import os

    load_dotenv()

    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL is not configured")

    database = database_url.split("/")[-1].split("?")[0]
    if database != "ai_support_test":
        raise RuntimeError(f"Refusing to ingest into unexpected database: {database}")

    documents = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not documents:
        raise RuntimeError(f"No Markdown documents found in {KNOWLEDGE_DIR}")

    records = []
    for document in documents:
        content = document.read_text(encoding="utf-8").strip()
        for chunk in split_text(content):
            records.append({"source": document.name, "content": chunk})

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(
        [record["content"] for record in records],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
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
        print(f"Chunks stored: {len(stored)}")
        for source in sources:
            count = sum(1 for row in stored if row.source == source)
            print(f"  {source}: {count} chunks")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
