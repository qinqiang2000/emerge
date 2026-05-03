import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import public
from app.api.v1 import api_v1
from app.db import SessionFactory
from app.errors import register_error_handler
from app.services.builtin_templates import seed_builtin_templates
from app.services.ratelimit import limiter
from app.settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with SessionFactory() as session:
        try:
            await seed_builtin_templates(session)
        except Exception as exc:
            # Pre-bootstrap path (DB not migrated yet, or no users for FK target).
            # Resilient on startup but surface real failures to operators.
            logger.warning("seed_builtin_templates failed at startup: %s", exc, exc_info=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="emerge", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handler(app)
    app.state.limiter = limiter

    app.include_router(api_v1)
    app.include_router(public.router)  # no prefix — public surface
    return app


app = create_app()
