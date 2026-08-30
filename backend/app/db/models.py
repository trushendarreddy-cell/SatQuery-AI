from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    session_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True, default=dict)

    images: Mapped[list["ImageRecord"]] = relationship(back_populates="session")
    analyses: Mapped[list["AnalysisRecord"]] = relationship(back_populates="session")
    artifacts: Mapped[list["ArtifactRecord"]] = relationship(back_populates="session")


class ImageRecord(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    image_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    modality: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    acquisition_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    crs: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    band_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bounds: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    image_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    session: Mapped[SessionRecord] = relationship(back_populates="images")
    evidences: Mapped[list["EvidenceRecord"]] = relationship(back_populates="image")


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    session: Mapped[SessionRecord] = relationship(back_populates="analyses")
    executions: Mapped[list["ExecutionRecord"]] = relationship(back_populates="analysis")
    evidences: Mapped[list["EvidenceRecord"]] = relationship(back_populates="analysis")
    artifacts: Mapped[list["ArtifactRecord"]] = relationship(back_populates="analysis")
    reports: Mapped[list["ReportRecord"]] = relationship(back_populates="analysis")


class ExecutionRecord(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    warnings: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True, default=list)
    errors: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True, default=list)

    analysis: Mapped[AnalysisRecord] = relationship(back_populates="executions")


class EvidenceRecord(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    image_id: Mapped[Optional[str]] = mapped_column(ForeignKey("images.id"), nullable=True, index=True)
    artifact_id: Mapped[Optional[str]] = mapped_column(ForeignKey("artifacts.id"), nullable=True, index=True)

    analysis: Mapped[AnalysisRecord] = relationship(back_populates="evidences")
    image: Mapped[Optional["ImageRecord"]] = relationship(back_populates="evidences")
    artifact: Mapped[Optional["ArtifactRecord"]] = relationship(back_populates="evidence_records")


class ArtifactRecord(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    analysis_id: Mapped[Optional[str]] = mapped_column(ForeignKey("analyses.id"), nullable=True, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    session: Mapped[SessionRecord] = relationship(back_populates="artifacts")
    analysis: Mapped[Optional[AnalysisRecord]] = relationship(back_populates="artifacts")
    evidence_records: Mapped[list[EvidenceRecord]] = relationship(back_populates="artifact")


class ReportRecord(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    report_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    analysis: Mapped[AnalysisRecord] = relationship(back_populates="reports")
