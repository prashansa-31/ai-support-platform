import asyncio
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.user import User


def register_and_login(client, email: str, register_flag: bool = True) -> str:
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
        assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def set_user_role(email: str, role: str) -> None:
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


def get_user_id(email: str) -> str:
    async def fetch_user_id() -> str:
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

    return asyncio.run(fetch_user_id())


def test_admin_users_endpoint_requires_authentication(client):
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401


def test_customer_cannot_access_admin_endpoints(client):
    customer_token = register_and_login(client, "customer-admin-test@example.com")
    headers = auth_headers(customer_token)

    get_response = client.get("/api/v1/admin/users", headers=headers)
    assert get_response.status_code == 403

    patch_response = client.patch(
        "/api/v1/admin/users/any-user-id",
        headers=headers,
        json={"role": "support"},
    )
    assert patch_response.status_code == 403


def test_support_agent_cannot_access_admin_endpoints(client):
    support_email = "support-admin-test@example.com"
    support_token = register_and_login(client, support_email)
    set_user_role(support_email, "support")
    support_token = register_and_login(client, support_email, register_flag=False)
    headers = auth_headers(support_token)

    response = client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 403


def test_admin_can_list_users(client):
    admin_email = "admin-list@example.com"
    admin_token = register_and_login(client, admin_email)
    set_user_role(admin_email, "admin")
    admin_token = register_and_login(client, admin_email, register_flag=False)
    headers = auth_headers(admin_token)

    register_and_login(client, "user-one@example.com")
    register_and_login(client, "user-two@example.com")

    response = client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


def test_admin_can_filter_users_by_role(client):
    admin_email = "admin-filter@example.com"
    admin_token = register_and_login(client, admin_email)
    set_user_role(admin_email, "admin")
    admin_token = register_and_login(client, admin_email, register_flag=False)
    headers = auth_headers(admin_token)

    support_email = "agent-to-filter@example.com"
    register_and_login(client, support_email)
    set_user_role(support_email, "support")

    register_and_login(client, "customer-filter@example.com")

    # Filter for role=support
    response = client.get("/api/v1/admin/users?role=support", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert all(user["role"] == "support" for user in data["items"])
    assert any(user["email"] == support_email for user in data["items"])


def test_admin_can_promote_customer_to_support_agent(client):
    admin_email = "admin-promoter@example.com"
    admin_token = register_and_login(client, admin_email)
    set_user_role(admin_email, "admin")
    admin_token = register_and_login(client, admin_email, register_flag=False)
    headers = auth_headers(admin_token)

    target_email = "customer-to-promote@example.com"
    register_and_login(client, target_email)
    target_id = get_user_id(target_email)

    patch_response = client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=headers,
        json={"role": "support"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["role"] == "support"
    assert patch_response.json()["id"] == target_id


def test_admin_can_deactivate_and_activate_agent(client):
    admin_email = "admin-activator@example.com"
    admin_token = register_and_login(client, admin_email)
    set_user_role(admin_email, "admin")
    admin_token = register_and_login(client, admin_email, register_flag=False)
    headers = auth_headers(admin_token)

    target_email = "agent-to-toggle@example.com"
    register_and_login(client, target_email)
    set_user_role(target_email, "support")
    target_id = get_user_id(target_email)

    # Deactivate agent
    deactivate_resp = client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    # Reactivate agent
    activate_resp = client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=headers,
        json={"is_active": True},
    )
    assert activate_resp.status_code == 200
    assert activate_resp.json()["is_active"] is True


def test_admin_cannot_deactivate_themselves(client):
    admin_email = "self-admin@example.com"
    admin_token = register_and_login(client, admin_email)
    set_user_role(admin_email, "admin")
    admin_token = register_and_login(client, admin_email, register_flag=False)
    headers = auth_headers(admin_token)
    admin_id = get_user_id(admin_email)

    response = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert "cannot deactivate their own account" in response.json()["detail"]


def test_admin_cannot_demote_themselves(client):
    admin_email = "self-demote-admin@example.com"
    admin_token = register_and_login(client, admin_email)
    set_user_role(admin_email, "admin")
    admin_token = register_and_login(client, admin_email, register_flag=False)
    headers = auth_headers(admin_token)
    admin_id = get_user_id(admin_email)

    response = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers=headers,
        json={"role": "customer"},
    )
    assert response.status_code == 400
    assert "cannot change their own role" in response.json()["detail"]


def test_admin_update_nonexistent_user_returns_404(client):
    admin_email = "admin-404-test@example.com"
    admin_token = register_and_login(client, admin_email)
    set_user_role(admin_email, "admin")
    admin_token = register_and_login(client, admin_email, register_flag=False)
    headers = auth_headers(admin_token)

    response = client.patch(
        "/api/v1/admin/users/nonexistent-id",
        headers=headers,
        json={"role": "support"},
    )
    assert response.status_code == 404


def test_admin_update_with_empty_payload_returns_422(client):
    admin_email = "admin-empty-payload@example.com"
    admin_token = register_and_login(client, admin_email)
    set_user_role(admin_email, "admin")
    admin_token = register_and_login(client, admin_email, register_flag=False)
    headers = auth_headers(admin_token)

    target_email = "target-empty@example.com"
    register_and_login(client, target_email)
    target_id = get_user_id(target_email)

    response = client.patch(
        f"/api/v1/admin/users/{target_id}",
        headers=headers,
        json={},
    )
    assert response.status_code == 422
