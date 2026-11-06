from app.services.rag.generation import generate_answer
from app.services.rag.retrieval import retrieve_knowledge

FALLBACK_INSUFFICIENT_KNOWLEDGE = (
    "I couldn't find relevant information in the available "
    "support documentation. Please contact support for help."
)


class RAGAnswer(str):
    """String result that also carries RAG metadata (sources and has_knowledge)."""

    sources: list[str]
    has_knowledge: bool

    def __new__(
        cls,
        text: str,
        sources: list[str] | None = None,
        has_knowledge: bool = True,
    ):
        obj = super().__new__(cls, text)
        obj.sources = sources or []
        obj.has_knowledge = has_knowledge
        return obj


async def answer_question(
    question: str,
    conversation_history: list[dict[str, str]] | None = None,
    similarity_threshold: float = 0.25,
) -> RAGAnswer:
    """Retrieve support knowledge and generate a grounded answer with history and metadata."""
    chunks = await retrieve_knowledge(question, limit=3)

    # Filter by similarity threshold
    relevant_chunks = [
        chunk for chunk in chunks if chunk.get("similarity", 0) >= similarity_threshold
    ]

    # If no relevant documentation was found, flag insufficient knowledge
    if not relevant_chunks:
        return RAGAnswer(
            FALLBACK_INSUFFICIENT_KNOWLEDGE,
            sources=[],
            has_knowledge=False,
        )

    context_chunks = [
        f"Source: {chunk['source']}\n{chunk['content']}" for chunk in relevant_chunks
    ]
    sources = sorted(list({chunk["source"] for chunk in relevant_chunks}))

    kwargs = {
        "question": question,
        "context_chunks": context_chunks,
    }
    if conversation_history:
        kwargs["conversation_history"] = conversation_history

    answer_text = await generate_answer(**kwargs)

    return RAGAnswer(
        answer_text,
        sources=sources,
        has_knowledge=True,
    )
