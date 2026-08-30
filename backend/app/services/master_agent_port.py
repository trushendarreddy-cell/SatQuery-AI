"""Master Agent integration ports (M15).

Defines the stable contracts/protocols that the backend expects from
the team's Master Agent implementation.

These are not implementations; they are Protocol definitions that guide
how the team's code should be structured.

The backend never depends on specific Master Agent implementations.
Instead, it depends on these Protocols, which the team's code implements.
"""

from __future__ import annotations

from typing import Optional, Protocol, Dict, Any

from app.schemas.agent_integration_schema import (
    AgentContextData,
    AgentResponseData,
    SpecialistResultData,
)


class MasterAgentPort(Protocol):
    """Protocol that the team's Master Agent must implement.
    
    The backend depends on this contract, not on a specific implementation.
    The team's LangGraph workflow or other orchestrator should implement
    this Protocol.
    
    Usage:
        # Team's implementation
        class LangGraphMasterAgent:
            def run(self, ...) -> AgentResponseData:
                ...
        
        # Backend dependency injection
        master_agent: MasterAgentPort = LangGraphMasterAgent()
        backend.set_master_agent(master_agent)
    """

    def run(
        self,
        query: str,
        context: AgentContextData,
    ) -> AgentResponseData:
        """Run Master Agent on a user query.
        
        Args:
            query: User's natural language query
            context: Session context (images, artifacts, spatial info)
            
        Returns:
            AgentResponseData with findings, evidence, artifacts
            
        The Master Agent should:
        1. Classify the query intent
        2. Route to appropriate tools/specialists
        3. Execute via backend GIS services
        4. Ground findings in evidence
        5. Return structured AgentResponse
        """
        ...


class IntentClassifierPort(Protocol):
    """Protocol for intent classification.
    
    The Master Agent uses this to understand what the user wants.
    The backend provides context; the classifier returns structured intent.
    """

    def classify(
        self,
        query: str,
        context: AgentContextData,
    ) -> Dict[str, Any]:
        """Classify query intent.
        
        Returns dict with:
        {
            "task": "change",  # Main task
            "target": "building",  # What to analyze
            "modality": "optical",  # Which modality
            "requires_temporal_pair": true,
            "requires_cross_modal_pair": false,
            "ambiguous": false,
            "confidence": 0.95,
        }
        """
        ...


class SpecialistPort(Protocol):
    """Protocol for specialist tools (T1-T5).
    
    The Master Agent calls specialists via the backend.
    Each specialist implements this Protocol.
    """

    def execute(
        self,
        session_id: str,
        image_ids: list,
        query: str,
        parameters: Dict[str, Any],
    ) -> SpecialistResultData:
        """Execute specialist analysis.
        
        Args:
            session_id: Session identifier
            image_ids: Image IDs to process
            query: Original user query for context
            parameters: Tool-specific parameters
            
        Returns:
            SpecialistResultData with results, evidence, artifacts
        """
        ...


class ToolRouterPort(Protocol):
    """Protocol for tool routing/selection logic.
    
    Given a classified intent, the router decides which tools to invoke.
    """

    def route(
        self,
        intent: Dict[str, Any],
        context: AgentContextData,
    ) -> list:
        """Route intent to tools.
        
        Args:
            intent: Classified intent
            context: Session context
            
        Returns:
            List of tools to invoke, with parameters
            
        Example:
        [
            {"tool": "spectral_index", "params": {"index_type": "ndvi"}},
            {"tool": "change_detection", "params": {"threshold": 0.1}},
        ]
        """
        ...


class EvidenceGrounderPort(Protocol):
    """Protocol for grounding findings in evidence.
    
    Takes analysis results and creates Evidence items.
    """

    def ground(
        self,
        findings: list,
        execution_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Ground findings in evidence.
        
        Returns dict with evidence items and grounded findings.
        """
        ...


class SynthesisPort(Protocol):
    """Protocol for LLM synthesis of findings.
    
    After specialists execute, the synthesizer produces final response.
    """

    def synthesize(
        self,
        query: str,
        specialist_results: list,
        evidence: list,
    ) -> AgentResponseData:
        """Synthesize specialist results into final response.
        
        Returns AgentResponseData with natural language answer,
        findings, evidence, and confidence.
        """
        ...
