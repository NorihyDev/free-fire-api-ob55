# Free Fire API · OB55

An unofficial Python REST API for Free Fire player profiles, nickname search,
Battle Royale stats, and Clash Squad stats. Built with FastAPI, with interactive
OpenAPI documentation and a ready-to-open Bruno collection.

Inspired by [0xMe/FreeFire-Api](https://github.com/0xMe/FreeFire-Api), rebuilt with
async HTTP, validated inputs, consistent JSON errors, region-specific session
caching, one-time session refresh, bounded response caching, and optional API keys.

> **Verification status:** the local API and encrypted protocol flows are covered
> by automated tests. Demo mode works without credentials and returns clearly
> labelled synthetic data. Live OB55 access has **not** been verified with an owned
> guest account. The automatic guest registration attempt returned HTTP 404 on
> October 9, 2026. Configure your own guest credentials and verify upstream settings
> before relying on live responses. Garena may change these unofficial endpoints.

## Start locally

Python 3.11 or newer is required. Run these commands from the repository root.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
Copy-Item config/accounts.example.json config/accounts.json
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
cp config/accounts.example.json config/accounts.json
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

1. Set `FF_MODE=live` in `.env`.
2. Put the guest login UID and password of accounts you own in
   `config/accounts.json`, using the format below. These are guest credentials,
   not a Google/Facebook password. The login UID may differ from a player UID.
3. Add only configured regions; remove the placeholder example entry.
4. Restart the API and request a known player's profile in the matching region.

```json
{
  "IND": {"uid": "YOUR_GUEST_LOGIN_UID", "password": "YOUR_GUEST_PASSWORD"},
  "BR": {"uid": "YOUR_BRAZIL_GUEST_LOGIN_UID", "password": "YOUR_GUEST_PASSWORD"}
}
```

Missing regions return `503 REGION_NOT_CONFIGURED`; live mode never substitutes
demo data. Invalid credential configuration stops startup with a sanitized error.
`.env` and `config/accounts.json` are ignored by Git.

An optional, experimental single-account setup script is available:

```powershell
.\.venv\Scripts\python.exe scripts/create_guest.py --region IND
```

It refuses to overwrite accounts or create another account while a pending guest
exists. It verifies game login before marking configuration complete. Registration
currently returned 404 in this environment; existing owned credentials are the
recommended setup. See [configuration](docs/configuration.md).

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
2. Select **Local Demo** for demo mode or **Local Live** for credentialed live mode.
3. Set `uid`, `region`, `keyword`, and `apiKey` for your instance.
4. Run health, profile, BR stats, CS stats, search and the validation requests.

The collection includes response assertions. `Local Live` needs a real target UID
before profile/stat requests pass. See [Bruno instructions](docs/bruno.md).

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
- [Deployment](docs/deployment.md)
- [Bruno collection](docs/bruno.md)
- [Third-party attribution](THIRD_PARTY_NOTICES.md)

Garena published [OB55 patch notes](https://ff.garena.com/en/article/1712/) on
September 10, 2026. The release header is configurable because game protocol
compatibility depends on more than the OB label. This project is not affiliated
with or endorsed by Garena. Licensed under [GPL-3.0-only](LICENSE).
