# Configuration and troubleshooting

Settings load from `.env` in the working directory, with process environment
variables taking precedence. Start the API from the repository root when using
relative paths. Restart after changing settings or account credentials.

| Variable | Default | Purpose |
| --- | --- | --- |
| `FF_MODE` | `live` | `live` or synthetic `demo` |
| `FF_RELEASE_VERSION` | `OB55` | Game release header (`OB` plus 2–3 digits) |
| `FF_ACCOUNTS_FILE` | `config/accounts.json` | Private account file |
| `FF_DEFAULT_REGION` | `IND` | Default query region |
| `FF_API_KEY` | empty | Optional player endpoint key |
| `FF_TIMEOUT_SECONDS` | `15` | HTTP operation timeout, up to 120 seconds |
| `FF_CACHE_TTL_SECONDS` | `30` | Response cache TTL; 0 disables caching |
| `FF_RATE_LIMIT_PER_MINUTE` | `60` | Per-IP player request allowance |
| `FF_LOGIN_URL` | `https://loginbp.ggblueshark.com/MajorLogin` | Game session login |
| `FF_TOKEN_URL` | `https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant` | Guest OAuth endpoint |
| `FF_GUEST_REGISTER_URL` | `https://ffmconnect.live.gop.garenanow.com/oauth/guest/register` | Experimental one-account setup |
| `FF_UNITY_VERSION` | `2018.4.11f1` | Protocol header from community references |
| `FF_AES_KEY`, `FF_AES_IV` | community protocol constants | 16-byte UTF-8 transport values |
| `FF_GARENA_CLIENT_ID`, `FF_GARENA_CLIENT_SECRET` | community client constants | Guest OAuth client values |

The account file is a JSON object mapping uppercase region codes to a string
`uid` and `password`. Empty `{}` is valid but does not make live mode ready.
No account password is bundled. Do not use credentials copied from public repos.

Game login discovers the regional server URL; the API accepts HTTPS subdomains
of `freefiremobile.com`, on port 443, with no embedded credentials or path/query.
Redirects are disabled. A future legitimate domain change needs a reviewed
allowlist change in `freefire_api/client.py`.

## Experimental guest setup

`scripts/create_guest.py` provisions at most one guest per invocation. It does
not retry failed registration or expose an account-creation HTTP endpoint.
Credentials are saved in ignored `config/guest-pending.json` immediately after
guest registration, then moved into the configured accounts file only after game
registration and session login succeed. Existing accounts are never overwritten.
The configured accounts path is also used by this script; custom paths must be
kept outside source control by the operator.

The initial attempt on October 9, 2026 returned HTTP 404 before any guest UID was
issued. No guest account was created. Do not repeatedly create accounts to work
around an upstream restriction. If a pending file exists, inspect it locally and
resolve the existing account before another provisioning attempt.

## Troubleshooting

- **API does not start:** ensure `.venv` dependencies are installed, inspect the
  account JSON format, remove placeholders in live mode, and run from the project root.
- **503 REGION_NOT_CONFIGURED:** add an account for the requested region and restart.
- **502 UPSTREAM_AUTH_FAILED:** guest login credentials may be incorrect or expired;
  upstream endpoint/client settings may have changed. A player's public UID is not
  necessarily the guest login UID. Google/Facebook passwords cannot be used here.
- **502 UPSTREAM_PROTOCOL_ERROR:** verify the response schemas, AES settings and
  release headers. Merely incrementing OB does not update protobuf schemas.
- **404 in demo:** only `1234567890` in `IND` exists. Live mode requires a real UID.
- **Connection refused in Bruno:** start Uvicorn and use the correct environment port.
- **429 behind a reverse proxy:** configure trusted proxy handling in Uvicorn.
  Without it, the proxy address may be shared by all callers.
- **Stale data:** cache entries expire after `FF_CACHE_TTL_SECONDS`; set it to 0
  and restart for direct requests. Credential and session updates also require restart.

The API's timeout applies to individual HTTP operations. An uncached player
request can require OAuth, game login, the player call, and a refresh attempt;
its total duration can exceed one configured timeout.
