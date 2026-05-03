from fastapi import APIRouter

from app.api.routes import annotations, auth, documents, extraction, me, projects, publish, scores, templates, versions

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(me.router)
api_v1.include_router(projects.router)
api_v1.include_router(documents.router)
api_v1.include_router(extraction.router)
api_v1.include_router(versions.router)
api_v1.include_router(annotations.router)
api_v1.include_router(scores.router)
api_v1.include_router(templates.router)
api_v1.include_router(publish.router)
