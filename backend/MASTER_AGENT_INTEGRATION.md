# SatQuery AI — Master Agent Integration Guide (M15)

**Date:** August 30, 2026  
**Purpose:** Define stable contracts for integrating team's Master Agent with SatQuery backend  
**Status:** Ready for team implementation

---

## Overview

This document defines the **integration boundary** between:
- **SatQuery Backend** – Infrastructure, storage, GIS, persistence
- **Team Master Agent** – Intelligence, orchestration, routing, LLM

The backend is **NOT** the Master Agent. The backend is a **data and GIS service**.

The Master Agent **owns**:
- Intent classification
- Tool routing
- Specialist invocation
- LLM synthesis
- Reasoning and evidence grounding

The backend **owns**:
- Image ingestion and validation
- Session management
- Persistent storage
- GIS operations (spectral indices, change detection, etc.)
- Artifact management
- HTTP API

---

## Architecture

```
USER QUERY
    │
    ▼
FRONTEND
    │
    ▼
SATQUERY BACKEND (Ingest)
    ├── Session creation
    ├── Image upload
    └── Metadata extraction
    │
    ▼
AGENT CONTEXT API
    │
    ├── Images
    ├── Artifacts
    ├── Spatial compatibility
    └── CRS information
    │
    ▼
TEAM MASTER AGENT (Your Code)
    ├── Intent Classification
    ├── Tool Routing
    └── Specialist Invocation
    │
    ▼
SATQUERY BACKEND (GIS Services)
    ├── Spectral indices (NDVI, EVI, NDWI, SAVI, NDBI)
    ├── Change detection
    ├── Cloud masking
    ├── Zonal statistics
    ├── Area calculation
    └── Vectorization
    │
    ▼
BACKEND ADAPTERS
    ├── Evidence grounding
    ├── Response conversion
    └── Report generation
    │
    ▼
FINAL REPORT
    │
    ▼
FRONTEND
```

---

## Key Contracts

### 1. AgentContext — Backend → Master Agent

The Master Agent requests this once per session:

```python
GET /api/v1/agent/context/{session_id}
```

Response (Python Pydantic):

```python
from app.schemas.agent_integration_schema import AgentContextData

AgentContextData {
    session_id: str
    created_at: str  # ISO8601
    image_count: int
    images: [
        {
            image_id: str
            filename: str
            storage_key: str  # Safe reference (no filesystem paths)
            modality: "optical" | "sar" | "thermal" | ...
            timestamp: str | null
            crs: str | null  # e.g., "EPSG:4326"
            width: int | null
            height: int | null
            band_count: int | null
            bounds_wgs84: {minx, miny, maxx, maxy} | null
            metadata: {...}  # Full image metadata
        }
    ]
    modalities: [str]  # Unique modalities
    timestamps: [str]  # Unique timestamps
    spatial_context: {
        common_crs: str | null
        bounds_intersection: {minx, miny, maxx, maxy} | null
        all_georeferenced: bool
        compatible_for_temporal: bool  # Can compare images temporally
    }
    artifacts: [
        {
            artifact_id: str
            artifact_type: str
            filename: str
            storage_key: str
            file_size: int
            checksum: str | null
        }
    ]
    metadata: {...}
}
```

**Key points:**
- All file references are `storage_key`, not filesystem paths
- No sensitive information exposed
- CRS, timestamps, and modalities clearly listed
- Spatial compatibility pre-computed

**Usage in Master Agent:**

```python
from app.services.agent_context_service import AgentContextService

# Get session context
context = AgentContextService.get_agent_context(session_id)

# Now you can:
# 1. Check which modalities are available
# 2. Check CRS compatibility
# 3. Decide which tools to call
# 4. Resolve images for processing
```

---

### 2. MasterAgentPort — Protocol for Team's Implementation

The backend expects your Master Agent to implement this **Protocol**:

```python
from app.services.master_agent_port import MasterAgentPort
from app.schemas.agent_integration_schema import AgentContextData, AgentResponseData

class YourMasterAgent:
    """Implement this protocol."""
    
    def run(
        self,
        query: str,
        context: AgentContextData,
    ) -> AgentResponseData:
        """
        Args:
            query: User's natural language query
            context: Session context from backend
            
        Returns:
            AgentResponseData with findings, evidence, artifacts
        """
        # 1. Classify intent
        intent = self.classifier.classify(query, context)
        
        # 2. Route to tools
        tools = self.router.route(intent, context)
        
        # 3. Execute via backend
        results = []
        for tool in tools:
            result = self.backend_client.execute_tool(
                tool.name,
                session_id=context.session_id,
                parameters=tool.parameters,
            )
            results.append(result)
        
        # 4. Ground findings in evidence
        grounded_findings = self.grounder.ground(
            raw_findings=extract_findings(results),
            evidence=extract_evidence(results),
        )
        
        # 5. Synthesize to final response
        response = self.synthesizer.synthesize(
            query=query,
            findings=grounded_findings,
            evidence=extract_evidence(results),
        )
        
        return response  # AgentResponseData
```

**Register with backend:**

```python
from app.main import app
from your_code import LangGraphMasterAgent

master_agent = LangGraphMasterAgent()
app.state.master_agent = master_agent
```

---

### 3. AgentResponse — Master Agent → Backend

Your Master Agent returns this structure:

```python
from app.schemas.agent_integration_schema import AgentResponseData

AgentResponseData {
    session_id: str
    query: str
    answer: str  # Natural language response
    findings: [
        {
            text: str  # Human-readable finding
            evidence_ids: [str]  # References to evidence items
            confidence: str | null
        }
    ]
    quantitative_results: [
        {
            metric: str  # e.g., "mean_ndvi"
            value: float
            unit: str | null  # e.g., "index", "ha", "m2"
            evidence_ids: [str]
        }
    ]
    visual_observations: [str]  # Visual-only observations
    evidence: [
        {
            evidence_id: str
            evidence_type: "computed" | "visual" | "metadata" | "inference"
            source: str  # Tool or service that produced this
            value: any
            unit: str | null
            confidence: float | null  # 0.0-1.0
            artifact_id: str | null
            explanation: str | null
        }
    ]
    artifacts: [
        {
            artifact_id: str
            artifact_type: str
            filename: str
            storage_key: str
            file_size: int
        }
    ]
    limitations: [str]
    confidence: str  # "high", "medium", "low", "unknown"
    execution_trace: {...}  # Metadata about execution
}
```

**Key points:**
- Every finding **must** reference evidence
- Evidence types are explicit (computed vs. visual vs. inference)
- Inference **must** be marked as such, never hidden
- Artifacts use `storage_key`, not filesystem paths

---

### 4. Backend GIS Services — API for Specialists

The backend provides these endpoints for tool execution:

#### Spectral Index
```
POST /api/v1/analysis/spectral-index
{
    "session_id": "...",
    "image_id": "...",
    "index_type": "ndvi",  # or evi, ndwi, savi, ndbi
    "red_band": 3,
    "nir_band": 4,
    "blue_band": 1,  # optional
    "green_band": 2,  # optional
    "swir_band": 5  # optional
}
```

Response:
```
{
    "success": true,
    "index_image_id": "...",
    "artifact_filename": "...",
    "valid_pixel_count": 1000000,
    "min_value": -1.0,
    "max_value": 1.0,
    "mean_value": 0.65,
    "std_value": 0.15
}
```

#### Change Detection
```
POST /api/v1/analysis/change-detection
{
    "session_id": "...",
    "image_before_id": "...",
    "image_after_id": "...",
    "confidence_threshold": 0.7
}
```

Response:
```
{
    "success": true,
    "change_mask_id": "...",
    "change_pixels": 5000,
    "change_percentage": 5.0,
    "affected_area_ha": 50.0
}
```

#### Cloud Mask
```
POST /api/v1/analysis/cloud-mask
{
    "session_id": "...",
    "image_id": "..."
}
```

Response:
```
{
    "success": true,
    "mask_id": "...",
    "cloud_fraction": 0.1,
    "shadow_fraction": 0.05,
    "clear_fraction": 0.85
}
```

#### Area Calculation
```
POST /api/v1/analysis/area
{
    "geojson": {...}  # GeoJSON Feature, Polygon, or FeatureCollection
}
```

Response:
```
{
    "success": true,
    "area_m2": 100000.0,
    "area_ha": 10.0,
    "area_sqkm": 0.1
}
```

**All existing endpoints at `/api/v1/analysis/` remain unchanged.**

---

## Integration Steps

### For Team Master Agent Implementation:

1. **Implement MasterAgentPort**
   ```python
   class LangGraphMasterAgent:
       def run(self, query: str, context: AgentContextData) -> AgentResponseData:
           # Your LangGraph implementation
           pass
   ```

2. **Get AgentContext**
   ```python
   context = AgentContextService.get_agent_context(session_id)
   ```

3. **Classify Intent**
   - Use query + context to determine what needs to be done
   - Decide if it's change detection, vegetation analysis, etc.

4. **Route to Specialists**
   - Each specialist (T1–T5) executes via backend endpoints
   - Collect results and evidence

5. **Ground Findings**
   - Map results to Evidence items
   - Ensure every finding has evidence

6. **Synthesize Response**
   - Combine findings into natural language
   - Return AgentResponseData

7. **Backend Adapts to Report**
   ```python
   from app.services.integration_adapter import AgentResponseAdapter
   
   report = AgentResponseAdapter.to_report(agent_response, original_query)
   # Report is now compatible with /api/v1/query/report
   ```

---

## Evidence Grounding Contract

**Critical:** Every finding must be grounded.

### Evidence Types

**Computed** (from deterministic GIS)
```
{
    "evidence_type": "computed",
    "source": "backend.spectral_index",
    "value": 0.75,
    "unit": "ndvi",
    "confidence": 0.95
}
```

**Visual** (from vision model or human)
```
{
    "evidence_type": "visual",
    "source": "T1_VQA",
    "observation": "Green vegetation visible",
    "confidence": 0.80
}
```

**Metadata** (from image metadata)
```
{
    "evidence_type": "metadata",
    "source": "image_metadata",
    "field": "crs",
    "value": "EPSG:4326"
}
```

**Inference** (from LLM or reasoning)
```
{
    "evidence_type": "inference",
    "source": "llm_synthesis",
    "observation": "Likely caused by urban expansion",
    "confidence": 0.60
}
```

**Never hide inference as computed. Always mark it explicitly.**

---

## Security & Safety

### Path Traversal Prevention
- All file references use `storage_key`, not filesystem paths
- Backend prevents `../`, `C:\`, `/etc/`, etc.
- Images and artifacts are session-scoped

### Safe Image Access
```python
from app.services.agent_context_service import ImageAccessService

# Safe access
path = ImageAccessService.resolve_image(session_id, image_id)
# Returns Path within session_dir, or raises ValueError if traversal attempted
```

### Safe Artifact Access
```python
from app.services.agent_context_service import ArtifactAccessService

# Safe download
path = ArtifactAccessService.download_artifact(session_id, artifact_id)
# Returns Path within session_dir, or raises ValueError if traversal attempted
```

---

## API Endpoints for Master Agent Integration

### New Endpoints (M15)

```
GET /api/v1/agent/context/{session_id}
    Returns: AgentContextData
    Purpose: Get session context for decision making

POST /api/v1/agent/response/{session_id}
    Body: AgentResponseData
    Returns: Report
    Purpose: Submit Master Agent response, get adapted Report
```

### Existing Endpoints (Used by Master Agent)

```
All /api/v1/analysis/* endpoints remain unchanged
All /api/v1/spatial/* endpoints remain unchanged
All /api/v1/session/* endpoints remain unchanged
```

---

## Database Support

The backend works with:
- **SQLite** for development/testing
- **MySQL** for production team deployment

Set `DATABASE_URL`:
```env
# Development
DATABASE_URL=sqlite:///satquery.db

# Production
DATABASE_URL=mysql+pymysql://user:password@localhost/satquery
```

---

## Testing the Integration

### Mock Master Agent (Included in Backend)

```python
from tests.test_agent_integration import TestMasterAgentIntegration

# Runs full mock flow:
# 1. Create session
# 2. Get AgentContext
# 3. Master Agent processes (mock)
# 4. Convert AgentResponse to Report
# 5. Verify evidence grounding
```

Run tests:
```bash
pytest tests/test_agent_integration.py -v
```

---

## What NOT To Do

**DO NOT:**
- Reimplement spectral index, change detection, or GIS in Master Agent
- Create another database or storage system
- Duplicate image validation or metadata extraction
- Hardcode filesystem paths
- Break existing `/api/v1/query/` endpoints

**DO:**
- Call existing `/api/v1/analysis/` endpoints
- Use AgentContext to make decisions
- Ground all findings in evidence
- Use adapters to convert responses
- Test via mock Master Agent

---

## Regression Guarantee

The backend regression test suite remains at **227 tests passing**.

Adding Master Agent integration:
- ✅ Does NOT break existing tests
- ✅ Adds new integration contract tests
- ✅ Preserves M1–M14 functionality
- ✅ Maintains backward compatibility

```bash
pytest -q
# Expected: 227 passed, X new passed (integration tests)
```

---

## File Reference

### New Files Added (M15)

```
app/schemas/agent_integration_schema.py
    └─ AgentContextData, AgentResponseData, Evidence, etc.

app/services/agent_context_service.py
    └─ AgentContextService, ImageAccessService, ArtifactAccessService

app/services/master_agent_port.py
    └─ MasterAgentPort and other Protocol definitions

app/services/integration_adapter.py
    └─ AgentResponseAdapter, EvidenceAdapter, SpecialistExecutionAdapter

tests/test_agent_integration.py
    └─ Integration contract tests + mock Master Agent
```

### Updated Files

```
app/main.py
    └─ Added new agent context endpoints (if needed)

requirements.txt
    └─ No new dependencies required
```

---

## Next Steps for Team

1. **Read this document completely**
2. **Implement MasterAgentPort in your code**
3. **Test with mock AgentContext** (see test file)
4. **Call backend endpoints** for GIS operations
5. **Return AgentResponseData** structured correctly
6. **Backend adapts to Report** automatically

---

## Contact & Support

If integration questions arise:
- Inspect `app/services/agent_context_service.py` for context generation
- Inspect `app/services/master_agent_port.py` for contracts
- Inspect `tests/test_agent_integration.py` for examples
- Inspect `app/schemas/agent_integration_schema.py` for data structures

**Bottom line:** Backend is infrastructure. Master Agent is intelligence. Keep them separate.
