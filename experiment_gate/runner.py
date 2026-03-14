from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from experiment_gate.gate_pipeline import run_gate_pipeline
from experiment_gate.llm_client import LLMClient
from experiment_gate.schemas import GateRequest, GateResponse, Rationale, ScoreBreakdown
from experiment_gate.scorer import (
    ScoringConfig,
    create_default_rationale,
    create_default_score_breakdown,
    create_failure_rationale,
    create_gate_response,
    load_scoring_config,
)


def load_gate_request(
    input_path: str | Path | None = None,
    request_dict: dict | None = None,
) -> GateRequest:
    """Load a GateRequest from file or dict."""
    if input_path is not None:
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        with open(path, encoding="utf-8") as f:
            request_dict = json.load(f)

    if request_dict is None:
        raise ValueError("Either input_path or request_dict must be provided")

    return GateRequest(**request_dict)


def _resolve_gate_fallback(error: Exception | None = None) -> tuple[ScoreBreakdown, Rationale]:
    score_breakdown = create_default_score_breakdown()
    reason = str(error) if error else None
    rationale = create_failure_rationale(reason) if error else create_default_rationale()
    return score_breakdown, rationale


def run_gate(
    *,
    request: GateRequest | None = None,
    request_dict: dict | None = None,
    input_path: str | Path | None = None,
    score_breakdown: ScoreBreakdown | None = None,
    rationale: Rationale | None = None,
    config: ScoringConfig | None = None,
    config_dict: dict | None = None,
    config_path: str | Path | None = None,
    set_values: list[str] | None = None,
    llm: LLMClient | None = None,
    use_llm: bool = True,
    verbose: bool = True,
) -> GateResponse:
    """Run the experiment gate evaluation."""
    started_at = datetime.now(timezone.utc)
    scoring_config = load_scoring_config(
        config=config,
        config_dict=config_dict,
        config_path=config_path,
        set_values=set_values,
    )

    if request is None:
        request = load_gate_request(input_path=input_path, request_dict=request_dict)

    if verbose:
        print(f"[ExperimentGate] Processing request: {request.request_id}", flush=True)
        print(f"[ExperimentGate] Hypothesis: {request.hypothesis[:80]}...", flush=True)

    applied_persona_ids: list[str] = []

    if use_llm and score_breakdown is None:
        try:
            llm_client = llm or LLMClient()
            score_breakdown, rationale, applied_persona_ids = asyncio.run(
                run_gate_pipeline(request, llm_client, verbose)
            )
        except Exception as e:
            if verbose:
                print(f"[ExperimentGate] LLM evaluation failed, using conservative fallback: {e}", flush=True)
            score_breakdown, rationale = _resolve_gate_fallback(e)

    if score_breakdown is None:
        score_breakdown, fallback_rationale = _resolve_gate_fallback()
        rationale = rationale or fallback_rationale
    if rationale is None:
        rationale = create_default_rationale()

    response = create_gate_response(request, score_breakdown, rationale, scoring_config)
    response.run.started_at = started_at
    response.run.finished_at = datetime.now(timezone.utc)
    response.run.applied_personas = applied_persona_ids

    if verbose:
        print(f"[ExperimentGate] Verdict: {response.decision.verdict.value}", flush=True)
        print(f"[ExperimentGate] Total score: {response.decision.total_score}/160", flush=True)
        print(f"[ExperimentGate] Confidence: {response.decision.confidence:.2f}", flush=True)
        print(f"[ExperimentGate] Recommended: {response.next_step.recommended_action}", flush=True)

    return response


async def run_gate_async(
    *,
    request: GateRequest | None = None,
    request_dict: dict | None = None,
    input_path: str | Path | None = None,
    score_breakdown: ScoreBreakdown | None = None,
    rationale: Rationale | None = None,
    config: ScoringConfig | None = None,
    config_dict: dict | None = None,
    config_path: str | Path | None = None,
    set_values: list[str] | None = None,
    llm: LLMClient | None = None,
    use_llm: bool = True,
    verbose: bool = True,
) -> GateResponse:
    """Async version of run_gate."""
    started_at = datetime.now(timezone.utc)
    scoring_config = load_scoring_config(
        config=config,
        config_dict=config_dict,
        config_path=config_path,
        set_values=set_values,
    )

    if request is None:
        request = load_gate_request(input_path=input_path, request_dict=request_dict)

    if verbose:
        print(f"[ExperimentGate] Processing request: {request.request_id}", flush=True)
        print(f"[ExperimentGate] Hypothesis: {request.hypothesis[:80]}...", flush=True)

    applied_persona_ids: list[str] = []

    if use_llm and score_breakdown is None:
        try:
            llm_client = llm or LLMClient()
            score_breakdown, rationale, applied_persona_ids = await run_gate_pipeline(
                request, llm_client, verbose
            )
        except Exception as e:
            if verbose:
                print(f"[ExperimentGate] LLM evaluation failed, using conservative fallback: {e}", flush=True)
            score_breakdown, rationale = _resolve_gate_fallback(e)

    if score_breakdown is None:
        score_breakdown, fallback_rationale = _resolve_gate_fallback()
        rationale = rationale or fallback_rationale
    if rationale is None:
        rationale = create_default_rationale()

    response = create_gate_response(request, score_breakdown, rationale, scoring_config)
    response.run.started_at = started_at
    response.run.finished_at = datetime.now(timezone.utc)
    response.run.applied_personas = applied_persona_ids

    if verbose:
        print(f"[ExperimentGate] Verdict: {response.decision.verdict.value}", flush=True)
        print(f"[ExperimentGate] Total score: {response.decision.total_score}/160", flush=True)
        print(f"[ExperimentGate] Confidence: {response.decision.confidence:.2f}", flush=True)
        print(f"[ExperimentGate] Recommended: {response.next_step.recommended_action}", flush=True)

    return response
