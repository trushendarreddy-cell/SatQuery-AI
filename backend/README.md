# SatQuery AI - Backend & Data Pipeline

SatQuery AI is an Interactive Vision-Language Assistant for Multimodal Remote Sensing Image Analysis through Text Queries (Smart India Hackathon 2026).

This service provides the **Data Pipeline, Geospatial Processing Engine, and REST API** that validates satellite imagery, extracts rich spatial metadata, aligns multi-temporal rasters, and computes geospatial metrics.

---

## Milestone 1: GeoTIFF Ingestion, Validation & Metadata Extraction

### Features Implemented
- **GeoTIFF Structural & Geospatial Validation:** Validates file headers, raster drivers, positive dimensions, spectral bands, valid CRS, and affine geotransforms.
- **Metadata Extraction:** Extracts native bounding boxes, WGS84 Lat/Lon coordinates (`EPSG:4326`), ground sampling distance (spatial resolution), data types, nodata values, and per-band statistics.
- **REST API Endpoint (`POST /api/v1/ingest/inspect`):** Accepts GeoTIFF uploads via multipart form data and returns validated structured JSON responses.
- **Error Handling:** Gracefully handles corrupted, non-georeferenced, or non-image files with structured HTTP `422` error responses.
- **Automated Test Suite:** Pytest unit tests for the validator, metadata extractor, and API endpoints using synthetic test rasters.

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ (Python 3.10, 3.11, 3.12, 3.13, 3.14)
- Pip package manager

### 2. Create and Activate Virtual Environment
Open a terminal in the `backend` folder:

```bash
cd "d:\SIH 2026\SatQuery AI\backend"

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
.\venv\Scripts\activate.bat

# On Linux / macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Backend Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, visit:
- **Interactive Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## Running Automated Tests

Run the test suite from the `backend` directory:

```bash
pytest -v
```

---

## Project Structure (Milestone 1)

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py                # App configuration & paths
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── metadata_schema.py       # Pydantic schemas for API requests & responses
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── validator.py             # GeoTIFF integrity & geospatial validation
│   │   └── metadata.py              # Metadata extraction & bounds calculation
│   ├── geospatial/                  # (For subsequent milestones)
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── router.py            # Aggregated v1 API routes
│           └── endpoints/
│               ├── __init__.py
│               └── ingest.py        # POST /api/v1/ingest/inspect endpoint
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # In-memory GeoTIFF fixtures for testing
│   ├── test_validator.py            # Unit tests for validator
│   ├── test_metadata.py             # Unit tests for metadata extractor
│   └── test_api.py                  # Integration tests for FastAPI endpoints
├── requirements.txt
└── README.md
```
