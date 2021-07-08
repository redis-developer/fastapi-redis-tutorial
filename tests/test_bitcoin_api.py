import datetime
import json
import os.path
from unittest import mock

import pytest
from aioredis import Redis
from httpx import AsyncClient


REFRESH_URL = '/refresh'
URL = '/is-bitcoin-lit'
EXPECTED_FIELDS = (
    'hourly_average_of_averages',
    'sentiment_direction',
    'price_direction',
)
JSON_FIXTURE = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'fixtures',
    'sentiment_response.json',
)


@pytest.fixture
def mock_bitcoin_api():
    with mock.patch('app.main.now') as mock_utcnow:
        with mock.patch('requests.get') as mock_get:
            with mock.patch('requests.Response') as mock_response:
                mock_utcnow.return_value = datetime.datetime(
                    2021, 7, 7, 10, 30, 0, 0,  # 2020-07-07 10:30:00 UTC
                )

                # Mock out Response.json()
                m = mock.MagicMock()
                with open(JSON_FIXTURE) as f:
                    m.return_value = json.loads(f.read())
                mock_response.json = m

                # Make get() return our fake Response.
                mock_get.return_value = mock_response

                yield mock_get


@pytest.mark.asyncio
async def test_api(client: AsyncClient, mock_bitcoin_api: mock.MagicMock):
    await client.post(REFRESH_URL)
    res = await client.get(URL)
    summary = res.json()

    assert res.status_code == 200

    for field in EXPECTED_FIELDS:
        assert field in summary


@pytest.mark.asyncio
async def test_api_timeseries(
    client: AsyncClient, redis: Redis,
    mock_bitcoin_api: mock.MagicMock
):
    await client.post(REFRESH_URL)
    data = await client.get(URL)
    summary = data.json()

    for field in EXPECTED_FIELDS:
        assert field in summary
