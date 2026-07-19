import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter
from src.core.config import settings

# Global redis client
redis_client: redis.Redis | None = None


async def init_redis(url: str | None = None):
    global redis_client
    redis_client = redis.from_url(
        url or settings.redis_url, encoding="utf-8", decode_responses=True
    )
    await FastAPILimiter.init(redis_client)


async def close_redis():
    if redis_client:
        await redis_client.aclose()


async def is_token_blacklisted(jti: str) -> bool:
    if redis_client:
        return await redis_client.exists(f"blacklist:{jti}") > 0
    return False


async def blacklist_token(jti: str, expire_seconds: int):
    if redis_client:
        await redis_client.setex(f"blacklist:{jti}", expire_seconds, "true")
