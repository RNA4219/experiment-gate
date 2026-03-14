"""Scoring engine for Experiment Gate.

Responsible for:
- Computing scores for 8 evaluation axes (0-20 each)
- Applying configurable weights
- Determining verdict based on thresholds (go_min: 70, hold_min: 45)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional until config file is used
    yaml = None

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

DEFAULT_GATE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "defaults.yaml"


class ScoringConfig(BaseModel):
    """Configuration for scoring."""

    weights: dict[str, float] = Field(default_factory=lambda: DEFAULT_WEIGHTS.copy())
    thresholds: dict[str, int] = Field(default_factory=lambda: DEFAULT_THRESHOLDS.copy())


def compute_weighted_total(breakdown: ScoreBreakdown, weights: dict[str, float]) -> int:
    """Compute weighted total score from breakdown."""
    raw_scores = {
        "impact": breakdown.impact,
        "feasibility": breakdown.feasibility,
        "learning_value": breakdown.learning_value,
        "reusability": breakdown.reusability,
        "time_to_signal": breakdown.time_to_signal,
        "dependency_risk": breakdown.dependency_risk,
        "operational_risk": breakdown.operational_risk,
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
        top_concerns.append("依存リスクが低い")
    if breakdown.operational_risk >= 15:
        top_concerns.append("運用リスクが低い")
    if breakdown.time_to_signal <= 10:
        top_concerns.append("信号取得まで時間がかかる")

    parts = [f"{verdict_text[verdict]} (スコア: {total_score}/160)"]

    if top_strengths:
        parts.append(f"強み: {', '.join(top_strengths)}")
    if top_concerns:
        parts.append(f"補足: {', '.join(top_concerns)}")

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


def create_default_score_breakdown() -> ScoreBreakdown:
    """Create a conservative fallback score breakdown."""
    return ScoreBreakdown(
        impact=6,
        feasibility=6,
        learning_value=6,
        reusability=6,
        time_to_signal=6,
        dependency_risk=6,
        operational_risk=6,
        novelty=6
    )


def create_default_rationale() -> Rationale:
    """Create a default rationale for placeholder/fallback."""
    return Rationale(
        why_now=["評価を実施して理由を生成する必要があります"],
        why_not_now=["詳細な評価が未実施"],
        critical_uncertainties=["PoCの詳細要件", "リソースの可用性"]
    )


def create_failure_rationale(reason: str | None = None) -> Rationale:
    """Create a rationale for infrastructure or evaluation failures."""
    message = reason or "LLM評価を完了できませんでした"
    return Rationale(
        why_now=[],
        why_not_now=["評価基盤の状態が不安定なため判定を保留"],
        critical_uncertainties=[message],
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _load_mapping_file(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    text = config_path.read_text(encoding="utf-8")
    suffix = config_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML config files")
        data = yaml.safe_load(text) or {}
    else:
        raise ValueError(f"Unsupported config file format: {config_path}")
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a mapping at the top level")
    return data


def _normalize_scoring_config(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return {}
    if "gate" in data:
        gate = data.get("gate") or {}
        if not isinstance(gate, dict):
            raise ValueError("gate config must be a mapping")
        scoring = gate.get("scoring") or {}
        if not isinstance(scoring, dict):
            raise ValueError("gate.scoring config must be a mapping")
        return scoring
    if "scoring" in data:
        scoring = data.get("scoring") or {}
        if not isinstance(scoring, dict):
            raise ValueError("scoring config must be a mapping")
        return scoring
    return data


def _config_from_set_values(set_values: list[str] | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in set_values or []:
        if "=" not in item:
            raise ValueError(f"Override must be in key=value format: {item}")
        key, raw_value = item.split("=", 1)
        parts = [part for part in key.split(".") if part]
        if parts[:2] == ["gate", "scoring"]:
            parts = parts[2:]
        elif parts[:1] == ["scoring"]:
            parts = parts[1:]
        if not parts:
            raise ValueError(f"Override key is empty: {item}")
        current: dict[str, Any] = {}
        cursor = current
        for part in parts[:-1]:
            next_cursor: dict[str, Any] = {}
            cursor[part] = next_cursor
            cursor = next_cursor
        cursor[parts[-1]] = _parse_scalar(raw_value)
        merged = _deep_merge(merged, current)
    return merged


def load_scoring_config(
    *,
    config: ScoringConfig | None = None,
    config_dict: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    set_values: list[str] | None = None,
) -> ScoringConfig:
    """Load Gate scoring config from defaults, file, dict, and CLI overrides."""
    if config is not None:
        base = config.model_dump(mode="json")
    else:
        base = ScoringConfig().model_dump(mode="json")

    merged = dict(base)
    if DEFAULT_GATE_CONFIG_PATH.exists():
        merged = _deep_merge(merged, _normalize_scoring_config(_load_mapping_file(DEFAULT_GATE_CONFIG_PATH)))
    if config_path is not None:
        merged = _deep_merge(merged, _normalize_scoring_config(_load_mapping_file(config_path)))
    if config_dict:
        merged = _deep_merge(merged, _normalize_scoring_config(config_dict))
    merged = _deep_merge(merged, _config_from_set_values(set_values))
    return ScoringConfig.model_validate(merged)
