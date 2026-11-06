import asyncio
import logging

logging.basicConfig(level=logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
from app.db.session import engine
from app.services.rag.answer import answer_question


EVALUATION_CASES = [
    {
        "question": "I forgot my password. How can I reset it?",
        "expected_source": "password_reset.md",
        "must_mention": ["email", "reset"],
    },
    {
        "question": "What should I do if my password reset email never arrives?",
        "expected_source": "password_reset.md",
        "must_mention": ["spam", "support"],
    },
    {
        "question": "How can I check where my order is?",
        "expected_source": "order_tracking.md",
        "must_mention": ["orders", "status"],
    },
    {
        "question": "My order has no tracking information. What should I do?",
        "expected_source": "order_tracking.md",
        "must_mention": ["support", "order"],
    },
    {
        "question": "How do I request a refund, and is it guaranteed?",
        "expected_source": "refund_policy.md",
        "must_mention": ["support", "approval"],
    },
    {
        "question": "How long does a refund take, and what is the refund deadline?",
        "expected_source": "refund_policy.md",
        "must_mention": ["processing"],
    },
    {
        "question": "What is your company's CEO's name?",
        "expected_source": None,
        "must_mention": [],
    },
    {
        "question": "What is the exact refund deadline in days?",
        "expected_source": "refund_policy.md",
        "must_mention": ["does not", "deadline"],
    },
    {
        "question": "Can you guarantee that my refund will be approved?",
        "expected_source": "refund_policy.md",
        "must_mention": ["guarantee"],
    },
]


async def main() -> None:
    try:
        for index, case in enumerate(EVALUATION_CASES, start=1):
            print("\n" + "=" * 80)
            print(f"CASE {index}: {case['question']}")
            print("=" * 80)

            try:
                answer = await answer_question(case["question"])
                print(f"\nANSWER:\n{answer}")

                if case["expected_source"] is None:
                    print(
                        "\nMANUAL CHECK: The documentation does not identify "
                        "the CEO. Does the answer clearly admit this?"
                    )
                else:
                    missing = [
                        term
                        for term in case["must_mention"]
                        if term.lower() not in answer.lower()
                    ]

                    if missing:
                        print(
                            "\nREVIEW: Expected keywords not found: "
                            + ", ".join(missing)
                        )
                    else:
                        print("\nKEYWORD CHECK: Passed")

                    print(
                        "MANUAL CHECK: Confirm the answer is accurate, "
                        "grounded in the documentation, and not misleading."
                    )

            except Exception as exc:
                print(f"\nERROR: {type(exc).__name__}: {exc}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
