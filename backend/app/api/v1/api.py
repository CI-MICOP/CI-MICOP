"""Aggregates all v1 routers into a single APIRouter.

New feature routers (auth, claims, users, etc.) should be created under
app/api/v1/routers/ and registered here, so app/main.py never needs to
change when the API grows.
"""

from fastapi import APIRouter

from app.api.v1.routers import (
    admin,
    auth,
    claims,
    customers,
    documents,
    health,
    officer,
    policies,
    surveyor,
    vehicles,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(vehicles.router)
api_router.include_router(policies.router)
api_router.include_router(claims.router)
api_router.include_router(documents.router)
api_router.include_router(surveyor.router)
api_router.include_router(officer.router)
api_router.include_router(admin.router)
