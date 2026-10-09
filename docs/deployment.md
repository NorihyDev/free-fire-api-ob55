# Deployment

## Docker Compose

```bash
docker compose up --build -d
docker compose logs -f api
```

Compose defaults to demo unless `.env` sets another mode. It binds to loopback
`127.0.0.1:8000`, mounts `config/` read-only, and keeps credentials out of the image.
For direct-session live mode, supply `config/sessions.json` and set `FF_MODE=live`
and `FF_AUTH_METHOD=session` before startup. Optional guest mode uses
`config/accounts.json` and `FF_AUTH_METHOD=guest`.
The mounted account file must be readable by UID 10001 in the Linux container.

The image runs as a non-root user. Its healthcheck tests `/health`, which confirms
the process, not live authentication. Runtime dependencies are pinned in
`requirements.lock`; development dependencies are in `requirements-dev.lock`.

Docker configuration is supplied for deployment; local validation uses Python
and Bruno. A Docker build is only verified when Docker is available.

## Internet hosting

Deploy the Docker image to a host with outbound HTTPS access to Garena. Run
Uvicorn on the port your host expects, terminate HTTPS through the platform or
a reverse proxy, and set `FF_API_KEY` for player endpoints on a public instance.
Use secret environment variables and a private mounted sessions/accounts file.

For platforms injecting a `PORT` environment variable, override the container
command with a platform-supported command that passes that port to Uvicorn.
The image defaults to port 8000; source publication on GitHub does not create
an internet-hosted API.

Behind a reverse proxy, enable Uvicorn proxy headers and explicitly configure
the trusted proxy IP addresses. Do not trust arbitrary forwarded headers from
internet clients, because the rate limiter uses the client IP Uvicorn exposes.

## Scaling

Sessions, request limits and response caches are per process. Start with one
worker. Multiple workers/replicas each have their own allowance and may log in
the same guest concurrently. Use shared storage and distributed coordination
before requiring cross-worker rate limits or sessions. No Redis dependency is
required for local testing.

Direct-session mode has no automatic token refresh. Replace the private session
file and restart the process when your own session expires.

Game accounts and protocol availability are external dependencies. A green
process healthcheck does not mean that live player requests are succeeding.
