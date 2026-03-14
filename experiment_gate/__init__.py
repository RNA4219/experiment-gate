"""Experiment Gate - A hypothesis evaluation agent.

This package provides tools for evaluating hypotheses and PoC proposals,
deciding "is it worth trying now?" based on evidence and multi-perspective analysis.
"""

__version__ = "0.1.0"

from experiment_gate.pipeline import (
    run_insight,
    run_insight_result,
    run_pipeline,
    run_pipeline_async,
    run_pipeline_result,
    run_pipeline_result_async,
)
from experiment_gate.result_formatter import build_agent_result
from experiment_gate.runner import run, run_async, run_gate, run_gate_async
from experiment_gate.runtime_config import RuntimeConfig, load_runtime_config
from experiment_gate.schemas import (
    AssumptionItem,
    ClaimItem,
    Constraints,
    Decision,
    DecisionInfo,
    DerivationType,
    EpistemicMode,
    EvidenceBundle,
    EvidenceRef,
    FailureItem,
    GateRequest,
    GateResponse,
    InsightItem,
    InsightRequest,
    InsightResponse,
    JapaneseSummary,
    LimitationItem,
    NextStep,
    NormalizedRequest,
    OpenQuestionItem,
    PersonaDefinition,
    PersonaScore,
    PocSpec,
    ProblemCandidateItem,
    Rationale,
    ReasoningSummary,
    RunInfo,
    RunStatus,
    ScoreBreakdown,
    Source,
    SourceUnit,
    UpdateRule,
    Verdict,
)
from experiment_gate.scorer import ScoringConfig

__all__ = [
    # Main API
    "run",
    "run_async",
    "run_gate",
    "run_gate_async",
    "__version__",
    # Legacy pipeline
    "run_pipeline",
    "run_pipeline_async",
    "run_pipeline_result",
    "run_pipeline_result_async",
    "run_insight",
    "run_insight_result",
    "build_agent_result",
    # Config
    "RuntimeConfig",
    "load_runtime_config",
    "ScoringConfig",
    # Gate schemas
    "GateRequest",
    "GateResponse",
    "PocSpec",
    "EvidenceBundle",
    "Verdict",
    "ScoreBreakdown",
    "Rationale",
    "NextStep",
    "DecisionInfo",
    # Legacy schemas
    "InsightRequest",
    "InsightResponse",
    "NormalizedRequest",
    "RunInfo",
    "Source",
    "SourceUnit",
    "Constraints",
    "ClaimItem",
    "AssumptionItem",
    "LimitationItem",
    "ProblemCandidateItem",
    "InsightItem",
    "OpenQuestionItem",
    "EvidenceRef",
    "FailureItem",
    "PersonaDefinition",
    "PersonaScore",
    "EpistemicMode",
    "DerivationType",
    "UpdateRule",
    "Decision",
    "RunStatus",
    "JapaneseSummary",
    "ReasoningSummary",
]
