"""Aggregates all v1 routers into a single APIRouter.

New feature routers (auth, claims, users, etc.) should be created under
app/api/v1/routers/ and registered here, so app/main.py never needs to
change when the API grows.
"""

from fastapi import APIRouter

from app.api.v1.routers import health

api_router = APIRouter()
api_router.include_router(health.router)
