from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.baggage import router as baggage_router
from app.api.v1.endpoints.dashboard import router as dashboard_router
from app.api.v1.endpoints.public import router as public_router
from app.api.v1.endpoints.users import router as users_router

...

# Mounted in main.py under settings.API_PREFIX (default "/api").
v1_router = APIRouter()
v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(baggage_router)
v1_router.include_router(public_router)
v1_router.include_router(dashboard_router)
