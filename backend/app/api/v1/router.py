from fastapi import APIRouter
from app.api.v1.endpoints import ingest, session

api_router = APIRouter()

# Ingest & validation routes
api_router.include_router(ingest.router, prefix="/ingest", tags=["Ingest & Validation"])

# Session management & scene analysis routes
api_router.include_router(session.router, prefix="/session", tags=["Session & Scene Classification"])
