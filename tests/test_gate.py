"""Tests for Experiment Gate functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiment_gate.schemas import (
    Constraints,
    EvidenceBundle,
    GateRequest,
    GateResponse,
    PocSpec,
    Rationale,
    ScoreBreakdown,
    Verdict,
    DecisionInfo,
    NextStep,
    RunInfo,
    RunStatus,
)
from experiment_gate.scorer import (
    ScoringConfig,
    compute_weighted_total,
    determine_verdict,
    generate_next_step,
    create_gate_response,
    create_default_score_breakdown,
    create_default_rationale,
)
from experiment_gate.runner import run_gate, load_gate_request


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_poc_spec() -> PocSpec:
    return PocSpec(
        objective="テスト目的",
        problem="テスト問題",
        target_user_or_context="テストユーザー",
        success_metrics=["指標1"],
        failure_or_abort_criteria=["失敗基準1"],
        minimum_scope="最小スコープ",
        non_goals=["非目標1"],
        required_inputs_or_tools=["ツール1"],
        validation_plan="検証計画"
    )


@pytest.fixture
def sample_evidence_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        claims=["主張1", "主張2"],
        sources=["ソース1"],
        confidence_notes=["信頼度注記"],
        gaps=["ギャップ1"]
    )


@pytest.fixture
def sample_gate_request(sample_poc_spec: PocSpec, sample_evidence_bundle: EvidenceBundle) -> GateRequest:
    return GateRequest(
        request_id="req_test_001",
        hypothesis="テスト仮説",
        poc_spec=sample_poc_spec,
        evidence_bundle=sample_evidence_bundle,
        constraints=Constraints(domain="test"),
        assumptions=["前提1"],
        known_risks=["リスク1"],
        decision_context="テストコンテキスト"
    )


@pytest.fixture
def sample_score_breakdown() -> ScoreBreakdown:
    return ScoreBreakdown(
        impact=15,
        feasibility=14,
        learning_value=12,
        reusability=10,
        time_to_signal=13,
        dependency_risk=8,
        operational_risk=7,
        novelty=11
    )


@pytest.fixture
def sample_rationale() -> Rationale:
    return Rationale(
        why_now=["理由1", "理由2"],
        why_not_now=["懸念1"],
        critical_uncertainties=["不確実性1"]
    )


# ============================================================================
# GateRequest Validation Tests
# ============================================================================


class TestGateRequestValidation:
    """Tests for GateRequest model validation."""

    def test_gate_request_creation(self, sample_gate_request: GateRequest):
        """Test that a valid GateRequest can be created."""
        assert sample_gate_request.mode == "experiment_gate"
        assert sample_gate_request.request_id == "req_test_001"
        assert sample_gate_request.hypothesis == "テスト仮説"
        assert sample_gate_request.poc_spec.objective == "テスト目的"

    def test_gate_request_optional_fields(self, sample_poc_spec: PocSpec, sample_evidence_bundle: EvidenceBundle):
        """Test that optional fields can be None."""
        request = GateRequest(
            request_id="req_minimal",
            hypothesis="最小仮説",
            poc_spec=sample_poc_spec,
            evidence_bundle=sample_evidence_bundle
        )
        assert request.constraints is None
        assert request.assumptions is None
        assert request.known_risks is None
        assert request.decision_context is None
        assert request.config_override is None

    def test_gate_request_from_dict(self):
        """Test creating GateRequest from dictionary."""
        data = {
            "mode": "experiment_gate",
            "request_id": "req_dict",
            "hypothesis": "辞書からの仮説",
            "poc_spec": {
                "objective": "目的",
                "problem": "問題",
                "target_user_or_context": "ユーザー",
                "minimum_scope": "スコープ",
                "validation_plan": "計画"
            },
            "evidence_bundle": {
                "claims": ["主張"],
                "sources": ["ソース"]
            }
        }
        request = GateRequest(**data)
        assert request.request_id == "req_dict"
        assert request.poc_spec.objective == "目的"

    def test_poc_spec_required_fields(self):
        """Test that PocSpec requires mandatory fields."""
        with pytest.raises(Exception):
            PocSpec()  # Missing required fields

    def test_score_breakdown_validation(self):
        """Test ScoreBreakdown validates score ranges."""
        # Valid scores
        breakdown = ScoreBreakdown(
            impact=20, feasibility=0, learning_value=10,
            reusability=15, time_to_signal=5, dependency_risk=10,
            operational_risk=10, novelty=10
        )
        assert breakdown.impact == 20
        assert breakdown.feasibility == 0

        # Invalid score (out of range)
        with pytest.raises(Exception):
            ScoreBreakdown(impact=25)  # Over 20


# ============================================================================
# GateResponse Validation Tests
# ============================================================================


class TestGateResponseValidation:
    """Tests for GateResponse model validation."""

    def test_gate_response_creation(
        self,
        sample_gate_request: GateRequest,
        sample_score_breakdown: ScoreBreakdown,
        sample_rationale: Rationale
    ):
        """Test that a valid GateResponse can be created."""
        run_info = RunInfo(
            run_id="run_001",
            request_id="req_test_001",
            mode="experiment_gate",
            status=RunStatus.COMPLETED
        )
        decision = DecisionInfo(
            verdict=Verdict.GO,
            total_score=100,
            confidence=0.8
        )
        next_step = NextStep(recommended_action="run_minimal_probe")

        response = GateResponse(
            run=run_info,
            decision=decision,
            score_breakdown=sample_score_breakdown,
            rationale=sample_rationale,
            next_step=next_step,
            evidence_refs=["ref1"],
            reasoning_summary="テスト要約"
        )

        assert response.decision.verdict == Verdict.GO
        assert response.decision.total_score == 100
        assert response.next_step.recommended_action == "run_minimal_probe"

    def test_verdict_enum_values(self):
        """Test Verdict enum has expected values."""
        assert Verdict.GO.value == "go"
        assert Verdict.HOLD.value == "hold"
        assert Verdict.NO_GO.value == "no_go"


# ============================================================================
# Scoring Engine Tests
# ============================================================================


class TestScoringEngine:
    """Tests for the scoring engine."""

    def test_compute_weighted_total(self, sample_score_breakdown: ScoreBreakdown):
        """Test weighted total score computation."""
        total = compute_weighted_total(sample_score_breakdown, {})
        assert isinstance(total, int)
        assert 0 <= total <= 160

    def test_determine_verdict_go(self):
        """Test verdict determination for GO."""
        assert determine_verdict(80, {"go_min": 70, "hold_min": 45}) == Verdict.GO
        assert determine_verdict(70, {"go_min": 70, "hold_min": 45}) == Verdict.GO

    def test_determine_verdict_hold(self):
        """Test verdict determination for HOLD."""
        assert determine_verdict(60, {"go_min": 70, "hold_min": 45}) == Verdict.HOLD
        assert determine_verdict(45, {"go_min": 70, "hold_min": 45}) == Verdict.HOLD

    def test_determine_verdict_no_go(self):
        """Test verdict determination for NO_GO."""
        assert determine_verdict(30, {"go_min": 70, "hold_min": 45}) == Verdict.NO_GO
        assert determine_verdict(0, {"go_min": 70, "hold_min": 45}) == Verdict.NO_GO

    def test_generate_next_step_go(self, sample_rationale: Rationale):
        """Test next step generation for GO verdict."""
        next_step = generate_next_step(Verdict.GO, sample_rationale)
        assert next_step.recommended_action == "run_minimal_probe"
        assert next_step.minimal_probe is not None

    def test_generate_next_step_hold(self, sample_rationale: Rationale):
        """Test next step generation for HOLD verdict."""
        next_step = generate_next_step(Verdict.HOLD, sample_rationale)
        assert next_step.recommended_action == "gather_evidence"

    def test_generate_next_step_no_go(self, sample_rationale: Rationale):
        """Test next step generation for NO_GO verdict."""
        next_step = generate_next_step(Verdict.NO_GO, sample_rationale)
        assert next_step.recommended_action == "reject"

    def test_create_gate_response(
        self,
        sample_gate_request: GateRequest,
        sample_score_breakdown: ScoreBreakdown,
        sample_rationale: Rationale
    ):
        """Test GateResponse creation."""
        response = create_gate_response(
            sample_gate_request,
            sample_score_breakdown,
            sample_rationale
        )

        assert isinstance(response, GateResponse)
        assert isinstance(response.decision, DecisionInfo)
        assert isinstance(response.score_breakdown, ScoreBreakdown)
        assert isinstance(response.rationale, Rationale)
        assert isinstance(response.next_step, NextStep)


# ============================================================================
# Runner Tests
# ============================================================================


class TestRunner:
    """Tests for the runner module."""

    def test_run_gate_with_request(self, sample_gate_request: GateRequest):
        """Test run_gate with a GateRequest object."""
        response = run_gate(request=sample_gate_request, use_llm=False, verbose=False)
        assert isinstance(response, GateResponse)
        assert response.run.request_id == sample_gate_request.request_id

    def test_run_gate_with_dict(self, sample_poc_spec: PocSpec, sample_evidence_bundle: EvidenceBundle):
        """Test run_gate with a dictionary."""
        request_dict = {
            "request_id": "req_dict_test",
            "hypothesis": "辞書テスト仮説",
            "poc_spec": sample_poc_spec.model_dump(),
            "evidence_bundle": sample_evidence_bundle.model_dump()
        }
        response = run_gate(request_dict=request_dict, use_llm=False, verbose=False)
        assert isinstance(response, GateResponse)
        assert response.run.request_id == "req_dict_test"

    def test_run_gate_custom_scores(
        self,
        sample_gate_request: GateRequest,
        sample_score_breakdown: ScoreBreakdown,
        sample_rationale: Rationale
    ):
        """Test run_gate with custom scores."""
        response = run_gate(
            request=sample_gate_request,
            score_breakdown=sample_score_breakdown,
            rationale=sample_rationale,
            use_llm=False,
            verbose=False
        )
        assert response.score_breakdown.impact == 15
        assert response.rationale.why_now == ["理由1", "理由2"]

    def test_load_gate_request_from_file(self, tmp_path: Path):
        """Test loading GateRequest from a JSON file."""
        request_data = {
            "mode": "experiment_gate",
            "request_id": "req_file_test",
            "hypothesis": "ファイルからの仮説",
            "poc_spec": {
                "objective": "目的",
                "problem": "問題",
                "target_user_or_context": "ユーザー",
                "minimum_scope": "スコープ",
                "validation_plan": "計画"
            },
            "evidence_bundle": {
                "claims": ["主張"],
                "sources": ["ソース"]
            }
        }

        json_file = tmp_path / "request.json"
        json_file.write_text(json.dumps(request_data), encoding="utf-8")

        request = load_gate_request(input_path=json_file)
        assert request.request_id == "req_file_test"

    def test_load_gate_request_file_not_found(self, tmp_path: Path):
        """Test loading GateRequest from non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_gate_request(input_path=tmp_path / "nonexistent.json")

    def test_load_gate_request_no_input(self):
        """Test loading GateRequest without any input."""
        with pytest.raises(ValueError):
            load_gate_request()


# ============================================================================
# Evidence Insufficiency Tests
# ============================================================================


class TestEvidenceInsufficiency:
    """Tests for handling insufficient evidence."""

    def test_empty_evidence_bundle(self, sample_poc_spec: PocSpec):
        """Test handling of empty evidence bundle."""
        empty_evidence = EvidenceBundle(
            claims=[],
            sources=[],
            gaps=[]
        )
        request = GateRequest(
            request_id="req_empty_evidence",
            hypothesis="空の根拠テスト",
            poc_spec=sample_poc_spec,
            evidence_bundle=empty_evidence
        )

        # Should still work with default scores
        response = run_gate(request=request, use_llm=False, verbose=False)
        assert isinstance(response, GateResponse)
        # Confidence should be lower due to empty evidence
        assert response.decision.confidence < 0.5

    def test_missing_sources(self, sample_poc_spec: PocSpec):
        """Test handling of missing sources."""
        no_sources = EvidenceBundle(
            claims=["主張1", "主張2"],
            sources=[],
            gaps=["ギャップ1"]
        )
        request = GateRequest(
            request_id="req_no_sources",
            hypothesis="ソースなしテスト",
            poc_spec=sample_poc_spec,
            evidence_bundle=no_sources
        )

        response = run_gate(request=request, use_llm=False, verbose=False)
        assert isinstance(response, GateResponse)
        # Evidence refs should be empty
        assert response.evidence_refs == []


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for the complete flow."""

    def test_full_flow_from_request_to_response(self, sample_gate_request: GateRequest):
        """Test complete flow from GateRequest to GateResponse."""
        response = run_gate(request=sample_gate_request, use_llm=False, verbose=False)

        # Verify response structure
        assert response.run.mode == "experiment_gate"
        assert response.run.status == RunStatus.COMPLETED
        assert response.decision.verdict in [Verdict.GO, Verdict.HOLD, Verdict.NO_GO]
        assert 0 <= response.decision.total_score <= 160
        assert 0 <= response.decision.confidence <= 1
        assert response.next_step.recommended_action in [
            "run_minimal_probe",
            "gather_evidence",
            "defer",
            "reject"
        ]
        assert response.reasoning_summary is not None