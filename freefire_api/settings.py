from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REGIONS = ("IND", "SG", "RU", "ID", "TW", "US", "VN", "TH", "ME", "PK", "CIS", "BR", "BD")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FF_", env_file=".env", extra="ignore")
    mode: Literal["live", "demo"] = "live"
    auth_method: Literal["session", "guest"] = "session"
    release_version: str = Field(default="OB55", pattern=r"^OB[0-9]{2,3}$")
    accounts_file: Path = Path("config/accounts.json")
    sessions_file: Path = Path("config/sessions.json")
    default_region: str = "IND"
    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = Field(default=15, gt=0, le=120)
    cache_ttl_seconds: float = Field(default=30, ge=0, le=3600)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)
    login_url: str = "https://loginbp.ggblueshark.com/MajorLogin"
    token_url: str = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    guest_register_url: str = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/register"
    unity_version: str = "2018.4.11f1"
    aes_key: SecretStr = SecretStr("Yg&tc%DEuh6%Zc^8")
    aes_iv: SecretStr = SecretStr("6oyZDr22E3ychjM%")
    garena_client_id: str = "100067"
    garena_client_secret: SecretStr = SecretStr(
        "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
    )

    @field_validator("default_region")
    @classmethod
    def valid_region(cls, value: str) -> str:
        value = value.upper()
        if value not in REGIONS:
            raise ValueError("Unknown Free Fire region")
        return value

    @field_validator("aes_key", "aes_iv")
    @classmethod
    def valid_crypto(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode()) != 16:
            raise ValueError("Protocol AES key and IV must be 16 bytes")
        return value

    @field_validator("login_url", "token_url", "guest_register_url")
    @classmethod
    def valid_login_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Login URL must be HTTPS without embedded credentials")
        return value
