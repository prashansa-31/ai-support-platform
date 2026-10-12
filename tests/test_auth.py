from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.models.user import User
import jwt
import asyncio
import os


def register_and_login_with_role(client, email, role):  # helper fn
    password = "StrongPassword123!"

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )
    assert registration.status_code == 201

    # Assign the role directly in the test database.
    # Public registration must never let users choose their role.
    async def set_user_role():
        engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
        try:
            Session = async_sessionmaker(
                engine,
                expire_on_commit=False,
            )
            async with Session() as session:
                await session.execute(
                    update(User).where(User.email == email).values(role=role)
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(set_user_role())

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200

    return login_response.json()["access_token"]


def test_register_user_success(client):  # test-1
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "StrongPassword123!",
            "full_name": "New User",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert data["role"] == "customer"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data
    assert "password" not in data


def test_register_duplicate_email(client):  # test-2
    payload = {
        "email": "duplicate@example.com",
        "password": "StrongPassword123!",
        "full_name": "Duplicate User",
    }

    first_response = client.post("/api/v1/auth/register", json=payload)
    second_response = client.post("/api/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_register_invalid_email(client):  # test-3
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "StrongPassword123!",
            "full_name": "Invalid User",
        },
    )

    assert response.status_code == 422


def test_register_short_password(client):  # test-4
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "shortpassword@example.com",
            "password": "short",
            "full_name": "Short Password",
        },
    )

    assert response.status_code == 422


def test_login_success(client):  # test-5
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "loginuser@example.com",
            "password": "StrongPassword123!",
            "full_name": "Login User",
        },
    )
    assert registration.status_code == 201

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "loginuser@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):  # test-6
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpass@example.com",
            "password": "StrongPassword123!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_unknown_email(client):  # test-7
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_get_current_user_success(client):  # test-8
    # Register a user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "meuser@example.com",
            "password": "StrongPassword123!",
            "full_name": "My Profile",
        },
    )

    # Log in to get an access token
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "meuser@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Request the current user's profile
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "meuser@example.com"
    assert data["full_name"] == "My Profile"
    assert data["role"] == "customer"
    assert "hashed_password" not in data
    assert "password" not in data


def test_get_current_user_without_token(client):  # test-9
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == ("Invalid or missing authentication token")


def test_get_current_user_with_invalid_token(client):  # test-10
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == ("Invalid or missing authentication token")


def test_get_current_user_inactive_account(client):  # test-11
    # Register and log in
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "inactive@example.com",
            "password": "StrongPassword123!",
        },
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive@example.com",
            "password": "StrongPassword123!",
        },
    )
    token = login_response.json()["access_token"]

    # Deactivate the account in the test database
    async def deactivate_user():
        engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
        try:
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                await session.execute(
                    update(User)
                    .where(User.email == "inactive@example.com")
                    .values(is_active=False)
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(deactivate_user())

    # The previously issued token must no longer grant access
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "This account is inactive"


def test_get_current_user_with_expired_token(client):  # test-12
    expired_token = jwt.encode(
        {
            "sub": "nonexistent-user",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == ("Invalid or missing authentication token")


def test_customer_cannot_access_admin_endpoint(client):  # test-13
    token = register_and_login_with_role(
        client, "customer_role@example.com", "customer"
    )

    response = client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_support_agent_cannot_access_admin_endpoint(client):  # test-14
    token = register_and_login_with_role(
        client, "support_role@example.com", "support_agent"
    )

    response = client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_admin_can_access_admin_endpoint(client):  # test-15
    token = register_and_login_with_role(client, "admin_role@example.com", "admin")

    response = client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert response.json()["message"] == "Admin access granted"


def test_admin_endpoint_requires_authentication(client):  # test-16
    response = client.get("/api/v1/auth/admin-check")

    assert response.status_code == 401


def test_customer_cannot_access_support_endpoint(client):  # test-17
    token = register_and_login_with_role(
        client, "support_customer@example.com", "customer"
    )

    response = client.get(
        "/api/v1/auth/support-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_support_agent_can_access_support_endpoint(client):  # test-18
    token = register_and_login_with_role(
        client, "support_agent@example.com", "support_agent"
    )

    response = client.get(
        "/api/v1/auth/support-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "support_agent"
    assert response.json()["message"] == "Support access granted"


def test_admin_can_access_support_endpoint(client):  # test-19
    token = register_and_login_with_role(client, "support_admin@example.com", "admin")

    response = client.get(
        "/api/v1/auth/support-check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
