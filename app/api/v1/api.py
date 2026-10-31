from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.baggage import router as baggage_router
from app.api.v1.endpoints.users import router as users_router

# Mounted in main.py under settings.API_PREFIX (default "/api").
v1_router = APIRouter()
v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(baggage_router)
