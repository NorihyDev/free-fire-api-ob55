import asyncio
import json
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from freefire_api.errors import APIError
from freefire_api.protocol.codec import decode, encode
from freefire_api.session_config import load_sessions
from freefire_api.settings import REGIONS, Settings


class Credential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uid: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    password: SecretStr = Field(min_length=1)


@dataclass
class Session:
    token: str = field(repr=False)
    server_url: str
    expires_at: float


def load_accounts(settings: Settings) -> dict[str, Credential]:
    if settings.mode == "demo" or not settings.accounts_file.exists():
        return {}
    try:
        raw = json.loads(settings.accounts_file.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict) or any(key not in REGIONS for key in raw):
            raise ValueError("Unsupported region")
        return {region: Credential.model_validate(value) for region, value in raw.items()}
    except (ValueError, OSError, ValidationError):
        # Never include pydantic errors: their input values may contain passwords.
        raise RuntimeError("Invalid accounts file. Check config/accounts.example.json.") from None


def validate_server_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise APIError(
            502, "UPSTREAM_PROTOCOL_ERROR", "Game login returned an invalid server URL."
        ) from exc
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or not host.endswith(".freefiremobile.com")
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise APIError(
            502, "UPSTREAM_PROTOCOL_ERROR", "Game login returned an unexpected server URL."
        )
    return value.rstrip("/")


class FreeFireClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient):
        self.settings = settings
        self.http = http
        self.accounts = (
            load_sessions(settings)
            if settings.auth_method == "session"
            else load_accounts(settings)
        )
        self.sessions: dict[str, Session] = {}
        self.locks = {region: asyncio.Lock() for region in REGIONS}

    def available_regions(self) -> list[str]:
        if self.settings.auth_method == "session":
            return sorted(
                region
                for region, credential in self.accounts.items()
                if credential.remaining_seconds() > 0
            )
        return sorted(self.accounts)

    def headers(self, token: str = "") -> dict:
        return {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; A063 Build/TKQ1.221220.001)",
            "Authorization": f"Bearer {token}".rstrip(),
            "ReleaseVersion": self.settings.release_version,
            "X-Unity-Version": self.settings.unity_version,
            "X-GA": "v1 1",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def encrypted(self, schema: str, data: dict) -> bytes:
        return encode(
            schema,
            data,
            self.settings.aes_key.get_secret_value().encode(),
            self.settings.aes_iv.get_secret_value().encode(),
        )

    async def post(self, url: str, **kwargs) -> httpx.Response:
        try:
            response = await self.http.post(url, **kwargs)
        except httpx.TimeoutException as exc:
            raise APIError(504, "UPSTREAM_TIMEOUT", "Game server did not respond in time.") from exc
        except httpx.RequestError as exc:
            raise APIError(502, "UPSTREAM_UNAVAILABLE", "Could not reach the game server.") from exc
        if response.status_code == 429:
            raise APIError(
                503, "UPSTREAM_RATE_LIMITED", "Game server rate limit reached; retry later."
            )
        if response.status_code >= 500:
            raise APIError(502, "UPSTREAM_UNAVAILABLE", "Game server is currently unavailable.")
        return response

    async def session(self, region: str, rejected: Session | None = None) -> Session:
        credential = self.accounts.get(region)
        if not credential:
            instruction = (
                "game session token"
                if self.settings.auth_method == "session"
                else "guest credentials"
            )
            filename = "sessions" if self.settings.auth_method == "session" else "accounts"
            raise APIError(
                503,
                "REGION_NOT_CONFIGURED",
                f"Add your own {instruction} for {region} to the {filename} file and restart.",
            )
        if self.settings.auth_method == "session":
            remaining = credential.remaining_seconds()
            if remaining <= 0:
                raise APIError(
                    503,
                    "SESSION_EXPIRED",
                    "Game session expired. Update your local token and restart.",
                )
            if rejected is not None:
                raise APIError(
                    503,
                    "SESSION_REJECTED",
                    "Game server rejected the session. Update your local token and restart.",
                )
            return Session(
                credential.token.get_secret_value(),
                credential.server_url,
                time.monotonic() + remaining,
            )
        async with self.locks[region]:
            current = self.sessions.get(region)
            if current and current is not rejected and current.expires_at > time.monotonic():
                return current
            response = await self.post(
                self.settings.token_url,
                data={
                    "uid": credential.uid,
                    "password": credential.password.get_secret_value(),
                    "response_type": "token",
                    "client_type": "2",
                    "client_id": self.settings.garena_client_id,
                    "client_secret": self.settings.garena_client_secret.get_secret_value(),
                },
                headers={"User-Agent": "GarenaMSDK/4.0.19P9(A063 ;Android 13;en;IN;)"},
            )
            if response.status_code != 200:
                raise APIError(
                    502, "UPSTREAM_AUTH_FAILED", "Guest login failed; check credentials."
                )
            try:
                auth = response.json()
                if (
                    not isinstance(auth, dict)
                    or not auth.get("access_token")
                    or not auth.get("open_id")
                ):
                    raise ValueError("Missing login fields")
            except ValueError as exc:
                raise APIError(
                    502, "UPSTREAM_AUTH_FAILED", "Guest login returned no token."
                ) from exc
            login = await self.post(
                self.settings.login_url,
                content=self.encrypted(
                    "MajorLogin",
                    {
                        "openid": auth["open_id"],
                        "logintoken": auth["access_token"],
                        "platform": "4",
                    },
                ),
                headers=self.headers(),
            )
            if login.status_code != 200:
                raise APIError(
                    502,
                    "UPSTREAM_AUTH_FAILED",
                    "Game login failed; check credentials and OB version.",
                )
            data = decode("MajorLogin", login.content)
            if not data.get("token") or not data.get("serverUrl"):
                raise APIError(502, "UPSTREAM_AUTH_FAILED", "Game login returned no session.")
            returned_region = data.get("lockRegion")
            if returned_region and returned_region.upper() != region:
                raise APIError(
                    502, "UPSTREAM_REGION_MISMATCH", "Guest account belongs to a different region."
                )
            session = Session(
                data["token"],
                validate_server_url(data["serverUrl"]),
                time.monotonic() + max(1, min(data.get("ttl") or 3600, 86400) - 60),
            )
            self.sessions[region] = session
            return session

    async def request(self, region: str, endpoint: str, schema: str, data: dict) -> dict:
        session = await self.session(region)
        content = self.encrypted(schema, data)
        for attempt in range(2):
            response = await self.post(
                session.server_url + endpoint, content=content, headers=self.headers(session.token)
            )
            if response.status_code in (401, 403):
                if attempt == 0:
                    session = await self.session(region, rejected=session)
                    continue
                raise APIError(
                    502, "UPSTREAM_AUTH_FAILED", "Game server rejected the refreshed session."
                )
            if response.status_code == 404:
                raise APIError(
                    404, "PLAYER_NOT_FOUND", "Player was not found in the selected region."
                )
            if response.status_code != 200:
                raise APIError(
                    502,
                    "UPSTREAM_REJECTED_REQUEST",
                    "Game server rejected the request; check OB settings.",
                )
            return decode(schema, response.content)
        raise RuntimeError("Unreachable request state")

    async def profile(self, uid: str, region: str, gallery: bool = False) -> dict:
        data = await self.request(
            region,
            "/GetPlayerPersonalShow",
            "PlayerPersonalShow",
            {
                "accountId": uid,
                "callSignSrc": 7,
                "needGalleryInfo": gallery,
            },
        )
        if not data.get("basicinfo"):
            raise APIError(404, "PLAYER_NOT_FOUND", "Player was not found in the selected region.")
        return data

    async def stats(self, uid: str, region: str, mode: str, match_type: str) -> dict:
        match_mode = {"career": 0, "normal": 1, "ranked": 2 if mode == "br" else 6}[match_type]
        payload = {"accountid": uid, "matchmode": match_mode}
        if mode == "cs":
            payload["gamemode"] = 15
        return await self.request(
            region,
            "/GetPlayerStats" if mode == "br" else "/GetPlayerTCStats",
            "PlayerStats" if mode == "br" else "PlayerCSStats",
            payload,
        )

    async def search(self, keyword: str, region: str) -> dict:
        return await self.request(
            region, "/FuzzySearchAccountByName", "SearchAccountByName", {"keyword": keyword}
        )
