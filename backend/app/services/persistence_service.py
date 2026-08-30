from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.db.models import AnalysisRecord, ArtifactRecord, EvidenceRecord, ExecutionRecord, ImageRecord, ReportRecord, SessionRecord


@contextmanager
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_session(session_id: str, status: str = "active") -> SessionRecord:
    with db_session() as db:
        session = db.get(SessionRecord, session_id)
        if session is None:
            session = SessionRecord(id=session_id, status=status)
            db.add(session)
            db.flush()
        else:
            session.updated_at = datetime.now(timezone.utc)
            session.status = status
        return session


def get_session(session_id: str) -> Optional[SessionRecord]:
    with db_session() as db:
        return db.get(SessionRecord, session_id)


def create_or_update_session(session_id: str, status: str = "active") -> SessionRecord:
    return ensure_session(session_id, status=status)


def create_image_record(
    *,
    session_id: str,
    original_filename: str,
    safe_filename: str,
    storage_key: str,
    file_type: str,
    file_size: int,
    checksum: Optional[str],
    metadata: Optional[dict[str, Any]] = None,
    image_id: Optional[str] = None,
) -> ImageRecord:
    image_uuid = image_id or uuid.uuid4().hex[:12]
    with db_session() as db:
        existing = db.get(ImageRecord, image_uuid)
        if existing is not None:
            return existing
        image = ImageRecord(
            id=image_uuid,
            session_id=session_id,
            original_filename=original_filename,
            safe_filename=safe_filename,
            storage_key=storage_key,
            file_type=file_type,
            file_size=file_size,
            checksum=checksum,
            image_metadata=metadata or {},
            image_category=(metadata or {}).get("category"),
            modality=(metadata or {}).get("modality"),
            acquisition_timestamp=(metadata or {}).get("acquisition_date"),
            crs=(metadata or {}).get("crs"),
            width=(metadata or {}).get("width"),
            height=(metadata or {}).get("height"),
            band_count=(metadata or {}).get("band_count"),
            resolution=(metadata or {}).get("resolution"),
            bounds=(metadata or {}).get("bounds"),
        )
        db.add(image)
        db.flush()
        return image


def get_image(image_id: str) -> Optional[ImageRecord]:
    with db_session() as db:
        return db.get(ImageRecord, image_id)


def get_images_for_session(session_id: str) -> list[ImageRecord]:
    with db_session() as db:
        return list(db.scalars(select(ImageRecord).where(ImageRecord.session_id == session_id)).all())


def get_image_metadata(image_id: str) -> Optional[dict[str, Any]]:
    image = get_image(image_id)
    if image is None:
        return None
    return {
        "id": image.id,
        "session_id": image.session_id,
        "original_filename": image.original_filename,
        "safe_filename": image.safe_filename,
        "storage_key": image.storage_key,
        "file_type": image.file_type,
        "file_size": image.file_size,
        "checksum": image.checksum,
        "category": image.image_category,
        "modality": image.modality,
        "acquisition_timestamp": image.acquisition_timestamp.isoformat() if image.acquisition_timestamp else None,
        "crs": image.crs,
        "width": image.width,
        "height": image.height,
        "band_count": image.band_count,
        "resolution": image.resolution,
        "bounds": image.bounds,
        "metadata": image.image_metadata,
    }


def create_analysis_record(session_id: str, query: str, intent: str, status: str = "pending", error_message: Optional[str] = None) -> AnalysisRecord:
    analysis_id = uuid.uuid4().hex[:12]
    with db_session() as db:
        analysis = AnalysisRecord(
            id=analysis_id,
            session_id=session_id,
            query=query,
            intent=intent,
            status=status,
            error_message=error_message,
        )
        db.add(analysis)
        db.flush()
        return analysis


def create_execution_record(analysis_id: str, tool_name: str, step: int, status: str = "pending", warnings: Optional[list[str]] = None, errors: Optional[list[str]] = None) -> ExecutionRecord:
    execution_id = uuid.uuid4().hex[:12]
    with db_session() as db:
        execution = ExecutionRecord(
            id=execution_id,
            analysis_id=analysis_id,
            tool_name=tool_name,
            step=step,
            status=status,
            warnings=warnings or [],
            errors=errors or [],
            started_at=datetime.now(timezone.utc),
        )
        db.add(execution)
        db.flush()
        return execution


def save_evidence_record(
    *,
    analysis_id: str,
    evidence_type: str,
    source: str,
    payload: dict[str, Any],
    confidence: Optional[float] = None,
    image_id: Optional[str] = None,
    artifact_id: Optional[str] = None,
) -> EvidenceRecord:
    evidence_id = uuid.uuid4().hex[:12]
    with db_session() as db:
        evidence = EvidenceRecord(
            id=evidence_id,
            analysis_id=analysis_id,
            evidence_type=evidence_type,
            source=source,
            payload=payload,
            confidence=confidence,
            image_id=image_id,
            artifact_id=artifact_id,
        )
        db.add(evidence)
        db.flush()
        return evidence


def save_artifact_record(
    *,
    session_id: str,
    artifact_type: str,
    filename: str,
    storage_key: str,
    mime_type: Optional[str] = None,
    file_size: int = 0,
    checksum: Optional[str] = None,
    analysis_id: Optional[str] = None,
    source_reference: Optional[str] = None,
) -> ArtifactRecord:
    artifact_id = uuid.uuid4().hex[:12]
    with db_session() as db:
        artifact = ArtifactRecord(
            id=artifact_id,
            session_id=session_id,
            analysis_id=analysis_id,
            artifact_type=artifact_type,
            filename=filename,
            storage_key=storage_key,
            mime_type=mime_type,
            file_size=file_size,
            checksum=checksum,
            source_reference=source_reference,
        )
        db.add(artifact)
        db.flush()
        return artifact


def get_artifact(artifact_id: str) -> Optional[ArtifactRecord]:
    with db_session() as db:
        return db.get(ArtifactRecord, artifact_id)


def get_artifacts_for_session(session_id: str) -> list[ArtifactRecord]:
    with db_session() as db:
        return list(db.scalars(select(ArtifactRecord).where(ArtifactRecord.session_id == session_id)).all())


def get_artifacts_for_analysis(analysis_id: str) -> list[ArtifactRecord]:
    with db_session() as db:
        return list(db.scalars(select(ArtifactRecord).where(ArtifactRecord.analysis_id == analysis_id)).all())


def get_artifact_by_session_and_name(session_id: str, filename: str) -> Optional[ArtifactRecord]:
    with db_session() as db:
        return db.scalar(
            select(ArtifactRecord).where(
                ArtifactRecord.session_id == session_id,
                ArtifactRecord.filename == filename,
            )
        )


def save_report_record(*, analysis_id: str, title: str, summary: str, report_payload: dict[str, Any], confidence: str = "unknown") -> ReportRecord:
    report_id = uuid.uuid4().hex[:12]
    with db_session() as db:
        report = ReportRecord(
            id=report_id,
            analysis_id=analysis_id,
            title=title,
            summary=summary,
            report_payload=report_payload,
            confidence=confidence,
        )
        db.add(report)
        db.flush()
        return report


def resolve_storage_path(storage_key: str) -> Path:
    root = Path(settings.STORAGE_ROOT).resolve()
    candidate = (root / storage_key).resolve()
    candidate.relative_to(root)
    return candidate


def build_storage_key(session_id: str, *parts: str) -> str:
    safe_parts = [part.strip("/") for part in parts if part]
    return "/".join(["sessions", session_id, *safe_parts])


def compute_checksum(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)
