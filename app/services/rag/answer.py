from app.services.rag.generation import (
    generate_answer,
    condense_query_with_history,
    generate_small_talk_answer,
)
from app.services.rag.retrieval import retrieve_knowledge
import re

FALLBACK_INSUFFICIENT_KNOWLEDGE = (
    "I couldn't find relevant information in the available "
    "support documentation. Please contact support for help."
)
# Match pure social phrases
PURE_GREETINGS = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "howdy",
    "how's it going",
    "what's up",
}
PURE_GRATITUDE = {
    "thanks",
    "thank you",
    "thanks a lot",
    "thank you so much",
    "appreciate it",
    "thx",
}
PURE_FAREWELLS = {"bye", "goodbye", "see you", "have a good day", "take care"}
DYNAMIC_SMALL_TALK_PHRASES = {
    "how are you",
    "how are you doing",
    "how's it going",
    "who are you",
    "what can you do",
    "are you an ai",
    "are you human",
}
# QUESTION_INDICATORS = re.compile(
#     r"(\?|how|where|when|why|what|can you|could you|unable|not working|issue|problem|order|refund|password)",
#     re.IGNORECASE,
# )
# Direct, quick canned responses for pure social pleasantries (zero API delay)
SOCIAL_RESPONSES = {
    "greeting": "Hello! I'm your AI support assistant. How can I help you today?",
    "gratitude": "You're very welcome! Let me know if you need help with anything else.",
    "farewell": "Goodbye! Have a great day, and feel free to reach out if you need further assistance.",
}


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

    # Social intent
    social_intent = match_pure_social_intent(question)
    if social_intent and social_intent != "dynamic":
        return RAGAnswer(
            SOCIAL_RESPONSES[social_intent],
            sources=[],
            has_knowledge=True,
        )
    if social_intent == "dynamic":
        answer_text = await generate_small_talk_answer(
            question=question,
            conversation_history=conversation_history,
        )
        return RAGAnswer(
            answer_text,
            sources=[],
            has_knowledge=True,
        )

    # Context query re-write
    search_query = question
    if conversation_history:
        search_query = await condense_query_with_history(question, conversation_history)

    # Knowledge retrieve
    chunks = await retrieve_knowledge(search_query, limit=3)

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
    sources = sorted({chunk["source"] for chunk in relevant_chunks})

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


def match_pure_social_intent(message: str) -> str | None:
    """
    Returns 'greeting', 'gratitude', or 'farewell' ONLY if the message
    is pure small talk without a support question.
    """
    clean = message.strip().lower()
    clean_stripped = re.sub(r"[^\w\s]", "", clean).strip()
    # If it asks a question or has support keywords, don't intercept it here
    # if QUESTION_INDICATORS.search(clean) and len(clean.split()) > 4:
    #     return None
    if clean_stripped in PURE_GREETINGS:
        return "greeting"
    if clean_stripped in PURE_GRATITUDE:
        return "gratitude"
    if clean_stripped in PURE_FAREWELLS:
        return "farewell"
    if clean_stripped in DYNAMIC_SMALL_TALK_PHRASES:
        return "dynamic"
    return None
