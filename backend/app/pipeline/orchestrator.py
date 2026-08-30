"""Analysis orchestration layer (M8).

Takes a validated query plan and executes the appropriate analysis operation
by dispatching each step through the existing agent tool registry.
No algorithms are reimplemented here -- every step calls an existing tool.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.agent.schemas import AgentToolCall, ToolStatus
from app.agent.query_intelligence import QueryIntelligenceService
from app.agent.tools import invoke_agent_tool
from app.core.session_cache import session_manager
from app.schemas.orchestration_schema import (
    ExecutionResult,
    ExecutionStep,
    ExecutionStepStatus,
    ExecutionStatus,
    OrchestrationResponse,
)
from app.schemas.query_schema import QueryIntent, QueryStatus
from app.pipeline.query_planner import QueryPlanner


class AnalysisOrchestrator:
    """Deterministic orchestrator: plan -> validate -> execute -> aggregate."""

    def __init__(self, intelligence_service: Optional[QueryIntelligenceService] = None):
        self.intelligence_service = intelligence_service or QueryIntelligenceService()

    def orchestrate(self, session_id: str, query: str, use_llm: bool = True) -> OrchestrationResponse:
        llm_interpretation = None
        llm_reason = None
        if use_llm:
            interpretation_response = self.intelligence_service.interpret(session_id, query, use_llm=True)
            llm_interpretation = interpretation_response.interpretation.model_dump(exclude_none=True)
            llm_reason = interpretation_response.fallback_reason

        intent_hint = None
        if llm_interpretation:
            try:
                intent_hint = self._query_intent_from_llm(llm_interpretation.get("analysis_type"))
            except Exception:
                intent_hint = None

        # 1. Plan (deterministic, LLM-free unless the structured intent was validated).
        plan_response = QueryPlanner.analyze(session_id, query, intent_hint=intent_hint)

        if plan_response.status == QueryStatus.ERROR:
            return OrchestrationResponse(
                execution=ExecutionResult(
                    session_id=session_id,
                    query=query,
                    intent=plan_response.intent,
                    status=ExecutionStatus.FAILED,
                    plan_steps=0,
                    message=plan_response.reasoning or "Session not found.",
                    errors=[plan_response.unsupported_reason or "Session not found."],
                    llm_interpretation=llm_interpretation,
                )
            )

        if plan_response.status == QueryStatus.NEEDS_MORE_IMAGES:
            return OrchestrationResponse(
                execution=ExecutionResult(
                    session_id=session_id,
                    query=query,
                    intent=plan_response.intent,
                    status=ExecutionStatus.FAILED,
                    plan_steps=0,
                    message=plan_response.reasoning or "No images available.",
                    errors=[plan_response.unsupported_reason or "No images available."],
                    llm_interpretation=llm_interpretation,
                )
            )

        if plan_response.status == QueryStatus.UNSUPPORTED or not plan_response.plan:
            return OrchestrationResponse(
                execution=ExecutionResult(
                    session_id=session_id,
                    query=query,
                    intent=plan_response.intent,
                    status=ExecutionStatus.FAILED,
                    plan_steps=0,
                    message=plan_response.reasoning or "Unsupported query.",
                    errors=[plan_response.unsupported_reason or "Unsupported intent."],
                    llm_interpretation=llm_interpretation,
                )
            )

        # 2. Pre-validate session + required images.
        precheck = self._prevalidate(session_id, query, plan_response.required_images)
        if precheck is not None:
            precheck.llm_interpretation = llm_interpretation
            return OrchestrationResponse(execution=precheck)

        # 3. Execute the plan step by step.
        execution = self._execute_plan(session_id, query, plan_response)
        execution.llm_interpretation = llm_interpretation
        return OrchestrationResponse(execution=execution)

    @staticmethod
    def _query_intent_from_llm(analysis_type: Optional[str]) -> Optional[QueryIntent]:
        mapping = {
            "ndvi": QueryIntent.VEGETATION_ANALYSIS,
            "savi": QueryIntent.VEGETATION_ANALYSIS,
            "ndbi": QueryIntent.VEGETATION_ANALYSIS,
            "change_detection": QueryIntent.CHANGE_DETECTION,
            "spatial_overlap": QueryIntent.SPATIAL_OVERLAP,
            "compatibility": QueryIntent.IMAGE_COMPARISON,
            "image_inspection": QueryIntent.IMAGE_INSPECTION,
            "metadata": QueryIntent.METADATA_QUESTION,
            "cloud_shadow_assessment": QueryIntent.CLOUD_SHADOW_ASSESSMENT,
            "area_calculation": QueryIntent.AREA_CALCULATION,
            "seasonal_risk": QueryIntent.BEFORE_AFTER_ANALYSIS,
            "unsupported": QueryIntent.UNSUPPORTED,
        }
        if not analysis_type:
            return None
        return mapping.get(str(analysis_type).lower())

    # ------------------------------------------------------------------
    # Pre-execution validation
    # ------------------------------------------------------------------
    def _prevalidate(self, session_id: str, query: str, required_image_ids: List[str]) -> Optional[ExecutionResult]:
        session = session_manager.get_session(session_id)
        if not session:
            return ExecutionResult(
                session_id=session_id,
                query=query,
                intent=QueryIntent.UNSUPPORTED,
                status=ExecutionStatus.FAILED,
                plan_steps=0,
                message=f"Session '{session_id}' not found.",
                errors=[f"Session '{session_id}' not found."],
            )

        available = set(session.images.keys())
        missing = [i for i in required_image_ids if i not in available]
        if missing:
            return ExecutionResult(
                session_id=session_id,
                query=query,
                intent=QueryIntent.UNSUPPORTED,
                status=ExecutionStatus.FAILED,
                plan_steps=0,
                message=f"Required images not found in session: {', '.join(missing)}",
                errors=[f"Missing image '{i}'." for i in missing],
            )

        return None

    # ------------------------------------------------------------------
    # Plan execution
    # ------------------------------------------------------------------
    def _execute_plan(self, session_id: str, query: str, plan_response) -> ExecutionResult:
        steps: List[ExecutionStep] = []
        all_warnings: List[str] = []
        all_errors: List[str] = []
        artifacts: List[Dict[str, Any]] = []
        statistics: Dict[str, Any] = {}

        succeeded = 0
        failed = 0
        skipped = 0
        stop = False

        for idx, plan_step in enumerate(plan_response.plan):
            if stop:
                steps.append(
                    ExecutionStep(
                        step_index=idx,
                        tool_name=plan_step.tool_name,
                        arguments=plan_step.arguments,
                        status=ExecutionStepStatus.SKIPPED,
                        message="Skipped because a prior step failed.",
                    )
                )
                skipped += 1
                continue

            args = dict(plan_step.arguments)
            args["session_id"] = session_id

            call = AgentToolCall(tool_name=plan_step.tool_name, arguments=args)
            tool_result = invoke_agent_tool(call)

            step_status = (
                ExecutionStepStatus.SUCCESS
                if tool_result.status == ToolStatus.SUCCESS
                else ExecutionStepStatus.FAILED
            )

            step = ExecutionStep(
                step_index=idx,
                tool_name=plan_step.tool_name,
                arguments=args,
                status=step_status,
                message=tool_result.message,
                error=tool_result.error,
                result=tool_result.result,
            )
            steps.append(step)

            if step_status == ExecutionStepStatus.SUCCESS:
                succeeded += 1
                self._collect_artifact(tool_result, artifacts)
                self._collect_statistics(tool_result, statistics)
                all_warnings.extend(tool_result.warnings or [])
            else:
                failed += 1
                all_errors.append(tool_result.error or tool_result.message or f"Step {idx} failed.")
                # Short-circuit: subsequent dependent steps cannot run.
                stop = True

        total = len(steps)
        if succeeded == total:
            overall = ExecutionStatus.SUCCESS
        elif succeeded == 0:
            overall = ExecutionStatus.FAILED
        else:
            overall = ExecutionStatus.PARTIAL

        summary = self._summarize(overall, plan_response, succeeded, failed, skipped)
        return ExecutionResult(
            session_id=session_id,
            query=query,
            intent=plan_response.intent,
            status=overall,
            plan_steps=total,
            steps_executed=succeeded + failed,
            steps_succeeded=succeeded,
            steps_failed=failed,
            steps_skipped=skipped,
            steps=steps,
            results=[s.result for s in steps],
            artifacts=artifacts,
            statistics=statistics,
            message=summary,
            warnings=sorted(set(all_warnings)),
            errors=all_errors,
        )

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------
    def _collect_artifact(self, tool_result, artifacts: List[Dict[str, Any]]) -> None:
        result = tool_result.result or {}
        if not result.get("success"):
            return
        # Tool wrappers nest the typed Pydantic result under a descriptive key.
        nested_keys = (
            "spectral_index",
            "change_detection",
            "cloud_mask",
            "seasonal_filter",
            "alignment",
            "clip",
            "overlap",
            "compatibility",
            "classification",
            "metadata",
            "geojson",
            "zonal_stats",
            "area",
        )
        nested: Dict[str, Any] = {}
        for key in nested_keys:
            value = result.get(key)
            if isinstance(value, dict):
                nested = value
                break

        artifact: Dict[str, Any] = {
            "tool_name": tool_result.tool_name,
            "session_id": result.get("session_id", ""),
        }
        found = False
        for key in (
            "artifact_filename",
            "index_image_id",
            "change_mask_image_id",
            "mask_image_id",
            "cloud_mask_image_id",
            "alignment_image_id",
            "clip_image_id_1",
            "clip_image_id_2",
        ):
            value = result.get(key) or nested.get(key)
            if value:
                artifact[key] = value
                found = True
        if found:
            artifacts.append(artifact)

    def _collect_statistics(self, tool_result, statistics: Dict[str, Any]) -> None:
        result = tool_result.result or {}
        if not result.get("success"):
            return
        nested_keys = (
            "spectral_index",
            "change_detection",
            "cloud_mask",
            "seasonal_filter",
            "alignment",
            "clip",
            "overlap",
            "compatibility",
            "classification",
            "metadata",
            "geojson",
            "zonal_stats",
            "area",
        )
        nested: Dict[str, Any] = {}
        for key in nested_keys:
            value = result.get(key)
            if isinstance(value, dict):
                nested = value
                break

        for key in (
            "valid_pixel_count",
            "nodata_pixel_count",
            "min_value",
            "max_value",
            "mean_value",
            "changed_pixel_count",
            "unchanged_pixel_count",
            "change_percentage",
            "changed_area_sqkm",
            "overlap_percentage",
            "cloud_percentage",
            "shadow_percentage",
            "area_m2",
            "area_hectares",
            "area_sqkm",
        ):
            if key in result:
                statistics[key] = result[key]
            elif key in nested:
                statistics[key] = nested[key]

    def _summarize(self, overall, plan_response, succeeded, failed, skipped) -> str:
        tool_names = [p.tool_name for p in plan_response.plan]
        if overall == ExecutionStatus.SUCCESS:
            return (
                f"Executed {succeeded} of {len(tool_names)} planned tool(s) "
                f"({', '.join(tool_names)}) successfully."
            )
        if overall == ExecutionStatus.PARTIAL:
            return (
                f"Executed {succeeded} of {len(tool_names)} planned tool(s); "
                f"{failed} failed, {skipped} skipped."
            )
        return (
            f"Execution failed: {failed} of {len(tool_names)} planned tool(s) "
            f"({', '.join(tool_names)}) did not succeed."
        )


orchestrator = AnalysisOrchestrator()


def orchestrate_analysis(session_id: str, query: str, use_llm: bool = True) -> OrchestrationResponse:
    """Plan + execute a natural-language analysis query."""
    return orchestrator.orchestrate(session_id, query, use_llm=use_llm)