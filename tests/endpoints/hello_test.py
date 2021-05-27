from fastapi.testclient import TestClient


def test_root(client: TestClient):
    res = client.get('/')

    assert res.status_code == 200
    assert res.json()['hello'] == 'world'
