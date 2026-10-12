import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.session import get_db
from app.main import app
from app.models import Conversation, Message, User


@pytest.fixture
def client():
    database_url = os.environ.get("TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    if not database_url.endswith("/ai_support_test"):
        pytest.fail(
            "TEST_DATABASE_URL must point to the dedicated ai_support_test database"
        )

    # Prevent async database connections from being reused across event loops.
    engine = create_async_engine(database_url, poolclass=NullPool)

    TestSessionLocal = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )

    async def override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def clean_database():
        async with TestSessionLocal() as session:
            await session.execute(delete(Message))
            await session.execute(delete(Conversation))
            await session.execute(delete(User))
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db

    try:
        asyncio.run(clean_database())

        with TestClient(app) as test_client:
            yield test_client

    finally:
        app.dependency_overrides.pop(get_db, None)

        try:
            asyncio.run(clean_database())
        finally:
            asyncio.run(engine.dispose())
