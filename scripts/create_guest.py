"""Provision one dedicated guest account; keep all credentials in ignored local files."""

import argparse
import asyncio
import hashlib
import hmac
import json
import secrets
from pathlib import Path
from urllib.parse import urlencode

import httpx

from freefire_api.client import FreeFireClient
from freefire_api.errors import APIError
from freefire_api.settings import REGIONS, Settings


async def create(region: str, nickname: str):
    settings = Settings(mode="live", auth_method="guest")
    target = settings.accounts_file
    pending = Path("config/guest-pending.json")
    if target.exists() and json.loads(target.read_text(encoding="utf-8-sig")):
        raise RuntimeError("Accounts file is already configured; refusing to overwrite it.")
    if pending.exists():
        raise RuntimeError("A pending guest already exists. Resolve it before creating another.")
    async with httpx.AsyncClient(timeout=settings.timeout_seconds, follow_redirects=False) as http:
        client = FreeFireClient(settings, http)
        password = hashlib.sha256(secrets.token_bytes(32)).hexdigest().upper()
        form = urlencode(
            {
                "password": password,
                "client_type": "2",
                "source": "2",
                "app_id": settings.garena_client_id,
            }
        )
        signature = hmac.new(
            settings.garena_client_secret.get_secret_value().encode(), form.encode(), hashlib.sha256
        ).hexdigest()
        response = await client.post(
            settings.guest_register_url,
            content=form,
            headers={
                "Authorization": f"Signature {signature}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "GarenaMSDK/4.0.19P9(A063 ;Android 13;en;IN;)",
            },
        )
        if response.status_code != 200:
            raise RuntimeError(f"Guest registration refused (HTTP {response.status_code}).")
        try:
            uid = str(response.json()["uid"])
        except (ValueError, KeyError, TypeError):
            raise RuntimeError("Guest registration returned no UID.") from None
        if not uid.isascii() or not uid.isdecimal():
            raise RuntimeError("Guest registration returned an invalid UID.")
        credential = {"uid": uid, "password": password}
        pending.parent.mkdir(parents=True, exist_ok=True)
        with pending.open("x", encoding="utf-8") as file:
            json.dump({"region": region, "credential": credential}, file, indent=2)
        print("Guest created. Pending credentials saved locally; completing game registration.")
        auth_response = await client.post(
            settings.token_url,
            data={
                **credential,
                "response_type": "token",
                "client_type": "2",
                "client_id": settings.garena_client_id,
                "client_secret": settings.garena_client_secret.get_secret_value(),
            },
        )
        if auth_response.status_code != 200:
            raise RuntimeError(f"Guest token refused (HTTP {auth_response.status_code}).")
        try:
            auth = auth_response.json()
            token, openid = auth["access_token"], auth["open_id"]
        except (ValueError, KeyError, TypeError):
            raise RuntimeError("Guest token response was invalid.") from None
        mask = bytes(
            [
                0,
                0,
                0,
                2,
                0,
                1,
                7,
                0,
                0,
                0,
                0,
                0,
                2,
                0,
                1,
                7,
                0,
                0,
                0,
                0,
                0,
                2,
                0,
                1,
                7,
                0,
                0,
                0,
                0,
                0,
                2,
                0,
            ]
        )
        masked_openid = bytes(
            value ^ mask[index % len(mask)] ^ 48 for index, value in enumerate(openid.encode())
        )
        payload = {
            "nickname": nickname,
            "access_token": token,
            "openid": openid,
            "field_5": 102000007,
            "platform": 4,
            "field_7": 1,
            "field_13": 1,
            "region": region,
            "field_16": 1,
        }
        # ParseDict expects protobuf bytes fields as base64 strings.
        import base64

        payload["field_14"] = base64.b64encode(masked_openid).decode()
        registration = await client.post(
            settings.login_url.rsplit("/", 1)[0] + "/MajorRegister",
            content=client.encrypted("MajorRegister", payload),
            headers=client.headers(token),
        )
        if registration.status_code != 200:
            raise RuntimeError(
                f"Game registration refused (HTTP {registration.status_code}). "
                "Pending credentials remain in config/guest-pending.json. Do not recreate accounts."
            )
        # HTTP 200 is not sufficient: verify the new account can actually log in.
        from freefire_api.client import Credential

        client.accounts[region] = Credential.model_validate(credential)
        await client.session(region)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({region: credential}, indent=2) + "\n", encoding="utf-8")
        pending.unlink()
        print(f"Guest login verified. Credentials saved to {target}; no secrets were printed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", choices=REGIONS, default="IND")
    parser.add_argument("--nickname", default="ApiOB55" + secrets.token_hex(2))
    args = parser.parse_args()
    if not 3 <= len(args.nickname) <= 12:
        parser.error("Nickname must be 3-12 characters.")
    try:
        asyncio.run(create(args.region, args.nickname))
    except (APIError, RuntimeError, httpx.HTTPError) as exc:
        print(str(exc))
        raise SystemExit(1) from None
