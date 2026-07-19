import pytest
from pydantic import ValidationError

from conftest import ResourceConfig, _redis_database, validate_test_resources
from src.core.config import settings


def resources(database_url: str, redis_url: str) -> ResourceConfig:
    return ResourceConfig(
        database_url=database_url,
        redis_url=redis_url,
        _env_file=None,
    )


def test_requires_explicit_test_resource_urls(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_REDIS_URL", raising=False)

    with pytest.raises(ValidationError):
        ResourceConfig(_env_file=None)


def test_accepts_explicitly_separated_test_resources():
    validate_test_resources(
        resources(
            "postgresql+asyncpg://admin:password@localhost:5432/fastapi_test",
            "redis://localhost:6379/15",
        )
    )


def test_rejects_postgres_database_query_override():
    with pytest.raises(ValueError, match="must not include query parameters"):
        validate_test_resources(
            resources(
                "postgresql+asyncpg://localhost/fastapi_test?database=application",
                "redis://localhost:6379/15",
            )
        )


@pytest.mark.parametrize("database_name", ["devdb", "customer_test"])
def test_rejects_local_postgres_without_reserved_database_name(database_name):
    with pytest.raises(ValueError, match="reserved database 'fastapi_test'"):
        validate_test_resources(
            resources(
                f"postgresql+asyncpg://admin:password@localhost:5432/{database_name}",
                "redis://localhost:6379/15",
            )
        )


def test_rejects_application_postgres_even_with_test_name(monkeypatch):
    monkeypatch.setattr(settings, "postgres_db", "fastapi_test")

    with pytest.raises(ValueError, match="application database"):
        validate_test_resources(
            resources(
                "postgresql+asyncpg://admin:password@localhost:5432/fastapi_test",
                "redis://localhost:6379/15",
            )
        )


@pytest.mark.parametrize(
    "redis_url", ["redis://localhost:6379/0", "redis://localhost:6379/14"]
)
def test_rejects_redis_database_not_reserved_for_tests(redis_url):
    with pytest.raises(ValueError, match="reserved test database 15"):
        validate_test_resources(
            resources(
                "postgresql+asyncpg://admin:password@localhost:5432/fastapi_test",
                redis_url,
            )
        )


def test_rejects_redis_database_query_override():
    with pytest.raises(ValueError, match="must not include query parameters"):
        _redis_database("redis://localhost:6379/15?db=0")


def test_rejects_application_redis_database(monkeypatch):
    monkeypatch.setattr(settings, "redis_db", 15)

    with pytest.raises(ValueError, match="application Redis database"):
        validate_test_resources(
            resources(
                "postgresql+asyncpg://admin:password@localhost:5432/fastapi_test",
                "redis://localhost:6379/15",
            )
        )
