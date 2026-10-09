# API reference

Base URL: `http://127.0.0.1:8000`. Machine-readable specification: `/openapi.json`.
Interactive documentation: `/docs` and `/redoc`.

## Common behavior

- Player routes require `X-API-Key` only when the instance sets `FF_API_KEY`.
- `region` defaults to `FF_DEFAULT_REGION` (`IND`) and is case insensitive.
- Recognized codes: `IND`, `SG`, `RU`, `ID`, `TW`, `US`, `VN`, `TH`, `ME`, `PK`,
  `CIS`, `BR`, `BD`. Recognition does not prove upstream availability. Guest
  credentials must belong to the requested region.
- UIDs must be positive decimal uint64 strings (`1` through `18446744073709551615`).
  Use strings in JavaScript clients.
- Player requests are limited to 60 per minute per client IP by default.
  Cached responses also count. System/docs routes do not count.
- Success: `{"data": {...}, "meta": {...}}`. Metadata includes `region`,
  `release_version`, `source` (`live` or `demo`), `cached`, and `request_id`.
- Every response has an `X-Request-ID`. Responses set `Cache-Control: no-store`;
  the API maintains its own bounded, 30-second in-process cache.

## GET /api/v1/players/{uid}/profile

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `uid` | path string | required | Target player UID |
| `region` | query string | `IND` | Regional game server |
| `gallery` | query boolean | `false` | Request additional gallery fields |

The decoded protobuf can contain `basicinfo`, `profileinfo`, `clanbasicinfo`,
`captainbasicinfo`, `petinfo`, `socialinfo` and other fields. Presence depends on
the player and game response. `gallery=true` requests data but does not guarantee
that the server returns it. `callSignSrc` is fixed at 7 (PersonalShowView).
This API does not infer a ban status from absent fields.

## GET /api/v1/players/{uid}/stats

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `uid` | path string | required | Target player UID |
| `region` | query string | `IND` | Regional game server |
| `mode` | `br` or `cs` | `br` | Battle Royale or Clash Squad |
| `match_type` | `career`, `normal`, `ranked` | `career` | Stats filter |

BR data uses `solostats`, `duostats`, `quadstats`; CS uses `csstats`.
Present fields can include `gamesplayed`, `wins`, `kills` and `detailedstats`.
The API returns game values without inventing derived ratios. Empty or missing
stats do not prove the player is absent. A 404 is returned only when the upstream
returns 404; profile absence is separately detected by missing `basicinfo`.

## GET /api/v1/players/search

`keyword` is required, trimmed and must contain 3–50 characters. `region` is optional.
`data.infos` contains decoded account records when present. The game may omit
`infos` for an empty result; callers should treat omitted `infos` as an empty list.
Search is scoped to the regional session, with no automatic global fan-out.

## System routes

`GET /health` returns process status, mode and protocol release header. It does not
test game connectivity.

`GET /ready` returns 200 when at least one live credential is configured or when
demo mode is enabled; otherwise 503. It reports `configured_regions` and
`upstream_verified: false`. That field refers to this endpoint's check, which never
contacts Garena. A region can be configured while its credentials are invalid.

`GET /api/v1/regions` lists codes and a `configured` flag for each.

## Errors

```json
{
  "error": {
    "code": "REGION_NOT_CONFIGURED",
    "message": "Add your guest credentials for IND to the local accounts file and restart."
  },
  "request_id": "example-request-id"
}
```

Validation errors may include a `details` array of field locations and messages.
Passwords, session tokens and raw game responses are never included in errors.

| HTTP | Code | Action |
| --- | --- | --- |
| 401 | `INVALID_API_KEY` | Set the correct `X-API-Key` |
| 404 | `PLAYER_NOT_FOUND` | Verify UID and region |
| 422 | `VALIDATION_ERROR`, `INVALID_UID`, `INVALID_REGION`, `INVALID_KEYWORD` | Fix input |
| 429 | `RATE_LIMITED` | Wait; `Retry-After: 60` |
| 502 | `UPSTREAM_AUTH_FAILED` | Verify guest credentials, token/login endpoints and protocol settings |
| 502 | `UPSTREAM_REGION_MISMATCH` | Put the account under its correct region |
| 502 | `UPSTREAM_UNAVAILABLE` | Retry later; check connectivity |
| 502 | `UPSTREAM_REJECTED_REQUEST` | Check OB/protocol settings |
| 502 | `UPSTREAM_EMPTY_RESPONSE`, `UPSTREAM_PROTOCOL_ERROR` | Check response schemas/settings |
| 503 | `REGION_NOT_CONFIGURED` | Configure the region and restart |
| 503 | `UPSTREAM_RATE_LIMITED` | Wait; `Retry-After: 60` |
| 504 | `UPSTREAM_TIMEOUT` | Retry later |
| 500 | `INTERNAL_ERROR` | Investigate using the request ID |

Game 401/403 triggers one session refresh. Authentication failures after that
are returned as 502. No retry loop runs for timeouts, rate limits or other failures.

## Legacy routes

These are deprecated adapters for the original repository's route names. They
use the new `data`/`meta` envelope, so they are not response-shape compatible.

| Original route | Parameters |
| --- | --- |
| `/get_player_personal_show` | `uid`, `server`, `need_gallery_info` |
| `/get_player_stats` | `uid`, `server`, `gamemode=br\|cs`, `matchmode=CAREER\|NORMAL\|RANKED` |
| `/get_search_account_by_keyword` | `keyword`, `server` |

Unrecognized extra query parameters are ignored by FastAPI. This implementation
does not expose blacklist/spark request flags or account mutation endpoints.
