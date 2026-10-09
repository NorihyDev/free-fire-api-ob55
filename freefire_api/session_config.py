"""Load operator-owned game tokens; decoded JWT claims are only expiry hints."""

import base64
import json
import re
import time

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from freefire_api.settings import REGIONS, Settings


class SessionCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(min_length=1, max_length=16384)
    server_url: str
    expires_at: int | None = Field(default=None, gt=0, le=253402300799)

    @model_validator(mode="after")
    def validate_session(self):
        # Import locally to keep transport and configuration dependencies acyclic.
        from freefire_api.client import validate_server_url
        from freefire_api.errors import APIError

        try:
            self.server_url = validate_server_url(self.server_url)
        except APIError:
            raise ValueError("Invalid game server URL") from None
        token = self.token.get_secret_value()
        if not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
            raise ValueError("Provide only the ASCII bearer token without a Bearer prefix")
        if self.expires_at is None:
            try:
                parts = token.split(".")
                if len(parts) != 3:
                    raise ValueError("Not a JWT")
                payload = parts[1] + "=" * (-len(parts[1]) % 4)
                claims = json.loads(base64.urlsafe_b64decode(payload))
                expiry = claims["exp"]
                if type(expiry) is not int or not 0 < expiry <= 253402300799:
                    raise ValueError("Invalid JWT expiration")
                self.expires_at = expiry
            except (ValueError, KeyError, TypeError):
                raise ValueError(
                    "Provide expires_at as a Unix timestamp if the token has no JWT exp claim"
                ) from None
        return self

    def remaining_seconds(self) -> float:
        return self.expires_at - time.time()


def load_sessions(settings: Settings) -> dict[str, SessionCredential]:
    if settings.mode == "demo" or not settings.sessions_file.exists():
        return {}
    try:
        raw = json.loads(settings.sessions_file.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict) or any(key not in REGIONS for key in raw):
            raise ValueError("Unsupported region")
        return {region: SessionCredential.model_validate(value) for region, value in raw.items()}
    except (ValueError, OSError):
        raise RuntimeError(
            "Invalid sessions file. Check config/sessions.example.json; tokens were not logged."
        ) from None
