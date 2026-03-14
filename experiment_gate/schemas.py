"""Schema definitions for Experiment Gate."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """実行ステータス."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class PersonaDefinition(BaseModel):
    """Gate Persona 定義."""

    persona_id: str
    name: str
    role: str | None = None
    description: str | None = None
    obsession: str | None = None
    blind_spot: str | None = None
    objective: str
    priorities: list[str] = Field(default_factory=list)
    penalties: list[str] = Field(default_factory=list)
    time_horizon: str | None = None
    risk_tolerance: str | None = None
    evidence_preference: str | None = None
    key_questions: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    trigger_signals: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    optional_notes: list[str] = Field(default_factory=list)
    synthesis_style: str | None = None
    acceptance_rule: str
    weight: float = Field(default=1.0, ge=0.0)


class Constraints(BaseModel):
    """Gate 用の制約条件."""

    domain: str | None = None
    max_problem_candidates: int = 5
    max_insights: int = 3
    primary_persona: str | None = None


class RunInfo(BaseModel):
    """実行情報."""

    run_id: str
    request_id: str | None = None
    mode: str = "experiment_gate"
    status: RunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    applied_personas: list[str] = Field(default_factory=list)
    persona_source: str = "default"
    persona_catalog_version: str | None = None


class Verdict(str, Enum):
    """判定ラベル."""

    GO = "go"
    HOLD = "hold"
    NO_GO = "no_go"


class PocSpec(BaseModel):
    """最小PoC仕様."""

    objective: str = Field(description="目的")
    problem: str = Field(description="解決する問題")
    target_user_or_context: str = Field(description="対象ユーザー/コンテキスト")
    success_metrics: list[str] = Field(default_factory=list, description="成功指標")
    failure_or_abort_criteria: list[str] = Field(default_factory=list, description="失敗/中止基準")
    minimum_scope: str = Field(description="最小スコープ")
    non_goals: list[str] = Field(default_factory=list, description="非対象")
    required_inputs_or_tools: list[str] = Field(default_factory=list, description="必要な入力/ツール")
    validation_plan: str = Field(description="検証計画")


class EvidenceBundle(BaseModel):
    """根拠束."""

    claims: list[str] = Field(default_factory=list, description="主張")
    sources: list[str] = Field(default_factory=list, description="ソース")
    confidence_notes: list[str] | None = Field(default=None, description="信頼度注記")
    gaps: list[str] | None = Field(default=None, description="ギャップ")


class GateRequest(BaseModel):
    """実験ゲート リクエスト."""

    mode: str = "experiment_gate"
    request_id: str
    hypothesis: str = Field(description="仮説")
    poc_spec: PocSpec = Field(description="最小PoC仕様")
    evidence_bundle: EvidenceBundle = Field(description="根拠束")
    constraints: Constraints | None = Field(default=None, description="制約条件")
    assumptions: list[str] | None = Field(default=None, description="前提")
    known_risks: list[str] | None = Field(default=None, description="既知リスク")
    decision_context: str | None = Field(default=None, description="判断コンテキスト")
    config_override: dict[str, Any] | None = Field(default=None, description="設定オーバーライド")


class ScoreBreakdown(BaseModel):
    """評価軸ごとのスコア (各0-20点)."""

    impact: int = Field(ge=0, le=20, description="影響度")
    feasibility: int = Field(ge=0, le=20, description="実現可能性")
    learning_value: int = Field(ge=0, le=20, description="学習価値")
    reusability: int = Field(ge=0, le=20, description="再利用性")
    time_to_signal: int = Field(ge=0, le=20, description="信号までの時間")
    dependency_risk: int = Field(ge=0, le=20, description="依存リスク (低いほど良い)")
    operational_risk: int = Field(ge=0, le=20, description="運用リスク (低いほど良い)")
    novelty: int = Field(ge=0, le=20, description="新規性")


class Rationale(BaseModel):
    """判定理由."""

    why_now: list[str] = Field(default_factory=list, description="今やるべき理由")
    why_not_now: list[str] = Field(default_factory=list, description="今やるべきでない理由")
    critical_uncertainties: list[str] = Field(default_factory=list, description="重要な不確実性")


class NextStep(BaseModel):
    """次アクション."""

    recommended_action: str = Field(description="推奨アクション: run_minimal_probe, gather_evidence, defer, reject")
    minimal_probe: str | None = Field(default=None, description="最小プローブの提案")


class DecisionInfo(BaseModel):
    """判定情報."""

    verdict: Verdict = Field(description="判定結果")
    total_score: int = Field(ge=0, le=160, description="総合スコア")
    confidence: float = Field(ge=0.0, le=1.0, description="信頼度")


class GateResponse(BaseModel):
    """実験ゲート レスポンス."""

    run: RunInfo = Field(description="実行情報")
    decision: DecisionInfo = Field(description="判定情報")
    score_breakdown: ScoreBreakdown = Field(description="スコア内訳")
    rationale: Rationale = Field(description="判定理由")
    next_step: NextStep = Field(description="次アクション")
    evidence_refs: list[str] = Field(default_factory=list, description="根拠参照")
    reasoning_summary: str = Field(description="推論要約")
