# SatQuery AI - Backend & Data Pipeline

**SatQuery AI** is an Interactive Vision-Language Assistant for Multimodal Remote Sensing Image Analysis through Text Queries (Smart India Hackathon 2026).

This service provides the **Data Pipeline, Geospatial Processing Engine, REST API, and Deterministic Analysis Framework** that validates satellite imagery, extracts rich spatial metadata, aligns multi-temporal rasters, detects change, computes spectral indices, and generates grounded analysis reports.

**Current Status:** M1–M15 Complete  
**Test Coverage:** 242 passed, 0 failed, 16 warnings (227 baseline + 15 integration)  
**Database Support:** SQLAlchemy 2.0+ with SQLite (dev) and MySQL (production-ready)  
**Master Agent Integration:** Ready for team's LangGraph deployment

---

## Development Milestones

### ✅ Milestone 1: GeoTIFF Ingestion, Validation & Metadata Extraction
- **GeoTIFF Validation:** File headers, raster drivers, dimensions, spectral bands, CRS, affine geotransforms
- **Metadata Extraction:** Native bounding boxes, WGS84 coordinates, ground sampling distance, data types, nodata values, per-band statistics
- **API Endpoint:** `POST /api/v1/ingest/inspect` – multipart file upload with structured JSON responses
- **Error Handling:** Corrupted, non-georeferenced, and non-image files handled with HTTP 422 responses
- **Test Coverage:** Pytest unit tests for validator, metadata extractor, and API endpoints

### ✅ Milestone 2: Image Standardization & Multi-modal Support
- **Universal Image Validator:** Single interface for GeoTIFF, JPEG, PNG, and other raster formats
- **Unified Metadata Schema:** Consistent metadata representation across all image types
- **Multi-modal Detection:** Automatic categorization (geospatial_geotiff, visual_standard, unsupported)
- **Cross-format Compatibility:** Safe handling of mixed GeoTIFF + visual image workflows

### ✅ Milestone 3: Geospatial Index Computation
- **Spectral Indices:** NDVI, EVI, NDWI, SAVI, NDBI computation from multispectral rasters
- **Safe Division & NoData Handling:** Prevents divide-by-zero, respects nodata values
- **Flexible Band Selection:** User-configurable red, NIR, blue, green, SWIR bands
- **Artifact Generation:** Computed indices stored as GeoTIFF artifacts with full geospatial metadata
- **Statistical Summary:** Per-index min/max/mean/std and valid/nodata pixel counts

### ✅ Milestone 4: Multi-temporal Raster Alignment
- **Automatic CRS Alignment:** Reprojects rasters to a common CRS before comparison
- **Bounds Intersection:** Computes spatial overlap for safe multi-temporal analysis
- **Clipping & Resampling:** Aligns raster grids and resolution for temporal stacking
- **Compatibility Checking:** Validates image pairs for temporal analysis

### ✅ Milestone 5: Scene Classification
- **Scene Classifier:** Categorizes image content (urban, vegetation, water, agricultural, mixed, other)
- **Metadata-based Rules:** Applies deterministic rules to metadata for classification
- **Per-image & Per-band Confidence:** Reports classification confidence by band and scene-level
- **No ML Required:** Purely rule-based, reproducible, explainable classification

### ✅ Milestone 6: Geospatial Overlap & Compatibility Analysis
- **Spatial Overlap Calculation:** Computes area of intersection between image footprints
- **Bounds Compatibility:** Checks if image pairs can be jointly analyzed
- **Polygon Vectorization:** Converts raster masks to GeoJSON polygons with area calculation
- **Area Computation:** Converts any GeoJSON geometry to area in m², ha, km²

### ✅ Milestone 7: Change Detection
- **Binary Change Masks:** Identifies pixels changed between temporal image pairs
- **Temporal Validation:** Phenological and temporal consistency checks
- **Artifact Generation:** Produces change-detection raster as GeoTIFF output
- **Quantitative Reporting:** Reports change statistics (pixels, percentages, affected area)

### ✅ Milestone 8: Analysis Orchestration
- **Deterministic Plan Execution:** Transforms natural-language queries into structured execution plans
- **Tool Registry:** Central registry of available analysis tools (validators, masks, indices, etc.)
- **Step-by-step Execution:** Tracks per-step success, failure, and skip status
- **Artifact & Statistics Aggregation:** Collects all outputs into unified result structures
- **No Black-Box LLM:** Deterministic backbone with optional LLM/vision enhancements

### ✅ Milestone 9: LLM Query Intelligence
- **Pluggable LLM Providers:** Gemini, OpenAI-compatible, deterministic mock fallback
- **Natural-language Intent Detection:** Interprets user queries to guide plan selection
- **Tool-grounded Responses:** LLM responses reference tool outputs (no hallucination)
- **Provider Abstraction:** Unified `chat(messages, tools)` contract across providers

### ✅ Milestone 10: Multimodal & Vision-Aware Analysis
- **Vision Service Integration:** Image analysis using vision models (e.g., Gemini Vision)
- **Visual Reasoning:** Describes visible objects, features, and scene content
- **Confidence Scoring:** Provides confidence levels for visual observations
- **Fallback Handling:** Gracefully degrades when vision provider is unavailable

### ✅ Milestone 11: Interactive Agent API
- **Agent Service:** LLM-driven tool orchestration and execution
- **Tool Invocation:** Dynamically calls geospatial tools based on LLM suggestions
- **Agent Endpoints:** `/api/v1/agent/query` for interactive agent-driven analysis
- **Multi-turn Capable:** Supports follow-up questions and tool-result refinement

### ✅ Milestone 12: End-to-End Report Generation
- **Evidence-grounded Reports:** Assembles findings from execution results (no fabrication)
- **Structured Report Schema:** Includes title, summary, findings, quantitative results, artifacts, limitations
- **Evidence Tagging:** Marks each finding as computed, visual, metadata, or inference
- **Confidence Assessment:** Reports confidence based on evidence and execution status
- **Report Artifacts:** References generated rasters and derived outputs

### ✅ Milestone 13: End-to-End Report Flow (Verified & Hardened)
- **Query → Plan → Execute → Report Pipeline:** Complete deterministic flow from user query to final report
- **Planner Bug Fix:** Explicit classification to prevent false-positive image inspection calls
- **Report Integrity:** Ensures all findings are grounded in tool outputs and execution evidence
- **Session State Consistency:** Maintains image, artifact, and execution state throughout pipeline
- **Full Test Coverage:** End-to-end flow validation across M1–M13 components

### ✅ Milestone 14: Persistence & Database Integration
- **SQLAlchemy 2.0 Models:** Durable session, image, analysis, execution, evidence, artifact, and report records
- **Alembic Migrations:** Schema evolution support for production deployments
- **Safe File Storage:** Storage path traversal prevention and artifact filename sanitization
- **Persistence Service:** Unified DB and filesystem storage abstraction
- **Session Management:** Runtime cache + durable database for session lifecycle
- **Reference Stability:** Stable session_id, image_id, analysis_id for external integration

### ✅ Milestone 15: Master Agent Integration (Current)
- **AgentContext Service:** Exposes stable session context (images, artifacts, spatial info) to Master Agent
- **MasterAgentPort Protocol:** Defines contract for team's LangGraph implementation (dependency injection)
- **Integration Schemas:** Pydantic models for AgentContext, AgentResponse, Evidence (grounding)
- **Response Adapters:** Converts Master Agent responses to existing Report schema seamlessly
- **Artifact Safety:** Safe storage key references (no filesystem paths exposed)
- **Evidence Grounding:** Enforces that all findings reference evidence (computed/visual/metadata/inference)
- **Integration Tests:** 15 tests validating context generation, artifact access, adapters, evidence grounding
- **Integration Documentation:** Complete guide for team's Master Agent deployment (MASTER_AGENT_INTEGRATION.md)

---

## Key Features

### 🗺️ Geospatial Capabilities
- GeoTIFF validation and georeferencing
- Multi-temporal raster alignment (CRS + bounds checking)
- Spectral index computation (NDVI, EVI, NDWI, SAVI, NDBI)
- Cloud & shadow masking via QA/SCL bands
- Change detection between temporal image pairs
- Polygon vectorization and area calculation
- Zonal statistics and spatial overlap analysis

### 🔬 Analysis Pipeline
- Deterministic query planner (no hidden inference)
- Modular tool registry with pluggable analysis functions
- Evidence-backed execution results and artifact generation
- LLM-optional query interpretation and visual reasoning
- Grounded report generation with confidence scoring

### 🛡️ Production Readiness
- REST API with CORS support
- Request/response validation via Pydantic
- Structured error handling (422 for validation, 500 for runtime)
- Health check endpoints (`/health`, `/ready`)
- Safe session and artifact management (no path traversal)
- SQLAlchemy-backed persistence layer
- Alembic migration support for schema evolution

---

---

## API Endpoints

### Health & Info
- `GET /` – Root status endpoint
- `GET /health` – Health check probe
- `GET /ready` – Readiness check (confirms storage availability)

### Image Ingestion & Inspection
- `POST /api/v1/ingest/inspect` – Inspect and validate image (GeoTIFF, JPEG, PNG)
- `POST /api/v1/ingest/upload` – Upload images to session

### Session Management
- `POST /api/v1/session/create` – Create new analysis session
- `GET /api/v1/session/{session_id}` – Get session state
- `GET /api/v1/session/{session_id}/artifacts` – List session artifacts
- `GET /api/v1/session/{session_id}/artifacts/{filename}` – Download artifact
- `GET /api/v1/session/{session_id}/classification` – Get scene classification
- `DELETE /api/v1/session/{session_id}` – Delete session and artifacts

### Query & Analysis
- `POST /api/v1/query/analyze` – Plan query execution (deterministic planner)
- `POST /api/v1/query/orchestrate` – Execute analysis plan
- `POST /api/v1/query/report` – Generate end-to-end report
- `POST /api/v1/agent/query` – Agent-driven interactive query

### Geospatial Analysis (via orchestration or direct)
- **Cloud Masking** – Detects and masks cloud/shadow pixels from QA/SCL bands
- **Spectral Indices** – Computes NDVI, EVI, NDWI, SAVI, NDBI
- **Change Detection** – Identifies temporal changes between image pairs
- **Temporal Validation** – Checks phenological and seasonal consistency
- **Zonal Statistics** – Summarizes raster values over geometries or masks
- **Area Calculation** – Computes area from GeoJSON geometries
- **Vectorization** – Converts raster masks to GeoJSON polygons
- **Scene Classification** – Classifies scene content (urban, vegetation, water, etc.)

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ (Python 3.10, 3.11, 3.12, 3.13, 3.14)
- Pip package manager
- SQLite 3 (default) or MySQL (production)

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

### 4. Configure Environment (Optional)
Create a `.env` file in the `backend` directory to override defaults:

```env
# Database
DATABASE_URL=sqlite:///satquery.db

# LLM Provider (optional)
LLM_PROVIDER=gemini
LLM_API_KEY=your-api-key
LLM_MODEL=gemini-2.0-flash

# Vision Provider (optional)
VISION_PROVIDER=gemini

# Storage
UPLOAD_SIZE_LIMIT_MB=500
```

### 5. Run the Backend Server
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
# Run all tests with verbose output
pytest -v

# Run only one test file
pytest tests/test_api.py -v

# Run tests with coverage
pytest --cov=app tests/
```

**Current Test Status:**
- 227 tests passed
- 0 tests failed
- 16 warnings (from dependencies, not our code)
- Runtime: ~11 seconds

---

## Project Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Environment config, DATABASE_URL, storage paths
│   │   ├── database.py              # SQLAlchemy engine, session, base metadata
│   │   ├── logging.py               # Structured logging setup
│   │   ├── path_utils.py            # Safe filename/path handling (traversal prevention)
│   │   └── session_cache.py         # Runtime session manager and image registry
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── models.py                # SQLAlchemy ORM models (Session, Image, Analysis, etc.)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── persistence_service.py   # DB + filesystem storage abstraction
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── schemas.py               # AgentToolCall, AgentToolResult
│   │   ├── service.py               # Agent service (LLM + tool execution)
│   │   ├── llm.py                   # LLM providers (Gemini, OpenAI, Mock)
│   │   ├── vision.py                # Vision service for image analysis
│   │   ├── tools.py                 # Tool registry and invocation
│   │   └── query_intelligence.py    # Query interpretation and classification
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── validator.py             # GeoTIFF validation (M1)
│   │   ├── metadata.py              # Metadata extraction (M1)
│   │   ├── scene_classifier.py      # Scene classification (M5)
│   │   ├── alignment.py             # Multi-temporal alignment (M4)
│   │   ├── compatibility.py         # Compatibility checking (M6)
│   │   ├── overlap.py               # Spatial overlap (M6)
│   │   ├── query_planner.py         # Query planning (M8, M13)
│   │   ├── orchestrator.py          # Plan execution (M8, M13)
│   │   ├── analysis.py              # Analysis execution helpers
│   │   └── change_detection.py      # Change detection (M7)
│   │
│   ├── geospatial/
│   │   ├── __init__.py
│   │   ├── cloud_mask.py            # Cloud/shadow masking (M7)
│   │   ├── spectral_index.py        # Spectral indices (M3)
│   │   ├── seasonal.py              # Temporal validation (M7)
│   │   ├── zonal.py                 # Zonal statistics (M6)
│   │   ├── area.py                  # Area calculation (M6)
│   │   ├── clip.py                  # Clipping utilities (M4)
│   │   └── vectorize.py             # Raster to GeoJSON (M6)
│   │
│   ├── reporting/
│   │   ├── __init__.py
│   │   └── report_generator.py      # Evidence-grounded report assembly (M12)
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── metadata_schema.py       # Image metadata (M1)
│   │   ├── query_schema.py          # Query intent and response (M8)
│   │   ├── orchestration_schema.py  # Execution result schemas (M8)
│   │   ├── report_schema.py         # Report structure (M12)
│   │   ├── analysis_schema.py       # Analysis request/response schemas
│   │   ├── change_detection_schema.py
│   │   ├── scene_schema.py          # Scene classification schemas
│   │   ├── spatial_schema.py        # Spatial analysis schemas
│   │   ├── vision_schema.py         # Vision service schemas (M10)
│   │   └── query_intelligence_schema.py  # Query intelligence schemas (M9)
│   │
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── router.py            # API v1 route aggregator
│           └── endpoints/
│               ├── __init__.py
│               ├── ingest.py        # Image upload & inspection
│               ├── session.py       # Session management & artifacts
│               ├── query.py         # Query planning
│               ├── orchestration.py # Plan execution
│               ├── report.py        # Report generation
│               ├── agent.py         # Agent-driven queries
│               ├── analysis.py      # Direct analysis endpoints
│               ├── change_detection.py
│               └── spatial.py       # Spatial analysis endpoints
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures (GeoTIFF, images, sessions)
│   ├── test_api.py                  # API integration tests
│   ├── test_validator.py            # GeoTIFF validator tests
│   ├── test_metadata.py             # Metadata extractor tests
│   ├── test_scene_classifier.py     # Scene classification tests
│   ├── test_alignment.py            # Alignment tests
│   ├── test_overlap.py              # Overlap calculation tests
│   ├── test_change_detection.py     # Change detection tests
│   ├── test_spectral_index.py       # Spectral index tests
│   ├── test_query_pipeline.py       # Query planning tests
│   ├── test_orchestration.py        # Orchestration tests
│   ├── test_report_generation.py    # Report generation tests
│   ├── test_analysis_api.py         # Analysis endpoint tests
│   ├── test_persistence.py          # Persistence & DB tests (M14)
│   └── [additional test files for M9-M14 features]
│
├── alembic/                         # Database migration scripts (M14)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── temp/
│   ├── cache/                       # Runtime artifact cache
│   └── uploads/                     # Uploaded image storage
│
├── requirements.txt                 # Python dependencies
├── alembic.ini                      # Alembic configuration
├── conftest.py                      # Top-level pytest configuration
├── pytest.ini                       # Pytest configuration
└── README.md                        # This file
```

---

## Configuration

### Environment Variables
The backend reads configuration from environment variables or `.env` file:

```env
# FastAPI
PROJECT_NAME=SatQuery AI
VERSION=1.0.0
DEBUG=False

# Database (SQLAlchemy URL)
DATABASE_URL=sqlite:///satquery.db
# For MySQL: DATABASE_URL=mysql+pymysql://user:password@localhost/satquery

# Storage
UPLOAD_DIR=./temp/uploads
CACHE_DIR=./temp/cache
MAX_UPLOAD_SIZE_BYTES=524288000  # 500 MB

# LLM Provider
LLM_PROVIDER=gemini  # or openai, mock, or disabled
LLM_API_KEY=your-api-key
LLM_MODEL=gemini-2.0-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MAX_TOKENS=1024
LLM_TEMPERATURE=0.0

# Vision Provider
VISION_PROVIDER=gemini
VISION_API_KEY=your-api-key

# CORS
CORS_ALLOWED_ORIGINS=["*"]
```

### Database Setup
The backend automatically initializes the SQLite database on startup. For production MySQL deployments:

```bash
# Create a MySQL database
mysql -u root -p -e "CREATE DATABASE satquery CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Set DATABASE_URL environment variable
export DATABASE_URL=mysql+pymysql://user:password@localhost/satquery

# Run alembic migrations (if applicable)
alembic upgrade head
```

---

## Workflow: Upload → Query → Report

### Example: Complete Analysis Flow

1. **Create Session**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/session/create \
     -H "Content-Type: application/json" \
     -d '{"description": "Urban area analysis"}'
   ```
   Response: `{"session_id": "abc123", "created_at": "..."}`

2. **Upload Images**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/ingest/upload \
     -F "session_id=abc123" \
     -F "files=@image1.tif" \
     -F "files=@image2.tif"
   ```

3. **Plan Query** (Deterministic Planner)
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/query/analyze \
     -H "Content-Type: application/json" \
     -d '{
       "session_id": "abc123",
       "query": "Compute NDVI and detect vegetation changes between these two images"
     }'
   ```
   Response: Execution plan with required tools and steps

4. **Execute Plan** (Orchestrator)
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/query/orchestrate \
     -H "Content-Type: application/json" \
     -d '{
       "session_id": "abc123",
       "query": "Compute NDVI and detect vegetation changes between these two images"
     }'
   ```
   Response: Execution results, artifacts, and statistics

5. **Generate Report** (Report Generator)
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/query/report \
     -H "Content-Type: application/json" \
     -d '{
       "session_id": "abc123",
       "query": "Compute NDVI and detect vegetation changes between these two images"
     }'
   ```
   Response: Evidence-grounded final report with findings, quantitative results, and artifacts

---

## Architecture & Design Principles

### Deterministic Backend
- **Query Planner:** Translates natural-language queries into deterministic execution plans using rule-based pattern matching
- **Tool Registry:** Central registry of all available geospatial analysis tools
- **Orchestrator:** Executes plans step-by-step, collecting outputs into unified result structures
- **No Hidden Inference:** All analysis results are traceable to specific tool outputs or evidence

### Optional LLM/Vision Enhancements
- **Intent Detection:** LLM can suggest refined query intent to guide planner
- **Visual Reasoning:** Vision service can describe visible features and content
- **Evidence-grounded Responses:** All LLM responses reference tool outputs (no hallucination)

### Layered Abstractions
- **Schemas:** Pydantic models enforce API contracts
- **Endpoints:** RESTful interface to business logic
- **Services:** Reusable application logic (agent, orchestration, persistence)
- **Pipeline:** Deterministic geospatial algorithms
- **Geospatial:** Low-level GIS operations (validators, indices, analysis)

---

## Persistence Layer (M14)

### Database Models
- **SessionRecord:** Active session metadata and state
- **ImageRecord:** Ingested image metadata and file references
- **AnalysisRecord:** Analysis execution metadata
- **ExecutionRecord:** Per-step execution results
- **EvidenceRecord:** Execution evidence for report grounding
- **ArtifactRecord:** Generated artifact metadata and file paths
- **ReportRecord:** Final report metadata and content

### Storage Strategy
- **Metadata:** SQLAlchemy models in database (SQLite/MySQL)
- **Rasters & Files:** Filesystem storage with safe path resolution
- **References:** Stable IDs (session_id, image_id, analysis_id) for external integration

### Safe File Handling
- Path traversal prevention via `safe_filename()` and `safe_path()`
- Filename sanitization (removes unsafe characters)
- Session-scoped artifact access control
- Checksum computation for artifact integrity

---

## Testing Strategy

### Unit Tests
- Validators, metadata extractors, geospatial functions
- Individual schema compliance
- Edge cases (corrupt files, missing metadata, etc.)

### Integration Tests
- API endpoints with real FastAPI TestClient
- End-to-end session → upload → query → report flows
- Persistence regression coverage

### Fixtures
- Synthetic GeoTIFF rasters (georeferenced, multiple bands)
- Visual images (JPEG, PNG)
- Corrupted/invalid files for error handling

---


SatQuery AI – Smart India Hackathon 2026

---
T.Rushendar Reddy

AIML student 

Vignan university 
Hyderabad 
