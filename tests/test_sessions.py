import base64
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from freefire_api.client import FreeFireClient
from freefire_api.errors import APIError
from freefire_api.main import create_app
from freefire_api.protocol.codec import message_type
from freefire_api.settings import Settings


def jwt(expiry):
    claims = base64.urlsafe_b64encode(json.dumps({"exp": expiry}).encode()).decode().rstrip("=")
    return f"e30.{claims}.local-test-signature"


def configure(tmp_path, credential=None):
    path = tmp_path / "sessions.json"
    path.write_text(
        json.dumps(
            {
                "IND": credential
                or {
                    "token": jwt(int(time.time()) + 3600),
                    "server_url": "https://client.ind.freefiremobile.com",
                }
            }
        ),
        encoding="utf-8",
    )
    return Settings(_env_file=None, mode="live", auth_method="session", sessions_file=path)


async def test_direct_session_profile_makes_only_the_player_request(tmp_path):
    config = configure(tmp_path)
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.url.host == "client.ind.freefiremobile.com"
        assert request.url.path == "/GetPlayerPersonalShow"
        assert request.headers["Authorization"].startswith("Bearer e30.")
        message = message_type("PlayerPersonalShow", "response")()
        message.basicinfo.accountid = 1234567890
        message.basicinfo.nickname = "TransportFixture"
        return httpx.Response(200, content=message.SerializeToString())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = FreeFireClient(config, http)
        result = await client.profile("1234567890", "IND")
        assert result["basicinfo"]["accountid"] == "1234567890"
        assert calls == ["/GetPlayerPersonalShow"]


@pytest.mark.parametrize("status", [401, 403])
async def test_rejected_session_does_not_contact_auth_or_retry(tmp_path, status):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = FreeFireClient(configure(tmp_path), http)
        with pytest.raises(APIError) as caught:
            await client.profile("1234567890", "IND")
        assert caught.value.code == "SESSION_REJECTED"
        assert caught.value.status == 503
        assert calls == ["/GetPlayerPersonalShow"]


async def test_expired_session_makes_no_network_calls(tmp_path):
    config = configure(
        tmp_path,
        {
            "token": jwt(int(time.time()) - 60),
            "server_url": "https://client.ind.freefiremobile.com",
        },
    )

    def unexpected_request(request):
        raise AssertionError("Expired token must not cause a network request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected_request)) as http:
        client = FreeFireClient(config, http)
        with pytest.raises(APIError) as caught:
            await client.profile("1234567890", "IND")
        assert caught.value.code == "SESSION_EXPIRED"
        assert client.available_regions() == []
    with TestClient(create_app(config)) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["configured_regions"] == ["IND"]
        assert response.json()["available_regions"] == []


def test_explicit_expiry_supports_opaque_token(tmp_path):
    config = configure(
        tmp_path,
        {
            "token": "opaque-owned-token",
            "expires_at": int(time.time()) + 600,
            "server_url": "https://client.ind.freefiremobile.com/",
        },
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/ready").status_code == 200
        assert client.app.state.client.accounts["IND"].server_url.endswith(".com")


@pytest.mark.parametrize(
    "credential",
    [
        {"token": "hidden-secret-token", "server_url": "https://client.ind.freefiremobile.com"},
        {
            "token": "hidden-secret-token",
            "server_url": "http://127.0.0.1",
            "expires_at": 2000000000,
        },
        {
            "token": "hidden-secret-token",
            "server_url": "https://client.ind.freefiremobile.com:invalid",
            "expires_at": 2000000000,
        },
        {
            "token": "Bearer hidden-secret-token",
            "server_url": "https://client.ind.freefiremobile.com",
            "expires_at": 2000000000,
        },
        {
            "token": "hidden-secret-token",
            "server_url": "https://client.ind.freefiremobile.com",
            "expires_at": 10**400,
        },
    ],
)
def test_session_config_errors_do_not_expose_tokens(tmp_path, credential):
    config = configure(tmp_path, credential)
    with pytest.raises(RuntimeError) as caught, TestClient(create_app(config)):
        pass
    assert "hidden-secret-token" not in str(caught.value)


def test_default_live_method_is_session_and_missing_token_is_clear(tmp_path):
    config = Settings(_env_file=None, sessions_file=tmp_path / "missing.json")
    assert config.auth_method == "session"
    with TestClient(create_app(config)) as client:
        assert client.get("/ready").status_code == 503
        response = client.get("/api/v1/players/1234567890/profile")
        assert response.status_code == 503
        assert "session token" in response.json()["error"]["message"]
        assert response.json()["error"]["code"] == "REGION_NOT_CONFIGURED"
