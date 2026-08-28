from fastapi import FastAPI  # pyright: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # pyright: ignore[reportMissingImports]
from fastapi.openapi.utils import get_openapi  # pyright: ignore[reportMissingImports]

from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="SatQuery AI Backend - Data Pipeline, Geospatial Processing & Vision-Language Assistant Service.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable Cross-Origin Resource Sharing (CORS) for seamless frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust allowed origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


def custom_openapi():
    """Custom OpenAPI schema generator ensuring Swagger UI displays file pickers for array-of-files."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Ensure multipart array-of-files displays as binary file pickers in Swagger UI
    for schema_name, schema in openapi_schema.get("components", {}).get("schemas", {}).items():
        for prop_name, prop in schema.get("properties", {}).items():
            if prop.get("type") == "array" and "items" in prop:
                if "contentMediaType" in prop["items"] or prop_name in ["files", "images"]:
                    prop["items"] = {"type": "string", "format": "binary"}

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/", tags=["Health & Info"])
async def root():
    """Root status endpoint providing API information."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs_url": "/docs",
        "api_v1": settings.API_V1_PREFIX,
    }


@app.get("/health", tags=["Health & Info"])
async def health_check():
    """Health check probe endpoint."""
    return {"status": "healthy"}
