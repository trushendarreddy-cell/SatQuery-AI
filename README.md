# SatQuery AI — Satellite Analysis Backend

SatQuery AI is an AI-assisted interface for working with satellite imagery through natural language.

The backend exists to turn a user request into an analysis workflow instead of forcing the user to manually move between imagery, computer-vision tools, and model outputs.

## What the system is for

A useful satellite-analysis workflow needs more than a chatbot. It needs to connect a question to imagery, run the appropriate analysis, and return an answer that can be inspected against the source data.

The project is being developed around that idea:

```text
Natural-language query
        ↓
 Query understanding
        ↓
 Analysis / tool selection
        ↓
 Satellite imagery + vision models
        ↓
 Evidence / structured result
        ↓
 User-facing answer
```

The intended analysis layer includes visual question answering, image captioning, comparison of observations across time, and change-focused reasoning.

## My contribution

My work on the project has focused on the AI/ML and Python side of the system, including query processing, API integration, analysis orchestration, multimodal model integration, computer-vision workflows, and agent-style tool coordination.

The repository is part of a larger team project, so the frontend and other components are maintained separately.

## Current system direction

The project is being developed as a set of services rather than one large application. This makes it possible to test the model and analysis layer independently before connecting it to the complete interface.

The companion frontend repository contains the dashboard and local GeoChat integration used during development.

## Project status

SatQuery is an active Smart India Hackathon 2026 project and is still evolving. Some analysis capabilities are working independently while the complete query-to-insight pipeline continues to be integrated.

The repository should therefore be read as an active engineering project, not as a claim that every planned satellite-analysis capability is production-ready.

## Running it

### Requirements

- Python 3.11 or newer
- No database server is needed. SQLite is created on first run under `backend/temp/`.

### Install and run

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is then on `http://localhost:8000`, with interactive docs at `/docs`
and a health check at `/health`.

`temp/` is created automatically. It is gitignored, so a fresh checkout needs
no setup step.

### Tests

```bash
cd backend
pytest -q
```

258 tests covering GeoTIFF validation, spectral indices, cloud masking,
change detection, alignment, zonal statistics, the agent tooling, and
persistence. CI runs the suite on every push.

### Endpoints

Everything is mounted under `/api/v1`:

| Group | Prefix | Purpose |
|---|---|---|
| Ingest | `/ingest` | Upload and profile a raster or photograph |
| Session | `/session` | Scene classification and session state |
| Spatial | `/spatial` | CRS alignment and compatibility checks |
| Analysis | `/analysis` | Spectral indices, cloud mask, seasonal filter, area, zonal stats |
| Query | `/query` | Query planning, orchestration, reports |
| Agent | `/agent` | Agent context and tool invocation |

### Configuration

All optional. Without keys the deterministic geospatial endpoints still work;
the model-backed query and vision paths need a provider.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Override the SQLite path |
| `LLM_PROVIDER` | `openai` (default), `gemini`, or `ollama` |
| `LLM_API_KEY` | Key for the chosen provider |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins |

## Tech direction

- Python
- FastAPI
- AI agents / workflow orchestration
- Multimodal language models
- Computer vision
- Satellite / geospatial imagery
- REST APIs

## Related frontend

The dashboard and local vision-language interface are maintained in the **SatQuery-AI-fronend-v4** repository.

## Author

**T. Rushendar Reddy**  
Artificial Intelligence and Machine Learning  
Hyderabad, India
