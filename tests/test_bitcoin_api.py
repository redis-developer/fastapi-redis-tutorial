import pytest
from aioredis import Redis
from httpx import AsyncClient


REFRESH_URL = '/refresh'
URL = '/is-bitcoin-lit'
EXPECTED_FIELDS = (
    'lit', 'time', 'mean_of_means_sentiment',
    'mean_of_means_price',
)


@pytest.mark.asyncio
async def test_api(client: AsyncClient):
    await client.get(REFRESH_URL)
    res = await client.get(URL)
    summary = res.json()

    assert res.status_code == 200

    for field in EXPECTED_FIELDS:
        assert field in summary


@pytest.mark.asyncio
async def test_api_timeseries(client: AsyncClient, redis: Redis):
    await client.get(REFRESH_URL)
    data = await client.get(URL)
    summary = data.json()

    for field in EXPECTED_FIELDS:
        assert field in summary
