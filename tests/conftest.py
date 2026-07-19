from urllib.parse import urlsplit

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

import src.core.database as db_module
from src.core.config import settings
from src.core.database import get_db, insert_super_user
from src.core.redis import close_redis, init_redis
from src.main import app


class ResourceConfig(BaseSettings):
    database_url: str = Field(validation_alias="TEST_DATABASE_URL")
    redis_url: str = Field(validation_alias="TEST_REDIS_URL")

    model_config = SettingsConfigDict(
        env_file=".env.test",
        env_ignore_empty=True,
        extra="ignore",
        populate_by_name=True,
    )


def _redis_database(url: str) -> int:
    parsed = urlsplit(url)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise ValueError("TEST_REDIS_URL must be a valid redis:// or rediss:// URL")
    if parsed.query:
        raise ValueError("TEST_REDIS_URL must not include query parameters")

    database = parsed.path.removeprefix("/")
    if not database.isdigit() or "/" in database:
        raise ValueError("TEST_REDIS_URL must include one numeric Redis database")
    return int(database)


def validate_test_resources(resources: ResourceConfig) -> None:
    test_database = make_url(resources.database_url)
    application_database = make_url(settings.async_database_url)

    if test_database.drivername != "postgresql+asyncpg":
        raise ValueError("TEST_DATABASE_URL must use postgresql+asyncpg")
    if test_database.query:
        raise ValueError("TEST_DATABASE_URL must not include query parameters")
    if test_database.database != "fastapi_test":
        raise ValueError("TEST_DATABASE_URL must use the reserved database 'fastapi_test'")
    if test_database.database == application_database.database:
        raise ValueError("TEST_DATABASE_URL must not use the application database")

    test_redis_database = _redis_database(resources.redis_url)
    application_redis_database = _redis_database(settings.redis_url)
    if test_redis_database != 15:
        raise ValueError("TEST_REDIS_URL must use the reserved test database 15")
    if test_redis_database == application_redis_database:
        raise ValueError("TEST_REDIS_URL must not use the application Redis database")


@pytest.fixture(scope="session")
def test_resources() -> ResourceConfig:
    resources = ResourceConfig()
    validate_test_resources(resources)
    return resources


@pytest_asyncio.fixture(scope="session")
async def test_engine(test_resources):
    # Independent engine for tests using Postgres
    # NullPool helps avoiding loop/concurrency issues with asyncpg in tests
    engine = create_async_engine(
        test_resources.database_url, echo=False, poolclass=NullPool
    )

    # IMPORTANT: Initialize the database module so AsyncSessionLocal is not None
    db_module.engine = engine
    db_module.AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        # Ensure clean state for session-scoped tests
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    # Initialize default roles and actions
    from src.core.database import insert_default_actions, insert_default_roles
    async with db_module.AsyncSessionLocal() as session:
        await insert_default_actions(session)
        await insert_default_roles(session)
        await session.commit()

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seed_db(db_session):
    await insert_super_user(db_session)
    await db_session.commit()


@pytest_asyncio.fixture
async def setup_redis(test_resources):
    await init_redis(test_resources.redis_url)
    from src.core.redis import redis_client

    if redis_client:
        await redis_client.flushdb()
    yield
    await close_redis()


@pytest_asyncio.fixture
async def db_session(test_engine):
    async with db_module.AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session, seed_db, setup_redis):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Desactivar OTel para tests para evitar errores de conexión a alloy
    settings.otel_enabled = False

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        yield client

    app.dependency_overrides.clear()
