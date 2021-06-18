from datetime import datetime

import pytest
from aioredis import Redis
from httpx import AsyncClient

from app.main import SUMMARY_KEY
from app.main import TIME_FORMAT_STRING

URL = '/is-bitcoin-lit'
SENTICRYPT_FIELDS = ('time', 'mean_sentiment')


@pytest.fixture
def summary_key():
    time = datetime.now().strftime(TIME_FORMAT_STRING)
    yield SUMMARY_KEY.format(time=time)


@pytest.mark.asyncio
async def test_api(client: AsyncClient):
    res = await client.get(URL)
    summary = res.json()

    assert res.status_code == 200

    for field in SENTICRYPT_FIELDS:
        assert field in summary


@pytest.mark.asyncio
async def test_api_cache(client: AsyncClient, redis: Redis, summary_key):
    # prime the cache
    await client.get(URL)

    summary = await redis.hgetall(summary_key)
    assert summary is not None

    for field in SENTICRYPT_FIELDS:
        assert field in summary


@pytest.mark.asyncio
async def test_api_timeseries(client: AsyncClient, redis: Redis):
    data = await client.get(URL)
    summary = data.json()

    for field in SENTICRYPT_FIELDS:
        assert field in summary
