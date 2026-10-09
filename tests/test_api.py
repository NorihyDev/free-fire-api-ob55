import json

import pytest
from fastapi.testclient import TestClient

from freefire_api.main import create_app
from freefire_api.settings import Settings


def settings(**kwargs):
    return Settings(_env_file=None, mode="demo", **kwargs)


def test_demo_profile_cache_metadata_and_precision():
    with TestClient(create_app(settings())) as client:
        first = client.get("/api/v1/players/1234567890/profile?region=ind")
        second = client.get("/api/v1/players/1234567890/profile?region=IND")
        assert first.status_code == second.status_code == 200
        body = first.json()
        assert body["data"]["basicinfo"]["accountid"] == "1234567890"
        assert body["meta"]["source"] == "demo"
        assert body["meta"]["cached"] is False
        assert second.json()["meta"]["cached"] is True
        assert first.headers["X-Request-ID"] == body["meta"]["request_id"]
        assert body["meta"]["request_id"] != second.json()["meta"]["request_id"]


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/players/0/profile",
        "/api/v1/players/abc/profile",
        "/api/v1/players/18446744073709551616/profile",
        "/api/v1/players/1234567890/profile?region=NOPE",
        "/api/v1/players/1234567890/profile?gallery=invalid",
        "/api/v1/players/1234567890/stats?mode=invalid",
        "/api/v1/players/1234567890/stats?match_type=invalid",
        "/api/v1/players/search?keyword=ab",
        "/api/v1/players/search?keyword=%20%20%20",
        "/get_player_stats",
        "/get_player_stats?uid=-3",
    ],
)
def test_invalid_requests_have_consistent_errors(url):
    with TestClient(create_app(settings())) as client:
        response = client.get(url)
        assert response.status_code == 422
        assert response.json()["error"]["code"]
        assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_api_key_and_rate_limit():
    with TestClient(create_app(settings(api_key="private-key", rate_limit_per_minute=1))) as client:
        url = "/api/v1/players/1234567890/profile"
        assert client.get(url).status_code == 401
        assert client.get(url, headers={"X-API-Key": "private-key"}).status_code == 200
        response = client.get(url, headers={"X-API-Key": "private-key"})
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"
        assert client.get("/health").status_code == 200


def test_stats_search_and_legacy_routes():
    with TestClient(create_app(settings())) as client:
        for mode, field in [("br", "solostats"), ("cs", "csstats")]:
            response = client.get(f"/api/v1/players/1234567890/stats?mode={mode}&match_type=ranked")
            assert field in response.json()["data"]
        assert len(client.get("/api/v1/players/search?keyword=Demo").json()["data"]["infos"]) == 1
        assert client.get("/api/v1/players/search?keyword=missing").json()["data"]["infos"] == []
        assert client.get("/get_player_personal_show?uid=1234567890").status_code == 200
        assert (
            client.get("/get_player_stats?uid=1234567890&gamemode=cs&matchmode=RANKED").status_code
            == 200
        )
        assert client.get("/get_search_account_by_keyword?keyword=Demo").status_code == 200
        assert client.get("/api/v1/players/999/profile").status_code == 404


def test_live_without_credentials_does_not_fall_back_to_demo(tmp_path):
    config = Settings(
        _env_file=None, mode="live", auth_method="guest", accounts_file=tmp_path / "missing.json"
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        response = client.get("/api/v1/players/1234567890/profile")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "REGION_NOT_CONFIGURED"


def test_invalid_account_configuration_does_not_expose_secrets(tmp_path):
    path = tmp_path / "accounts.json"
    path.write_text(json.dumps({"IND": {"uid": "bad", "password": "hidden-secret"}}))
    config = Settings(_env_file=None, mode="live", auth_method="guest", accounts_file=path)
    with pytest.raises(RuntimeError) as caught, TestClient(create_app(config)):
        pass
    assert "hidden-secret" not in str(caught.value)


def test_docs_and_openapi_describe_security_and_errors():
    with TestClient(create_app(settings())) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        schema = client.get("/openapi.json").json()
        operation = schema["paths"]["/api/v1/players/{uid}/profile"]["get"]
        assert "X-API-Key" == schema["components"]["securitySchemes"]["APIKeyHeader"]["name"]
        assert "503" in operation["responses"]
        assert schema["paths"]["/get_player_stats"]["get"]["deprecated"] is True
