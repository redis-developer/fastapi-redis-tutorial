import json

import pytest
from aioredis import Redis
from httpx import AsyncClient

from app.main import get_cache_key


@pytest.mark.asyncio
async def test_speedtest(client: AsyncClient):
    res = await client.get('/speedtest')
    json = res.json()

    assert res.status_code == 200

    for field in ('ping_ms', 'download_mbps', 'upload_mbps'):
        assert field in json


@pytest.mark.asyncio
async def test_speedtest_cache(client: AsyncClient, redis: Redis):
    # prime the cache
    await client.get('/speedtest')

    cached = await redis.get(get_cache_key())
    assert cached is not None
    data = json.loads(cached)

    for field in ('ping_ms', 'download_mbps', 'upload_mbps'):
        assert field in data
