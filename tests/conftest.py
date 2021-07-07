import asyncio
from typing import Generator

import aioredis
import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient

from app.main import app
from app.main import config
from app.main import initialize_redis
from app.main import Keys
from app.main import make_keys

TEST_PREFIX = 'test:is-bitcoin-lit'


@pytest.fixture(scope='module')
def redis() -> Generator:
    yield aioredis.from_url(config.redis_url, decode_responses=True)


@pytest.fixture(scope='session')
def event_loop(request):
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def keys(redis: aioredis.Redis):
    def make_test_keys():
        return Keys(TEST_PREFIX)
    app.dependency_overrides[make_keys] = make_test_keys
    keys = make_test_keys()

    yield keys

    # Cleanup any test keys the test run created
    keys = await redis.keys(f'{TEST_PREFIX}*')
    if keys:
        await redis.delete(*keys)


@pytest.fixture(scope='function')
async def client(keys):
    async with AsyncClient(app=app, base_url='http://test') as client, \
            LifespanManager(app):
        yield client


@pytest.fixture(scope='function', autouse=True)
@pytest.mark.asyncio
async def setup_redis(request, keys):
    await initialize_redis(keys)
