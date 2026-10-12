import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
import app.models  # Registers all model tables


async def main():
    database_url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(database_url)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        print("Test database tables created successfully.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
