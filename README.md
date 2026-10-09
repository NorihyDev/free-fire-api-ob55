# Free Fire API · OB55

An unofficial Python REST API for Free Fire player profiles, nickname search,
Battle Royale stats, and Clash Squad stats. Built with FastAPI, with interactive
OpenAPI documentation and a ready-to-open Bruno collection.

Inspired by [0xMe/FreeFire-Api](https://github.com/0xMe/FreeFire-Api), rebuilt with
async HTTP, validated inputs, consistent JSON errors, region-specific session
caching, one-time session refresh, bounded response caching, and optional API keys.

**Direct-session mode is now the default:** reuse a game session token you own and
call the player endpoints directly, without Garena guest token-grant, token-inspection
or MajorLogin requests. A valid game token is still required; this is not anonymous
access to authenticated game servers.

> **Verification status:** the local API and encrypted protocol flows are covered
> by automated tests. Demo mode works without credentials and returns clearly
> labelled synthetic data. Live OB55 access has **not** been verified with an owned
> account session. No owned game token has been supplied. The automatic guest
> registration attempt returned HTTP 404 on
> October 9, 2026. Configure your own session token and verify upstream settings
> before relying on live responses. Garena may change these unofficial endpoints.

## Start locally

Python 3.11 or newer is required. Run these commands from the repository root.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
Copy-Item config/sessions.example.json config/sessions.json
```

For an immediate Bruno test, set `FF_MODE=demo` in `.env`, then run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn freefire_api.main:app --host 127.0.0.1 --port 8000
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
cp config/sessions.example.json config/sessions.json
# Set FF_MODE=demo in .env for the first test.
.venv/bin/python -m uvicorn freefire_api.main:app --host 127.0.0.1 --port 8000
```

Open [Swagger UI](http://127.0.0.1:8000/docs),
[ReDoc](http://127.0.0.1:8000/redoc), or
[OpenAPI JSON](http://127.0.0.1:8000/openapi.json).

Demo player: **`1234567890`**, region **`IND`**, nickname **`DemoPlayer`**.
All demo stats filters use the same synthetic fixture for their mode. Unknown
demo UIDs return 404. Demo mode never contacts Garena.

## Use live data

1. Set `FF_MODE=live` and `FF_AUTH_METHOD=session` in `.env`.
2. Put an existing **game session JWT from your own account** and its matching
   regional game server URL in `config/sessions.json`.
3. Restart the API and request a known player's profile in the matching region.

Do not use a Garena OAuth access token here: that is a different token and normally
needs MajorLogin to obtain the game session. If you do not have a valid game token,
the linked TCP repository cannot create anonymous game access for you.

```json
{
  "IND": {
    "token": "YOUR_OWN_GAME_SESSION_JWT",
    "server_url": "https://client.ind.freefiremobile.com"
  }
}
```

Missing regions return `503 REGION_NOT_CONFIGURED`; live mode never substitutes
demo data. Expired or rejected sessions return `503 SESSION_EXPIRED` or
`503 SESSION_REJECTED`. Update your own token and restart; direct-session mode
does not attempt a Garena login to refresh it. Invalid configuration stops startup
with a sanitized error. `.env`, `config/sessions.json`, and `config/accounts.json`
are ignored by Git. Token claims are decoded only for expiry scheduling; the game
server verifies the token. For a token without a JWT `exp` claim, supply an explicit
`expires_at` Unix timestamp in the session entry.

### Optional older guest login

Set `FF_AUTH_METHOD=guest` to use the original guest OAuth + MajorLogin flow.
That mode contacts Garena authentication and requires your own guest credentials
in `config/accounts.json`:

```json
{
  "IND": {"uid": "YOUR_GUEST_LOGIN_UID", "password": "YOUR_GUEST_PASSWORD"}
}
```

An optional, experimental single-account setup script is available:

```powershell
.\.venv\Scripts\python.exe scripts/create_guest.py --region IND
```

It refuses to overwrite accounts or create another account while a pending guest
exists. It verifies game login before marking configuration complete. Registration
returned 404 in this environment. This setup script calls Garena auth and is not
part of direct-session mode. See [configuration](docs/configuration.md).

## Endpoints

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Process health and current mode |
| GET | `/ready` | Local configuration readiness; no upstream probe |
| GET | `/api/v1/regions` | Recognized region codes and configuration status |
| GET | `/api/v1/players/{uid}/profile` | Basic profile, guild, pet, social and equipment fields |
| GET | `/api/v1/players/{uid}/stats` | BR or CS statistics |
| GET | `/api/v1/players/search` | Nickname search |

```bash
curl "http://127.0.0.1:8000/api/v1/players/1234567890/profile?region=IND"
curl "http://127.0.0.1:8000/api/v1/players/1234567890/stats?region=IND&mode=cs&match_type=ranked"
curl "http://127.0.0.1:8000/api/v1/players/search?keyword=Demo&region=IND"
```

PowerShell also supports `Invoke-RestMethod` for these URLs. If `FF_API_KEY` is set,
send `X-API-Key` on player endpoints. Health, regions and API documentation are public.

Successful player responses contain `data` and `meta`:

```json
{
  "data": {"basicinfo": {"accountid": "1234567890", "nickname": "DemoPlayer"}},
  "meta": {
    "region": "IND", "release_version": "OB55", "source": "demo",
    "cached": false, "request_id": "example-request-id"
  }
}
```

The example is abbreviated. Profile fields retain the bundled protobuf names.
UIDs and other protobuf 64-bit integers are JSON strings to avoid precision loss.
Fields absent from the upstream message are omitted; unavailable data is not invented.

## Test with Bruno

1. In Bruno choose **Open Collection** and select this repository's `bruno/` folder.
2. Select **Local Demo** for demo mode or **Local Live** for a configured game session.
3. Set `uid`, `region`, `keyword`, and `apiKey` for your instance.
4. Run health, profile, BR stats, CS stats, search and the validation requests.

The collection includes response assertions. `Local Live` needs a real target UID
before profile/stat requests pass; a valid game session must be configured on the
API server. See [Bruno instructions](docs/bruno.md).

## Develop and deploy

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe scripts/compile_protocol.py
```

Runtime uses the checked-in protobuf descriptor; no `protoc` installation is required.
GitHub Actions runs tests and lint on Python 3.11, 3.12 and 3.14. Docker and Compose
configuration are included. See [deployment](docs/deployment.md).

The public GitHub repository contains source code; it does not itself host the API.
The local server URL works while the process is running on your computer.

## Documentation and sources

- [API reference and errors](docs/api.md)
- [Configuration and troubleshooting](docs/configuration.md)
- [Protocol research and verification limits](docs/research.md)
- [Direct sessions and the TeeXez TCP reference](docs/sessions.md)
- [Deployment](docs/deployment.md)
- [Bruno collection](docs/bruno.md)
- [Third-party attribution](THIRD_PARTY_NOTICES.md)

Garena published [OB55 patch notes](https://ff.garena.com/en/article/1712/) on
September 10, 2026. The release header is configurable because game protocol
compatibility depends on more than the OB label. This project is not affiliated
with or endorsed by Garena. Licensed under [GPL-3.0-only](LICENSE).
