"""Experiment Gate public package surface."""

__version__ = "0.1.0"

from experiment_gate.runner import run_gate, run_gate_async
from experiment_gate.schemas import (
    DecisionInfo,
    EvidenceBundle,
    GateRequest,
    GateResponse,
    NextStep,
    PocSpec,
    Rationale,
    RunInfo,
    RunStatus,
    ScoreBreakdown,
    Verdict,
)
from experiment_gate.scorer import ScoringConfig, load_scoring_config

__all__ = [
    "__version__",
    "run_gate",
    "run_gate_async",
    "load_scoring_config",
    "ScoringConfig",
    "GateRequest",
    "GateResponse",
    "PocSpec",
    "EvidenceBundle",
    "Verdict",
    "ScoreBreakdown",
    "Rationale",
    "NextStep",
    "DecisionInfo",
    "RunInfo",
    "RunStatus",
]
