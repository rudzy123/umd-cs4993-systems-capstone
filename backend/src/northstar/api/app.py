"""FastAPI application factory."""

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from northstar import __version__
from northstar.api.errors import ApiError, error_payload
from northstar.api.middleware import LimitRequestSizeMiddleware
from northstar.api.routes import router
from northstar.bootstrap import prepare_for_serve
from northstar.config import Settings, get_settings
from northstar.db import make_engine, make_session_factory
from northstar.logging_config import configure_logging

logger = logging.getLogger("northstar.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings or get_settings()
    configure_logging(active.log_level)
    engine = make_engine(active.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        prepare_for_serve(app.state.engine, app.state.settings, threading.Event())
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="Northstar Job Lab",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = active
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    _register_exceptions(app)
    app.add_middleware(LimitRequestSizeMiddleware, max_bytes=active.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins(active.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Idempotency-Key"],
        max_age=600,
    )
    app.include_router(router)
    return app


def _origins(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _register_exceptions(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "loc": [str(part) for part in error.get("loc", ())],
                "message": str(error.get("msg", "Invalid value")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_payload("validation_error", "The request is invalid.", details),
        )

    @app.exception_handler(HTTPException)
    async def handle_http(_request: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(status_code=exc.status_code, content=error_payload(code, message))

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, _exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", extra={"ns_exception_type": type(_exc).__name__})
        return JSONResponse(
            status_code=500,
            content=error_payload("internal_error", "The server could not complete this request."),
        )
