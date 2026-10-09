# Protocol research

Reviewed October 9, 2026. Sources distinguish official game-release information
from community reverse-engineered protocol details.

| Source | What it establishes | Limitation |
| --- | --- | --- |
| [Garena OB55 patch notes](https://ff.garena.com/en/article/1712/) | Official OB55 announcement dated September 10, 2026; BR/CS game changes | Does not document a public player-data REST API or these protobuf schemas |
| [0xMe/FreeFire-Api](https://github.com/0xMe/FreeFire-Api) | Original Python guest login, encrypted player requests, and BR/CS/search route design | Old release settings, hardcoded profile host, inconsistent timeouts; no live verification for this project |
| [rifancorteza/ffapis](https://github.com/rifancorteza/ffapis) | GPL-3.0 protobuf files, configurable OB headers and corresponding protocol request fields | Community implementation; its own prior live-test claims do not verify this API |
| [ffapis configuration](https://github.com/rifancorteza/ffapis/blob/main/docs/configuration.md) | Client identifiers, guest OAuth endpoint, AES interoperability values | Values can change independently of OB |
| [FastAPI documentation](https://fastapi.tiangolo.com/tutorial/bigger-applications/) | Router dependencies and generated API documentation | Framework reference, not game protocol evidence |
| [Bruno documentation](https://docs.usebruno.com/) | Portable request collections and response assertions | Client tooling reference |

## Implemented flow

1. Read an operator-owned guest login for the requested region.
2. Request a Garena guest OAuth token using form encoding.
3. Serialize and AES-CBC/PKCS#7 encrypt the MajorLogin protobuf request.
4. Decode the binary login response and validate its regional server URL.
5. Send encrypted player protobuf requests with the session token and release headers.
6. Decode protobuf responses to JSON, preserving uint64 values as strings.

Requests use the regional URL discovered during login rather than a hardcoded
Indian host. Session login is serialized per region and cached with a TTL.
Server 401/403 causes one refresh; refresh is never an unlimited loop.

Protocol request mapping:

| REST operation | Upstream operation | Important wire values |
| --- | --- | --- |
| Profile | `GetPlayerPersonalShow` | UID field 1; call-sign source 7; gallery flag |
| Search | `FuzzySearchAccountByName` | Keyword field 1 |
| BR stats | `GetPlayerStats` | Career 0, normal 1, ranked 2 |
| CS stats | `GetPlayerTCStats` | Game mode 15; career 0, normal 1, ranked 6 |

The bundled schemas retain existing community fields. Unknown protobuf fields
are ignored during JSON decoding, so newly added OB55 fields may be absent until
the schemas are updated from verified evidence.

## Verification boundaries

Automated tests exercise encrypted uint64 requests, guest/game login, discovered
regional hosts, CS ranked mapping, concurrent login, session refresh, timeout and
HTTP errors through a controlled HTTP transport. They also exercise real FastAPI
routes, OpenAPI, authentication, validation, response caching, and demo fixtures.

The local demo server and Bruno collection can be exercised without game accounts.
These checks do not establish live Garena connectivity. The single guest creation
attempt returned HTTP 404 before issuing an account. Live player results therefore
remain unverified until the operator configures an owned guest account.

This project provides player data retrieval. It does not offer mass account
creation, automated profile likes, friend mutations, or gameplay modifications.
