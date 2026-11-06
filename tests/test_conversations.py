import asyncio
import os
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.models import Message
from sqlalchemy import update, select
from app.models.user import User
from app.models.conversation import Conversation


def register_and_login(
    client, email: str, register_flag: bool = True
) -> str:  # helper fn
    password = "TestPassword123!"
    if register_flag:
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": "Test User",
            },
        )
        assert register_response.status_code == 201, (
            f"Registration failed for {email}: "
            f"{register_response.status_code} - "
            f"{register_response.text}"
        )

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200

    return login_response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:  # helper fn
    return {"Authorization": f"Bearer {token}"}


def insert_test_messages(
    conversation_id: str,
    messages: list[dict],
) -> None:  # helper fn
    async def insert():
        engine = create_async_engine(
            os.environ["TEST_DATABASE_URL"],
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with session_factory() as session:
                for message in messages:
                    session.add(
                        Message(
                            conversation_id=conversation_id,
                            role=message["role"],
                            content=message["content"],
                            sequence_number=message["sequence_number"],
                            token_count=message.get("token_count", 0),
                        )
                    )

                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(insert())


def configure_support_agent(
    support_email: str,
    conversation_id: str,
    assign_conversation: bool = True,
) -> None:  # helper fn
    async def configure():
        engine = create_async_engine(
            os.environ["TEST_DATABASE_URL"],
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with session_factory() as session:
                user_result = await session.execute(
                    select(User).where(User.email == support_email)
                )
                support_user = user_result.scalar_one()
                support_user.role = "support"

                if assign_conversation:
                    conversation_result = await session.execute(
                        select(Conversation).where(Conversation.id == conversation_id)
                    )
                    conversation = conversation_result.scalar_one()
                    conversation.assigned_to_id = support_user.id

                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(configure())


def set_user_role(email: str, role: str) -> None:  # helper fn
    async def update_role():
        engine = create_async_engine(
            os.environ["TEST_DATABASE_URL"],
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with session_factory() as session:
                result = await session.execute(select(User).where(User.email == email))
                user = result.scalar_one()
                user.role = role
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(update_role())


def get_user_id(email: str) -> str:  # helper fn
    async def fetch_user_id() -> str:  # Queries PostgreSQL using await
        engine = create_async_engine(
            os.environ["TEST_DATABASE_URL"],
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with session_factory() as session:
                result = await session.execute(select(User).where(User.email == email))
                user = result.scalar_one()
                return user.id
        finally:
            await engine.dispose()

    return asyncio.run(fetch_user_id())  # Runs the async database operation


def set_user_active_status(email: str, is_active: bool) -> None:  # helper fn
    async def update_active_status():
        engine = create_async_engine(
            os.environ["TEST_DATABASE_URL"],
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with session_factory() as session:
                result = await session.execute(select(User).where(User.email == email))
                user = result.scalar_one()
                user.is_active = is_active
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(update_active_status())


def test_create_conversation(client):  # test-1
    token = register_and_login(client, "customer@example.com")

    response = client.post(
        "/api/v1/conversations",
        json={"title": "Cannot access my account"},
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    data = response.json()
    assert data["title"] == "Cannot access my account"
    assert data["status"] == "open"
    assert data["priority"] == "normal"
    assert data["user_id"]
    assert data["assigned_to_id"] is None


def test_create_conversation_requires_authentication(client):  # test-2
    response = client.post(
        "/api/v1/conversations",
        json={"title": "Help me"},
    )

    assert response.status_code == 401


def test_create_conversation_rejects_blank_title(client):  # test-3
    token = register_and_login(client, "blank@example.com")

    response = client.post(
        "/api/v1/conversations",
        json={"title": "   "},
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_create_conversation_ignores_client_supplied_owner(client):  # test-4
    owner_token = register_and_login(client, "owner@example.com")
    other_token = register_and_login(client, "other@example.com")

    owner_response = client.post(
        "/api/v1/conversations",
        json={"title": "My conversation"},
        headers=auth_headers(owner_token),
    )
    assert owner_response.status_code == 201
    owner_id = owner_response.json()["user_id"]

    attempted_response = client.post(
        "/api/v1/conversations",
        json={
            "title": "Attempt to impersonate owner",
            "user_id": owner_id,
        },
        headers=auth_headers(other_token),
    )

    assert attempted_response.status_code == 201
    assert attempted_response.json()["user_id"] != owner_id


def test_list_conversations_returns_only_own_conversations(client):  # test-5
    token_a = register_and_login(client, "customer-a@example.com")
    token_b = register_and_login(client, "customer-b@example.com")

    created_a = client.post(
        "/api/v1/conversations",
        json={"title": "Customer A ticket"},
        headers=auth_headers(token_a),
    )
    created_b = client.post(
        "/api/v1/conversations",
        json={"title": "Customer B ticket"},
        headers=auth_headers(token_b),
    )

    assert created_a.status_code == 201
    assert created_b.status_code == 201

    response = client.get(
        "/api/v1/conversations",
        headers=auth_headers(token_a),
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Customer A ticket"
    assert data["items"][0]["user_id"] == created_a.json()["user_id"]


def test_list_conversations_requires_authentication(client):  # test-6
    response = client.get("/api/v1/conversations")

    assert response.status_code == 401


def test_list_conversations_supports_pagination(client):  # test-7
    token = register_and_login(client, "pagination@example.com")

    for index in range(3):
        response = client.post(
            "/api/v1/conversations",
            json={"title": f"Ticket {index}"},
            headers=auth_headers(token),
        )
        assert response.status_code == 201

    response = client.get(
        "/api/v1/conversations?page=1&page_size=2",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_list_conversations_rejects_invalid_pagination(client):  # test-8
    token = register_and_login(client, "invalid-page@example.com")

    response = client.get(
        "/api/v1/conversations?page=0",
        headers=auth_headers(token),
    )
    assert response.status_code == 422

    response = client.get(
        "/api/v1/conversations?page_size=101",
        headers=auth_headers(token),
    )
    assert response.status_code == 422


def test_get_conversation_messages_in_chronological_order(client):  # test-9
    token = register_and_login(client, "history@example.com")

    created = client.post(
        "/api/v1/conversations",
        json={"title": "Conversation history"},
        headers=auth_headers(token),
    )
    assert created.status_code == 201

    conversation_id = created.json()["id"]

    insert_test_messages(
        conversation_id,
        [
            {
                "role": "assistant",
                "content": "Second message",
                "sequence_number": 2,
            },
            {
                "role": "user",
                "content": "First message",
                "sequence_number": 1,
            },
            {
                "role": "assistant",
                "content": "Third message",
                "sequence_number": 3,
            },
        ],
    )

    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 3
    assert [item["sequence_number"] for item in data["items"]] == [1, 2, 3]
    assert [item["content"] for item in data["items"]] == [
        "First message",
        "Second message",
        "Third message",
    ]


def test_get_conversation_messages_supports_pagination(client):  # test-10
    token = register_and_login(client, "history-page@example.com")

    created = client.post(
        "/api/v1/conversations",
        json={"title": "Paginated history"},
        headers=auth_headers(token),
    )
    assert created.status_code == 201

    conversation_id = created.json()["id"]

    insert_test_messages(
        conversation_id,
        [
            {
                "role": "user",
                "content": f"Message {index}",
                "sequence_number": index,
            }
            for index in range(1, 6)
        ],
    )

    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages?page=2&page_size=2",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 5
    assert data["page"] == 2
    assert data["page_size"] == 2
    assert [item["sequence_number"] for item in data["items"]] == [3, 4]


def test_get_conversation_messages_denies_another_customer(client):  # test-11
    owner_token = register_and_login(client, "history-owner@example.com")
    other_token = register_and_login(client, "history-other@example.com")

    created = client.post(
        "/api/v1/conversations",
        json={"title": "Private conversation"},
        headers=auth_headers(owner_token),
    )
    assert created.status_code == 201

    conversation_id = created.json()["id"]

    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=auth_headers(other_token),
    )

    assert response.status_code == 404


def test_get_conversation_messages_rejects_invalid_pagination(client):  # test-12
    token = register_and_login(client, "history-invalid@example.com")

    created = client.post(
        "/api/v1/conversations",
        json={"title": "Pagination validation"},
        headers=auth_headers(token),
    )
    assert created.status_code == 201

    conversation_id = created.json()["id"]

    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages?page=0",
        headers=auth_headers(token),
    )
    assert response.status_code == 422

    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages?page_size=101",
        headers=auth_headers(token),
    )
    assert response.status_code == 422


def test_customer_can_send_message(client):  # test-13
    token = register_and_login(client, "message_sender@example.com")

    conversation_response = client.post(
        "/api/v1/conversations",
        json={"title": "Message test"},
        headers=auth_headers(token),
    )
    assert conversation_response.status_code == 201

    conversation_id = conversation_response.json()["id"]

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Hello, support team!"},
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    data = response.json()
    assert data["conversation_id"] == conversation_id
    assert data["role"] == "customer"
    assert data["content"] == "Hello, support team!"
    assert data["sequence_number"] == 1
    assert data["token_count"] == 0


def test_customer_cannot_send_message_to_another_customers_conversation(
    client,
):  # test-14
    first_token = register_and_login(client, "first_customer@example.com")
    second_token = register_and_login(client, "second_customer@example.com")

    conversation_response = client.post(
        "/api/v1/conversations",
        json={"title": "Private conversation"},
        headers=auth_headers(first_token),
    )
    assert conversation_response.status_code == 201

    conversation_id = conversation_response.json()["id"]

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "I should not be able to send this."},
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404


def test_sending_blank_message_is_rejected(client):  # test-15
    token = register_and_login(client, "blank_message@example.com")

    conversation_response = client.post(
        "/api/v1/conversations",
        json={"title": "Blank message test"},
        headers=auth_headers(token),
    )
    assert conversation_response.status_code == 201

    conversation_id = conversation_response.json()["id"]

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "   "},
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_message_sequence_numbers_increase(client):  # test-16
    token = register_and_login(client, "sequence_test@example.com")

    conversation_response = client.post(
        "/api/v1/conversations",
        json={"title": "Sequence test"},
        headers=auth_headers(token),
    )
    assert conversation_response.status_code == 201

    conversation_id = conversation_response.json()["id"]
    headers = auth_headers(token)

    first_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "First message"},
        headers=headers,
    )
    second_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Second message"},
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["sequence_number"] == 1
    assert second_response.json()["sequence_number"] == 2


def test_sent_message_appears_in_conversation_history(client):  # test-17
    token = register_and_login(
        client,
        "history_integration@example.com",
    )
    headers = auth_headers(token)

    conversation_response = client.post(
        "/api/v1/conversations",
        json={"title": "History integration test"},
        headers=headers,
    )
    assert conversation_response.status_code == 201

    conversation_id = conversation_response.json()["id"]

    send_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "I need help with my account."},
        headers=headers,
    )
    assert send_response.status_code == 201

    history_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert history_response.status_code == 200

    history = history_response.json()

    assert history["total"] == 1
    assert history["items"][0]["content"] == ("I need help with my account.")
    assert history["items"][0]["role"] == "customer"
    assert history["items"][0]["sequence_number"] == 1


def test_customer_cannot_update_conversation_status(client):  # test-18
    token = register_and_login(
        client,
        "status-customer@example.com",
    )

    headers = auth_headers(token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Status permissions test"},
    )

    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
        json={"status": "resolved"},
    )

    assert update_response.status_code == 403


def test_invalid_conversation_status_is_rejected(client):  # test-19
    token = register_and_login(
        client,
        "invalid-status@example.com",
    )
    headers = auth_headers(token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Invalid status test"},
    )
    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
        json={"status": "not_a_real_status"},
    )

    assert update_response.status_code == 422


def test_invalid_conversation_priority_is_rejected(client):  # test-20
    token = register_and_login(
        client,
        "invalid-priority@example.com",
    )
    headers = auth_headers(token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Invalid priority test"},
    )
    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
        json={"priority": "super_urgent"},
    )

    assert update_response.status_code == 422


def test_support_agent_cannot_update_unassigned_conversation(client):  # test-21
    customer_token = register_and_login(
        client,
        "unassigned-customer@example.com",
    )
    customer_headers = auth_headers(customer_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Unassigned conversation test"},
    )
    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    support_email = "unassigned-support@example.com"
    support_token = register_and_login(client, support_email)

    # Promote the user to support without assigning the conversation.
    configure_support_agent(
        support_email=support_email,
        conversation_id=conversation_id,
        assign_conversation=False,
    )

    update_response = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        headers=auth_headers(support_token),
        json={"priority": "urgent"},
    )

    assert update_response.status_code == 404


def test_empty_conversation_update_is_rejected(client):  # test-22
    token = register_and_login(
        client,
        "empty-update@example.com",
    )
    headers = auth_headers(token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Empty update test"},
    )
    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    # An empty PATCH request must not change anything.
    update_response = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
        json={},
    )

    assert update_response.status_code == 422


def test_admin_can_update_accessible_conversation(client):  # test-23
    admin_email = "conversation-admin@example.com"
    admin_token = register_and_login(client, admin_email)

    set_user_role(admin_email, "admin")

    headers = auth_headers(admin_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Admin update test"},
    )
    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
        json={
            "status": "resolved",
            "priority": "urgent",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["status"] == "resolved"
    assert update_response.json()["priority"] == "urgent"


def test_customer_cannot_access_another_customers_assigned_conversation(
    client,
):  # test-24
    # Customer A creates a conversation.
    owner_token = register_and_login(
        client,
        "ownership-owner@example.com",
    )
    owner_headers = auth_headers(owner_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=owner_headers,
        json={"title": "Ownership protection test"},
    )
    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    # Customer B attempts to access Customer A's conversation.
    other_customer_token = register_and_login(
        client,
        "ownership-other@example.com",
    )
    other_customer_headers = auth_headers(other_customer_token)

    # Even if assigned_to_id matches Customer B, the customer role
    # must still be restricted to conversations they own.
    async def assign_conversation_to_other_customer():
        engine = create_async_engine(
            os.environ["TEST_DATABASE_URL"],
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with session_factory() as session:
                result = await session.execute(
                    select(User).where(User.email == "ownership-other@example.com")
                )
                other_customer = result.scalar_one()

                conversation_result = await session.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = conversation_result.scalar_one()
                conversation.assigned_to_id = other_customer.id

                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(assign_conversation_to_other_customer())

    # The customer must not be able to read the conversation's messages.
    history_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=other_customer_headers,
    )
    assert history_response.status_code == 404

    # The customer must not be able to modify the conversation either.
    update_response = client.patch(
        f"/api/v1/conversations/{conversation_id}",
        headers=other_customer_headers,
        json={"priority": "urgent"},
    )
    assert update_response.status_code == 404


def test_customer_list_excludes_another_customers_assigned_conversation(
    client,
):  # test-25
    owner_token = register_and_login(
        client,
        "list-owner@example.com",
    )
    owner_headers = auth_headers(owner_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=owner_headers,
        json={"title": "Private customer conversation"},
    )
    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    other_email = "list-other-customer@example.com"
    other_token = register_and_login(client, other_email)
    other_headers = auth_headers(other_token)

    async def assign_conversation_to_other_customer():
        engine = create_async_engine(
            os.environ["TEST_DATABASE_URL"],
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with session_factory() as session:
                user_result = await session.execute(
                    select(User).where(User.email == other_email)
                )
                other_user = user_result.scalar_one()

                conversation_result = await session.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = conversation_result.scalar_one()
                conversation.assigned_to_id = other_user.id

                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(assign_conversation_to_other_customer())

    list_response = client.get(
        "/api/v1/conversations",
        headers=other_headers,
    )

    assert list_response.status_code == 200

    visible_ids = [item["id"] for item in list_response.json()["items"]]
    assert conversation_id not in visible_ids


def test_customer_cannot_send_message_to_another_customers_assigned_conversation(
    client,
):  # test-26
    owner_token = register_and_login(
        client,
        "message-owner@example.com",
    )
    owner_headers = auth_headers(owner_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=owner_headers,
        json={"title": "Private message test"},
    )
    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    other_email = "message-other-customer@example.com"
    other_token = register_and_login(client, other_email)
    other_headers = auth_headers(other_token)

    async def assign_conversation_to_other_customer():
        engine = create_async_engine(
            os.environ["TEST_DATABASE_URL"],
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        try:
            async with session_factory() as session:
                user_result = await session.execute(
                    select(User).where(User.email == other_email)
                )
                other_user = user_result.scalar_one()

                conversation_result = await session.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = conversation_result.scalar_one()
                conversation.assigned_to_id = other_user.id

                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(assign_conversation_to_other_customer())

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=other_headers,
        json={"content": "I should not be able to send this."},
    )

    assert response.status_code == 404


def test_support_agent_list_excludes_unassigned_owned_conversation(client):  # test-27
    support_email = "support-list-test@example.com"
    support_token = register_and_login(client, support_email)
    headers = auth_headers(support_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "Unassigned owned conversation"},
    )
    assert create_response.status_code == 201

    conversation_id = create_response.json()["id"]

    # Promote the owner to support without assigning the conversation.
    set_user_role(support_email, "support")

    list_response = client.get(
        "/api/v1/conversations",
        headers=headers,
    )

    assert list_response.status_code == 200

    visible_ids = [item["id"] for item in list_response.json()["items"]]
    assert conversation_id not in visible_ids


def test_admin_can_assign_conversation_to_support_agent(client):  # test-28
    customer_token = register_and_login(
        client,
        "assignment-customer@example.com",
    )
    admin_token = register_and_login(
        client,
        "assignment-admin@example.com",
    )
    support_token = register_and_login(
        client,
        "assignment-support@example.com",
    )

    customer_headers = auth_headers(customer_token)
    admin_headers = auth_headers(admin_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Assignment test"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    # Promote the admin and support user to their intended roles.
    set_user_role("assignment-admin@example.com", "admin")
    set_user_role("assignment-support@example.com", "support")

    # Log in again after role changes in case role data is stored in the token.
    admin_token = register_and_login(
        client, "assignment-admin@example.com", register_flag=False
    )
    admin_headers = auth_headers(admin_token)

    # Get the support user's ID from the database.
    support_id = get_user_id("assignment-support@example.com")

    response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=admin_headers,
        json={"assigned_to_id": support_id},
    )

    assert response.status_code == 200
    assert response.json()["assigned_to_id"] == support_id


def test_admin_can_unassign_conversation(client):  # test-29
    customer_token = register_and_login(
        client,
        "unassign-customer@example.com",
    )
    admin_token = register_and_login(
        client,
        "unassign-admin@example.com",
    )
    support_token = register_and_login(
        client,
        "unassign-support@example.com",
    )

    customer_headers = auth_headers(customer_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Unassignment test"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    set_user_role("unassign-admin@example.com", "admin")
    set_user_role("unassign-support@example.com", "support")

    # Log in again after promoting the admin.
    admin_token = register_and_login(
        client,
        "unassign-admin@example.com",
        register_flag=False,
    )
    admin_headers = auth_headers(admin_token)

    support_id = get_user_id("unassign-support@example.com")

    # First assign the conversation.
    assign_response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=admin_headers,
        json={"assigned_to_id": support_id},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["assigned_to_id"] == support_id

    # Then unassign it explicitly.
    unassign_response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=admin_headers,
        json={"assigned_to_id": None},
    )

    assert unassign_response.status_code == 200
    assert unassign_response.json()["assigned_to_id"] is None


def test_customer_cannot_assign_conversation(client):
    customer_token = register_and_login(
        client,
        "customer-assignment-denied@example.com",
    )
    support_token = register_and_login(
        client,
        "support-assignment-target@example.com",
    )

    customer_headers = auth_headers(customer_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Customer assignment denial test"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    set_user_role(
        "support-assignment-target@example.com",
        "support",
    )
    support_id = get_user_id("support-assignment-target@example.com")

    response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=customer_headers,
        json={"assigned_to_id": support_id},
    )

    assert response.status_code == 403


def test_admin_can_assign_conversation_they_do_not_own(client):
    customer_token = register_and_login(
        client,
        "other-owner-assignment@example.com",
    )
    admin_token = register_and_login(
        client,
        "unrelated-admin-assignment@example.com",
    )
    register_and_login(
        client,
        "target-support-assignment@example.com",
    )

    customer_headers = auth_headers(customer_token)

    # The customer creates the conversation.
    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Another user's conversation"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    # Promote the other users to their intended roles.
    set_user_role(
        "unrelated-admin-assignment@example.com",
        "admin",
    )
    set_user_role(
        "target-support-assignment@example.com",
        "support",
    )

    # Log in again after promoting the admin.
    admin_token = register_and_login(
        client,
        "unrelated-admin-assignment@example.com",
        register_flag=False,
    )
    admin_headers = auth_headers(admin_token)

    support_id = get_user_id("target-support-assignment@example.com")

    # The admin is neither the owner nor the current assignee.
    response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=admin_headers,
        json={"assigned_to_id": support_id},
    )

    assert response.status_code == 200
    assert response.json()["assigned_to_id"] == support_id


def test_admin_cannot_assign_conversation_to_nonexistent_user(client):
    customer_token = register_and_login(
        client,
        "invalid-target-customer@example.com",
    )
    admin_token = register_and_login(
        client,
        "invalid-target-admin@example.com",
    )

    customer_headers = auth_headers(customer_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Invalid assignment target test"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    set_user_role(
        "invalid-target-admin@example.com",
        "admin",
    )

    admin_token = register_and_login(
        client,
        "invalid-target-admin@example.com",
        register_flag=False,
    )
    admin_headers = auth_headers(admin_token)

    response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=admin_headers,
        json={"assigned_to_id": "nonexistent-support-user-id"},
    )

    assert response.status_code == 422


def test_admin_cannot_assign_conversation_to_customer(client):
    customer_token = register_and_login(
        client,
        "target-role-owner@example.com",
    )
    admin_token = register_and_login(
        client,
        "target-role-admin@example.com",
    )
    target_token = register_and_login(
        client,
        "target-role-customer@example.com",
    )

    customer_headers = auth_headers(customer_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Invalid target role test"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    set_user_role(
        "target-role-admin@example.com",
        "admin",
    )

    admin_token = register_and_login(
        client,
        "target-role-admin@example.com",
        register_flag=False,
    )
    admin_headers = auth_headers(admin_token)

    # target-role-customer@example.com remains a customer.
    target_id = get_user_id("target-role-customer@example.com")

    response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=admin_headers,
        json={"assigned_to_id": target_id},
    )

    assert response.status_code == 422


def test_admin_cannot_assign_conversation_to_inactive_support_agent(client):
    customer_token = register_and_login(
        client,
        "inactive-target-owner@example.com",
    )
    admin_token = register_and_login(
        client,
        "inactive-target-admin@example.com",
    )
    register_and_login(
        client,
        "inactive-support-target@example.com",
    )

    customer_headers = auth_headers(customer_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Inactive support target test"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    set_user_role(
        "inactive-target-admin@example.com",
        "admin",
    )
    set_user_role(
        "inactive-support-target@example.com",
        "support",
    )
    set_user_active_status(
        "inactive-support-target@example.com",
        False,
    )

    admin_token = register_and_login(
        client,
        "inactive-target-admin@example.com",
        register_flag=False,
    )
    admin_headers = auth_headers(admin_token)

    inactive_support_id = get_user_id("inactive-support-target@example.com")

    response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=admin_headers,
        json={"assigned_to_id": inactive_support_id},
    )

    assert response.status_code == 422


def test_support_agent_cannot_assign_conversation(client):
    customer_token = register_and_login(
        client,
        "support-denial-owner@example.com",
    )
    support_token = register_and_login(
        client,
        "support-denial-agent@example.com",
    )
    register_and_login(
        client,
        "support-denial-target@example.com",
    )

    customer_headers = auth_headers(customer_token)

    # Customer creates the conversation.
    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Support assignment denial test"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    # Promote both users to support agents.
    set_user_role(
        "support-denial-agent@example.com",
        "support",
    )
    set_user_role(
        "support-denial-target@example.com",
        "support",
    )

    # Log in again after changing the role.
    support_token = register_and_login(
        client,
        "support-denial-agent@example.com",
        register_flag=False,
    )
    support_headers = auth_headers(support_token)

    target_id = get_user_id("support-denial-target@example.com")

    response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=support_headers,
        json={"assigned_to_id": target_id},
    )

    assert response.status_code == 403


def test_admin_assignment_requires_assigned_to_id(client):
    customer_token = register_and_login(
        client,
        "missing-field-owner@example.com",
    )
    admin_token = register_and_login(
        client,
        "missing-field-admin@example.com",
    )

    customer_headers = auth_headers(customer_token)

    create_response = client.post(
        "/api/v1/conversations",
        headers=customer_headers,
        json={"title": "Missing assignment field test"},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    set_user_role(
        "missing-field-admin@example.com",
        "admin",
    )

    admin_token = register_and_login(
        client,
        "missing-field-admin@example.com",
        register_flag=False,
    )
    admin_headers = auth_headers(admin_token)

    response = client.patch(
        f"/api/v1/conversations/{conversation_id}/assignment",
        headers=admin_headers,
        json={},
    )

    assert response.status_code == 422


def test_list_conversations_returns_empty_page_when_offset_exceeds_total(
    client,
):
    token = register_and_login(
        client,
        "pagination-empty@example.com",
    )
    headers = auth_headers(token)

    response = client.post(
        "/api/v1/conversations",
        json={"title": "Only ticket"},
        headers=headers,
    )
    assert response.status_code == 201

    response = client.get(
        "/api/v1/conversations?page=5&page_size=2",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["page"] == 5
    assert data["page_size"] == 2
    assert data["items"] == []


def test_get_conversation_messages_returns_empty_page_when_offset_exceeds_total(
    client,
):
    token = register_and_login(
        client,
        "history-empty@example.com",
    )
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/conversations",
        json={"title": "Empty history pagination"},
        headers=headers,
    )
    assert created.status_code == 201

    conversation_id = created.json()["id"]

    insert_test_messages(
        conversation_id,
        [
            {
                "role": "user",
                "content": "Only message",
                "sequence_number": 1,
            }
        ],
    )

    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages?page=5&page_size=2",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["page"] == 5
    assert data["page_size"] == 2
    assert data["items"] == []


def test_message_at_maximum_length_is_accepted(client):
    token = register_and_login(
        client,
        "message-max-length@example.com",
    )
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/conversations",
        json={"title": "Maximum length test"},
        headers=headers,
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "a" * 10_000},
        headers=headers,
    )

    assert response.status_code == 201
    assert len(response.json()["content"]) == 10_000


def test_message_over_maximum_length_is_rejected(client):
    token = register_and_login(
        client,
        "message-over-length@example.com",
    )
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/conversations",
        json={"title": "Over maximum length test"},
        headers=headers,
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "a" * 10_001},
        headers=headers,
    )

    assert response.status_code == 422
