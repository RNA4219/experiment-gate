"""Scoring engine for Experiment Gate.

Responsible for:
- Computing scores for 8 evaluation axes (0-20 each)
- Applying configurable weights
- Determining verdict based on thresholds (go_min: 70, hold_min: 45)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from experiment_gate.schemas import (
    GateRequest,
    GateResponse,
    NextStep,
    Rationale,
    ScoreBreakdown,
    Verdict,
    DecisionInfo,
    RunInfo,
    RunStatus,
)


# Default weights for scoring axes
DEFAULT_WEIGHTS = {
    "impact": 1.0,
    "feasibility": 1.0,
    "learning_value": 1.0,
    "reusability": 0.8,
    "time_to_signal": 0.8,
    "dependency_risk": 1.0,
    "operational_risk": 1.0,
    "novelty": 0.6,
}

# Default thresholds
DEFAULT_THRESHOLDS = {
    "go_min": 70,
    "hold_min": 45,
}


class ScoringConfig(BaseModel):
    """Configuration for scoring."""

    weights: dict[str, float] = Field(default_factory=lambda: DEFAULT_WEIGHTS.copy())
    thresholds: dict[str, int] = Field(default_factory=lambda: DEFAULT_THRESHOLDS.copy())


def compute_weighted_total(breakdown: ScoreBreakdown, weights: dict[str, float]) -> int:
    """Compute weighted total score from breakdown.

    Note: dependency_risk and operational_risk are inverse (lower is better),
    so they're subtracted from 20 before weighting.
    """
    raw_scores = {
        "impact": breakdown.impact,
        "feasibility": breakdown.feasibility,
        "learning_value": breakdown.learning_value,
        "reusability": breakdown.reusability,
        "time_to_signal": breakdown.time_to_signal,
        "dependency_risk": 20 - breakdown.dependency_risk,  # Inverse
        "operational_risk": 20 - breakdown.operational_risk,  # Inverse
        "novelty": breakdown.novelty,
    }

    total = 0.0
    total_weight = 0.0
    for axis, score in raw_scores.items():
        weight = weights.get(axis, 1.0)
        total += score * weight
        total_weight += weight

    if total_weight == 0:
        return 0

    # Normalize to 0-160 scale (8 axes * 20 points each)
    return int(total / total_weight * 8)


def determine_verdict(total_score: int, thresholds: dict[str, int]) -> Verdict:
    """Determine verdict based on total score and thresholds."""
    go_min = thresholds.get("go_min", 70)
    hold_min = thresholds.get("hold_min", 45)

    if total_score >= go_min:
        return Verdict.GO
    elif total_score >= hold_min:
        return Verdict.HOLD
    else:
        return Verdict.NO_GO


def generate_next_step(verdict: Verdict, rationale: Rationale) -> NextStep:
    """Generate recommended next step based on verdict and rationale."""
    if verdict == Verdict.GO:
        return NextStep(
            recommended_action="run_minimal_probe",
            minimal_probe="最小スコープでPoCを開始し、早期に信号を取得することを推奨"
        )
    elif verdict == Verdict.HOLD:
        if rationale.critical_uncertainties:
            return NextStep(
                recommended_action="gather_evidence",
                minimal_probe=f"以下の不確実性を解消してから再評価: {', '.join(rationale.critical_uncertainties[:3])}"
            )
        return NextStep(
            recommended_action="gather_evidence",
            minimal_probe="追加の根拠収集または前提の検証が必要"
        )
    else:
        return NextStep(
            recommended_action="reject",
            minimal_probe=None
        )


def compute_confidence(evidence_bundle: Any) -> float:
    """Compute confidence based on evidence quality."""
    if evidence_bundle is None:
        return 0.3

    claims = getattr(evidence_bundle, "claims", []) or []
    sources = getattr(evidence_bundle, "sources", []) or []
    gaps = getattr(evidence_bundle, "gaps", []) or []

    # Base confidence from claims and sources
    claim_score = min(1.0, len(claims) / 5.0) * 0.3
    source_score = min(1.0, len(sources) / 3.0) * 0.3

    # Penalty for gaps
    gap_penalty = min(0.3, len(gaps) * 0.1)

    confidence = 0.4 + claim_score + source_score - gap_penalty
    return max(0.1, min(1.0, confidence))


def build_reasoning_summary(
    verdict: Verdict,
    total_score: int,
    breakdown: ScoreBreakdown,
    rationale: Rationale
) -> str:
    """Build a concise reasoning summary."""
    verdict_text = {
        Verdict.GO: "GO判定",
        Verdict.HOLD: "HOLD判定",
        Verdict.NO_GO: "NO_GO判定"
    }

    top_strengths = []
    if breakdown.impact >= 15:
        top_strengths.append("高い影響度")
    if breakdown.feasibility >= 15:
        top_strengths.append("実現可能性が高い")
    if breakdown.learning_value >= 15:
        top_strengths.append("学習価値が高い")

    top_concerns = []
    if breakdown.dependency_risk >= 15:
        top_concerns.append("依存リスクが高い")
    if breakdown.operational_risk >= 15:
        top_concerns.append("運用リスクが高い")
    if breakdown.time_to_signal <= 10:
        top_concerns.append("信号取得まで時間がかかる")

    parts = [f"{verdict_text[verdict]} (スコア: {total_score}/160)"]

    if top_strengths:
        parts.append(f"強み: {', '.join(top_strengths)}")
    if top_concerns:
        parts.append(f"懸念: {', '.join(top_concerns)}")

    if rationale.why_now:
        parts.append(f"今やる理由: {rationale.why_now[0]}")

    return "。".join(parts)


def create_gate_response(
    request: GateRequest,
    score_breakdown: ScoreBreakdown,
    rationale: Rationale,
    config: ScoringConfig | None = None,
) -> GateResponse:
    """Create a GateResponse from scoring results."""
    if config is None:
        config = ScoringConfig()

    total_score = compute_weighted_total(score_breakdown, config.weights)
    verdict = determine_verdict(total_score, config.thresholds)
    confidence = compute_confidence(request.evidence_bundle)
    next_step = generate_next_step(verdict, rationale)
    reasoning_summary = build_reasoning_summary(verdict, total_score, score_breakdown, rationale)

    decision = DecisionInfo(
        verdict=verdict,
        total_score=total_score,
        confidence=confidence
    )

    run_info = RunInfo(
        run_id=f"run_{request.request_id}",
        request_id=request.request_id,
        mode="experiment_gate",
        status=RunStatus.COMPLETED,
        started_at=None,  # Will be set by runner
        applied_personas=[],
    )

    # Extract evidence refs
    evidence_refs = []
    if request.evidence_bundle:
        evidence_refs.extend(request.evidence_bundle.sources or [])

    return GateResponse(
        run=run_info,
        decision=decision,
        score_breakdown=score_breakdown,
        rationale=rationale,
        next_step=next_step,
        evidence_refs=evidence_refs,
        reasoning_summary=reasoning_summary
    )


# Default score breakdown for placeholder/fallback
def create_default_score_breakdown() -> ScoreBreakdown:
    """Create a default mid-range score breakdown."""
    return ScoreBreakdown(
        impact=10,
        feasibility=10,
        learning_value=10,
        reusability=10,
        time_to_signal=10,
        dependency_risk=10,
        operational_risk=10,
        novelty=10
    )


def create_default_rationale() -> Rationale:
    """Create a default rationale for placeholder/fallback."""
    return Rationale(
        why_now=["評価を実施して理由を生成する必要があります"],
        why_not_now=["詳細な評価が未実施"],
        critical_uncertainties=["PoCの詳細要件", "リソースの可用性"]
    )