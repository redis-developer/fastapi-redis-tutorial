import datetime
import json
import os.path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from app.main import app


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
        with mock.patch('httpx.AsyncClient.get') as mock_get:
            with mock.patch('httpx.Response') as mock_response:
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


client = TestClient(app)


def test_api(mock_bitcoin_api: mock.MagicMock):
    client.post(REFRESH_URL)
    res = client.get(URL)
    summary = res.json()

    assert res.status_code == 200

    for field in EXPECTED_FIELDS:
        assert field in summary
