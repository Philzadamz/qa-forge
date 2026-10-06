"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import REQUEST_ID_HEADER, RequestIdMiddleware, configure_logging
from app.routers import (
    api_lab,
    apks,
    auth,
    bugs,
    cases,
    dashboard,
    features,
    health,
    projects,
    reports,
    runs,
    secrets,
    stories,
    suites,
    types,
)
from app.routers.admin import router as admin_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="QA Forge API",
        version="0.1.0",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)

    # Probes at the root (for orchestrators) and under the API prefix (for the web app proxy).
    app.include_router(health.router)
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(admin_router, prefix=settings.api_prefix)
    app.include_router(features.public_router, prefix=settings.api_prefix)
    app.include_router(types.router, prefix=settings.api_prefix)
    app.include_router(projects.router, prefix=settings.api_prefix)
    app.include_router(stories.router, prefix=settings.api_prefix)
    app.include_router(suites.router, prefix=settings.api_prefix)
    app.include_router(cases.router, prefix=settings.api_prefix)
    app.include_router(bugs.router, prefix=settings.api_prefix)
    app.include_router(reports.router, prefix=settings.api_prefix)
    app.include_router(secrets.router, prefix=settings.api_prefix)
    app.include_router(runs.router, prefix=settings.api_prefix)
    app.include_router(api_lab.router, prefix=settings.api_prefix)
    app.include_router(apks.router, prefix=settings.api_prefix)
    app.include_router(dashboard.router, prefix=settings.api_prefix)
    return app


app = create_app()
