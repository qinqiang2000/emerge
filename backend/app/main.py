from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1
from app.db import SessionFactory
from app.errors import register_error_handler
from app.services.builtin_templates import seed_builtin_templates
from app.settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with SessionFactory() as session:
        try:
            await seed_builtin_templates(session)
        except Exception:
            # Pre-bootstrap (no users yet) or transient FK issue — leave seeding
            # to a later request-driven retry. Logged elsewhere.
            pass
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
    app.include_router(api_v1)
    return app


app = create_app()
