import asyncio
from typing import Generator

import aioredis
import pytest
from httpx import AsyncClient

from app.main import app
from app.main import config


@pytest.fixture(scope='function')
async def client():
    async with AsyncClient(app=app, base_url='http://test') as ac:
        yield ac


@pytest.fixture(scope='module')
def redis() -> Generator:
    yield aioredis.from_url(config.redis_url, decode_responses=True)


@pytest.fixture(scope='session')
def event_loop(request):
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
