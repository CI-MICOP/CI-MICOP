from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings

settings.check_startup_security()

# Step 5.8.26: the interactive docs and the OpenAPI schema list every
# endpoint, so they are only served in development.
_docs_enabled = settings.is_development

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root():
    return {"service": settings.PROJECT_NAME, "status": "running"}
