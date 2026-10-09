# Bruno testing

Open the `bruno/` folder as a collection in [Bruno](https://www.usebruno.com/).
No import or generated Postman file is required. The collection uses text `.bru`
files with request-level assertions.

## Environments

| Variable | Local Demo | Local Live |
| --- | --- | --- |
| `baseUrl` | `http://127.0.0.1:8000` | same; change for a deployed instance |
| `uid` | `1234567890` | placeholder; set to a real player UID |
| `region` | `IND` | set to a configured region |
| `keyword` | `Demo` | set to a real nickname fragment |
| `apiKey` | empty | set if `FF_API_KEY` is configured |
| `expectedSource` | `demo` | `live` |

Do not put guest credentials in Bruno requests. They belong on the API server.
For a private API key, create a **Private** environment (`Private.bru` is ignored
by Git) or use Bruno's secret variable support. Keep public environment files
free of secrets.

Start the API first, choose the matching environment, and run requests in order:
health, readiness, regions, profile, BR stats, CS stats, search, invalid UID,
invalid region, legacy profile. Profile/stat/search assertions require HTTP 200
and the correct `meta.source`, so a live connection failure cannot silently pass
as demo data. Readiness requires a configured account for live mode.

Validation requests deliberately expect 422. Synthetic demo stats are identical
across filters within each mode; the collection tests REST behavior, not game accuracy.

## Command line

From the `bruno/` directory, with the API running:

```bash
npx --yes --package @usebruno/cli@4.2.1 bru run --env "Local Demo"
```

Replace the environment name with `Local Live` after setting its UID/region and
server credentials. The API defaults to 60 player requests/minute; repeated runs
may return 429. The collection itself does not create or change game accounts.
