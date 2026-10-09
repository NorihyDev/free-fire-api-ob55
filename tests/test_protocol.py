import asyncio
import json

import httpx
import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from google.protobuf import json_format

from freefire_api.client import FreeFireClient, validate_server_url
from freefire_api.errors import APIError
from freefire_api.protocol.codec import decode, encode, message_type
from freefire_api.settings import Settings


def serialized(schema, data):
    message = message_type(schema, "response")()
    json_format.ParseDict(data, message)
    return message.SerializeToString()


def unpack(schema, request, settings):
    body = unpad(
        AES.new(
            settings.aes_key.get_secret_value().encode(),
            AES.MODE_CBC,
            settings.aes_iv.get_secret_value().encode(),
        ).decrypt(request.content),
        16,
    )
    message = message_type(schema, "request")()
    message.ParseFromString(body)
    return message


def test_encrypted_uint64_preserves_precision():
    value = "18446744073709551615"
    key, iv = b"1234567890123456", b"abcdefghijklmnop"
    body = encode("PlayerStats", {"accountid": value, "matchmode": 2}, key, iv)
    message = message_type("PlayerStats", "request")()
    message.ParseFromString(unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(body), 16))
    assert message.accountid == int(value)
    response = serialized("PlayerStats", {"solostats": {"accountid": value}})
    assert decode("PlayerStats", response)["solostats"]["accountid"] == value


@pytest.mark.parametrize("body", [b"", b"<html>unavailable</html>"])
def test_protocol_errors(body):
    with pytest.raises(APIError) as caught:
        decode("PlayerStats", body)
    assert caught.value.status == 502


@pytest.mark.parametrize(
    "url",
    [
        "http://client.ind.freefiremobile.com",
        "https://localhost",
        "https://freefiremobile.com.attacker.example",
        "https://127.0.0.1",
        "https://secret@client.ind.freefiremobile.com",
        "https://client.ind.freefiremobile.com:444",
        "https://client.ind.freefiremobile.com:invalid",
    ],
)
def test_discovered_server_url_is_restricted(url):
    with pytest.raises(APIError):
        validate_server_url(url)


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "accounts.json"
    path.write_text(json.dumps({"IND": {"uid": "12345", "password": "own-password"}}))
    return Settings(_env_file=None, accounts_file=path, mode="live")


async def test_live_flow_refresh_and_cs_wire_mapping(config):
    calls = {"oauth": 0, "login": 0, "profile": 0}

    def handler(request):
        assert "Host" not in dict(request.headers)  # httpx supplies the actual target host.
        if request.url.path.endswith("/grant"):
            calls["oauth"] += 1
            return httpx.Response(200, json={"access_token": "oauth-secret", "open_id": "openid"})
        assert request.headers["ReleaseVersion"] == "OB55"
        if request.url.path == "/MajorLogin":
            calls["login"] += 1
            assert unpack("MajorLogin", request, config).logintoken == "oauth-secret"
            return httpx.Response(
                200,
                content=serialized(
                    "MajorLogin",
                    {
                        "token": f"session-{calls['login']}",
                        "ttl": 3600,
                        "lockRegion": "IND",
                        "serverUrl": "https://client.ind.freefiremobile.com",
                    },
                ),
            )
        if request.url.path == "/GetPlayerPersonalShow":
            calls["profile"] += 1
            assert request.url.host == "client.ind.freefiremobile.com"
            payload = unpack("PlayerPersonalShow", request, config)
            assert payload.accountId == 1234567890
            assert payload.needGalleryInfo is True
            if calls["profile"] == 1:
                return httpx.Response(401)
            return httpx.Response(
                200,
                content=serialized(
                    "PlayerPersonalShow",
                    {
                        "basicinfo": {"accountid": "1234567890", "nickname": "FixturePlayer"},
                    },
                ),
            )
        if request.url.path == "/GetPlayerTCStats":
            payload = unpack("PlayerCSStats", request, config)
            assert payload.gamemode == 15
            assert payload.matchmode == 6
            return httpx.Response(
                200,
                content=serialized(
                    "PlayerCSStats",
                    {
                        "csstats": {"accountid": "1234567890", "wins": 3},
                    },
                ),
            )
        raise AssertionError(f"Unexpected endpoint {request.url.path}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = FreeFireClient(config, http)
        data = await client.profile("1234567890", "IND", True)
        assert data["basicinfo"]["nickname"] == "FixturePlayer"
        await client.stats("1234567890", "IND", "cs", "ranked")
        assert calls == {"oauth": 2, "login": 2, "profile": 2}


async def test_concurrent_session_login_happens_once(config):
    count = 0

    async def handler(request):
        nonlocal count
        if request.url.path.endswith("/grant"):
            count += 1
            await asyncio.sleep(0.01)
            return httpx.Response(200, json={"access_token": "token", "open_id": "openid"})
        return httpx.Response(
            200,
            content=serialized(
                "MajorLogin",
                {
                    "token": "session",
                    "serverUrl": "https://client.ind.freefiremobile.com",
                    "ttl": 3600,
                },
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = FreeFireClient(config, http)
        await asyncio.gather(*(client.session("IND") for _ in range(10)))
        assert count == 1


@pytest.mark.parametrize("status,expected", [(429, 503), (500, 502), (302, 502), (403, 502)])
async def test_upstream_status_errors(config, status, expected):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status))
    ) as http:
        with pytest.raises(APIError) as caught:
            await FreeFireClient(config, http).profile("1234567890", "IND")
        assert caught.value.status == expected


async def test_timeout_maps_to_gateway_timeout(config):
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(APIError) as caught:
            await FreeFireClient(config, http).profile("1234567890", "IND")
        assert caught.value.status == 504
