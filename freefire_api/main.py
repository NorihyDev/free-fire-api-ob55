import hmac
import logging
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, FastAPI, Path, Query, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from freefire_api.client import FreeFireClient
from freefire_api.demo import DemoClient
from freefire_api.errors import APIError
from freefire_api.settings import REGIONS, Settings

UID = Annotated[
    str, Path(pattern=r"^[1-9][0-9]{0,19}$", description="Player UID as a decimal string")
]
Region = Annotated[str | None, Query(description="Server region, e.g. IND, BR or SG")]
Mode = Literal["br", "cs"]
MatchType = Literal["career", "normal", "ranked"]
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str


class Metadata(BaseModel):
    region: str
    release_version: str
    source: Literal["live", "demo"]
    cached: bool
    request_id: str


class DataResponse(BaseModel):
    data: dict[str, Any]
    meta: Metadata


ERRORS = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in {
        401: "Missing or invalid API key",
        404: "Player not found",
        422: "Invalid request parameters",
        429: "Local request limit exceeded",
        502: "Game authentication, transport or protocol failure",
        503: "Region unconfigured, or game server rate limited",
        504: "Game request timed out",
    }.items()
}


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(
            timeout=settings.timeout_seconds,
            transport=transport,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        ) as http:
            app.state.client = (
                DemoClient() if settings.mode == "demo" else FreeFireClient(settings, http)
            )
            app.state.cache = OrderedDict()
            app.state.limits = OrderedDict()
            yield

    app = FastAPI(
        title="Free Fire API",
        version="0.2.0",
        lifespan=lifespan,
        description=(
            "Unofficial Free Fire player data API. Direct-session mode uses your existing game JWT "
            "without Garena auth calls. A valid owned token is required for live requests. "
            "Demo mode is labelled in every response. UIDs and protobuf uint64 values "
            "are strings to preserve precision. Live OB55 needs credentialed verification."
        ),
        license_info={"name": "GPL-3.0-only", "identifier": "GPL-3.0-only"},
        openapi_tags=[{"name": "Players"}, {"name": "System"}, {"name": "Legacy"}],
    )
    app.state.settings = settings

    def error(request: Request, status: int, code: str, message: str, details=None, headers=None):
        body = {"error": {"code": code, "message": message}, "request_id": request.state.request_id}
        if details is not None:
            body["error"]["details"] = details
        return JSONResponse(body, status_code=status, headers=headers)

    @app.middleware("http")
    async def request_metadata(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        try:
            response = await call_next(request)
        except Exception:
            # Do not log request headers, credentials, raw upstream data or exception values.
            logging.getLogger(__name__).error("Unexpected API failure %s", request.state.request_id)
            response = error(request, 500, "INTERNAL_ERROR", "Unexpected server error.")
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(APIError)
    async def api_error(request: Request, exc: APIError):
        headers = {"Retry-After": "60"} if exc.status in (429, 503) else None
        return error(request, exc.status, exc.code, exc.message, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [{"location": list(item["loc"]), "message": item["msg"]} for item in exc.errors()]
        return error(request, 422, "VALIDATION_ERROR", "Invalid request parameters.", details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error(request, exc.status_code, "HTTP_ERROR", str(exc.detail))

    async def authorize(
        request: Request,
        key: Annotated[str | None, Security(api_key_header)],
    ):
        expected = settings.api_key.get_secret_value()
        if expected and not hmac.compare_digest((key or "").encode(), expected.encode()):
            raise APIError(401, "INVALID_API_KEY", "Provide a valid X-API-Key header.")
        identity = request.client.host if request.client else "unknown"
        now = time.monotonic()
        limits = request.app.state.limits
        start, count = limits.get(identity, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        limits[identity] = (start, count + 1)
        limits.move_to_end(identity)
        if len(limits) > 10000:
            limits.popitem(last=False)
        if count >= settings.rate_limit_per_minute:
            raise APIError(429, "RATE_LIMITED", "Request limit exceeded; retry after one minute.")

    def region_value(region: str | None) -> str:
        value = (region or settings.default_region).upper()
        if value not in REGIONS:
            raise APIError(422, "INVALID_REGION", "Unknown region. See /api/v1/regions.")
        return value

    def uid_value(uid: str) -> str:
        if not uid.isascii() or not uid.isdecimal() or not 0 < int(uid) <= 2**64 - 1:
            raise APIError(422, "INVALID_UID", "UID must be a positive uint64 decimal string.")
        return uid

    async def respond(request: Request, region: str, cache_key: tuple, loader):
        cache = request.app.state.cache
        cached = cache.get(cache_key)
        hit = bool(cached and cached[0] > time.monotonic())
        if hit:
            data = cached[1]
            cache.move_to_end(cache_key)
        else:
            data = await loader()
            if settings.cache_ttl_seconds:
                cache[cache_key] = (time.monotonic() + settings.cache_ttl_seconds, data)
                cache.move_to_end(cache_key)
                if len(cache) > 1000:
                    cache.popitem(last=False)
        return DataResponse(
            data=data,
            meta=Metadata(
                region=region,
                release_version=settings.release_version,
                source=settings.mode,
                cached=hit,
                request_id=request.state.request_id,
            ),
        )

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/docs")

    @app.get("/health", tags=["System"], summary="Check the API process")
    async def health():
        return {
            "status": "ok",
            "mode": settings.mode,
            "release_version": settings.release_version,
            "auth_method": settings.auth_method if settings.mode == "live" else None,
        }

    @app.get("/ready", tags=["System"], summary="Check credential configuration")
    async def ready(request: Request):
        regions = sorted(request.app.state.client.accounts)
        available = (
            regions if settings.mode == "demo" else request.app.state.client.available_regions()
        )
        ready = settings.mode == "demo" or bool(available)
        return JSONResponse(
            {
                "status": "ready" if ready else "not_ready",
                "mode": settings.mode,
                "configured_regions": regions,
                "available_regions": available,
                "auth_method": settings.auth_method if settings.mode == "live" else None,
                "upstream_verified": False,
                "note": "Configuration check only. A player request verifies live upstream access.",
            },
            status_code=200 if ready else 503,
        )

    @app.get("/api/v1/regions", tags=["System"], summary="List recognized and configured regions")
    async def regions(request: Request):
        configured = request.app.state.client.accounts
        return {
            "regions": [{"code": value, "configured": value in configured} for value in REGIONS],
            "default": settings.default_region,
            "mode": settings.mode,
        }

    router = APIRouter(dependencies=[Depends(authorize)], responses=ERRORS)

    @router.get(
        "/api/v1/players/{uid}/profile",
        tags=["Players"],
        response_model=DataResponse,
        summary="Get a player profile, guild and pet",
    )
    async def profile(request: Request, uid: UID, region: Region = None, gallery: bool = False):
        uid, region = uid_value(uid), region_value(region)
        return await respond(
            request,
            region,
            ("profile", region, uid, gallery),
            lambda: request.app.state.client.profile(uid, region, gallery),
        )

    @router.get(
        "/api/v1/players/{uid}/stats",
        tags=["Players"],
        response_model=DataResponse,
        summary="Get Battle Royale or Clash Squad statistics",
    )
    async def stats(
        request: Request,
        uid: UID,
        region: Region = None,
        mode: Mode = "br",
        match_type: MatchType = "career",
    ):
        uid, region = uid_value(uid), region_value(region)
        return await respond(
            request,
            region,
            ("stats", region, uid, mode, match_type),
            lambda: request.app.state.client.stats(uid, region, mode, match_type),
        )

    @router.get(
        "/api/v1/players/search",
        tags=["Players"],
        response_model=DataResponse,
        summary="Search players by nickname",
    )
    async def search(
        request: Request,
        keyword: Annotated[str, Query(min_length=3, max_length=50)],
        region: Region = None,
    ):
        keyword = keyword.strip()
        if len(keyword) < 3:
            raise APIError(
                422, "INVALID_KEYWORD", "Keyword must have at least three non-space characters."
            )
        region = region_value(region)
        return await respond(
            request,
            region,
            ("search", region, keyword),
            lambda: request.app.state.client.search(keyword, region),
        )

    @router.get(
        "/get_player_personal_show",
        tags=["Legacy"],
        deprecated=True,
        response_model=DataResponse,
        summary="Legacy profile route",
    )
    async def legacy_profile(
        request: Request,
        uid: Annotated[str, Query(pattern=r"^[1-9][0-9]{0,19}$")],
        server: str | None = None,
        need_gallery_info: bool = False,
    ):
        return await profile(request, uid, server, need_gallery_info)

    @router.get(
        "/get_player_stats",
        tags=["Legacy"],
        deprecated=True,
        response_model=DataResponse,
        summary="Legacy stats route",
    )
    async def legacy_stats(
        request: Request,
        uid: Annotated[str, Query(pattern=r"^[1-9][0-9]{0,19}$")],
        server: str | None = None,
        gamemode: Mode = "br",
        matchmode: Literal["CAREER", "NORMAL", "RANKED"] = "CAREER",
    ):
        return await stats(request, uid, server, gamemode, matchmode.lower())

    @router.get(
        "/get_search_account_by_keyword",
        tags=["Legacy"],
        deprecated=True,
        response_model=DataResponse,
        summary="Legacy search route",
    )
    async def legacy_search(
        request: Request,
        keyword: Annotated[str, Query(min_length=3, max_length=50)],
        server: str | None = None,
    ):
        return await search(request, keyword, server)

    app.include_router(router)
    return app


app = create_app()
