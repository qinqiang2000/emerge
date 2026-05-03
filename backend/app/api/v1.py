from fastapi import APIRouter

from app.api.routes import auth

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
