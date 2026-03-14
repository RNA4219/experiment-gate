from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_gate.gate_pipeline import run_gate_pipeline
from experiment_gate.llm_client import LLMClient
from experiment_gate.pipeline import run_pipeline, run_pipeline_async
from experiment_gate.request_loader import load_request
from experiment_gate.result_formatter import build_agent_result
from experiment_gate.runtime_config import RuntimeConfig, load_runtime_config
from experiment_gate.schemas import (
    GateRequest,
    GateResponse,
    InsightRequest,
    Rationale,
    ScoreBreakdown,
)
from experiment_gate.scorer import (
    ScoringConfig,
    create_default_rationale,
    create_default_score_breakdown,
    create_failure_rationale,
    create_gate_response,
    load_scoring_config,
)


RESULT_FORMAT = "result"
RAW_FORMAT = "raw"


def _build_llm_client(config: RuntimeConfig) -> LLMClient:
    provider = None
    if config.llm.provider_sequence:
        provider = ",".join(config.llm.provider_sequence)
    elif config.llm.provider:
        provider = config.llm.provider
    return LLMClient(
        model=config.llm.model,
        provider=provider,
        max_tokens=config.llm.max_tokens,
        max_retries=config.llm.max_retries,
        retry_backoff_seconds=config.llm.retry_backoff_seconds,
        timeout_seconds=config.llm.timeout_seconds,
    )


def _request_option_overrides(config: RuntimeConfig, checkpoint_path: str | None = None, resume: bool = False) -> dict[str, Any]:
    return {
        "include_source_units": config.output.include_source_units,
        "include_intermediate_items": config.output.include_intermediate_items,
        "include_japanese_summary": config.output.include_japanese_summary,
        "max_concurrency": config.pipeline.limits.max_concurrency,
        "checkpoint_path": checkpoint_path,
        "resume": resume,
    }


def _request_constraint_overrides(config: RuntimeConfig, domain: str | None = None) -> dict[str, Any]:
    overrides: dict[str, Any] = {
        "max_problem_candidates": config.pipeline.limits.max_problem_candidates,
        "max_insights": config.pipeline.limits.max_insights,
    }
    if config.pipeline.routing.primary_persona:
        overrides["primary_persona"] = config.pipeline.routing.primary_persona
    if domain:
        overrides["domain"] = domain
    return overrides


def _format_result(request: InsightRequest, response: Any, output_format: str) -> Any:
    if output_format == RAW_FORMAT:
        return response
    return build_agent_result(request, response)


def run(
    *,
    request: InsightRequest | None = None,
    request_dict: dict[str, Any] | None = None,
    config: RuntimeConfig | None = None,
    config_dict: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    set_values: list[str] | None = None,
    input_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    text_path: str | Path | None = None,
    source_id: str | None = None,
    title: str | None = None,
    request_id: str | None = None,
    checkpoint_path: str | None = None,
    resume: bool = False,
    domain: str | None = None,
    output_format: str | None = None,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> Any:
    runtime_config = load_runtime_config(
        config=config,
        config_dict=config_dict,
        config_path=config_path,
        overrides=overrides,
        set_values=set_values,
        request_dict=request_dict,
    )
    if request is None:
        request, request_payload = load_request(
            input_path=input_path,
            pdf_path=pdf_path,
            text_path=text_path,
            request_dict=request_dict,
            source_id=source_id,
            title=title,
            request_id=request_id,
            option_overrides=_request_option_overrides(runtime_config, checkpoint_path=checkpoint_path, resume=resume),
            constraint_overrides=_request_constraint_overrides(runtime_config, domain=domain),
        )
        _ = request_payload
    llm_client = llm or _build_llm_client(runtime_config)
    response = run_pipeline(request=request, llm=llm_client, verbose=verbose)
    return _format_result(request, response, output_format or runtime_config.output.format)


async def run_async(
    *,
    request: InsightRequest | None = None,
    request_dict: dict[str, Any] | None = None,
    config: RuntimeConfig | None = None,
    config_dict: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    set_values: list[str] | None = None,
    input_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    text_path: str | Path | None = None,
    source_id: str | None = None,
    title: str | None = None,
    request_id: str | None = None,
    checkpoint_path: str | None = None,
    resume: bool = False,
    domain: str | None = None,
    output_format: str | None = None,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> Any:
    runtime_config = load_runtime_config(
        config=config,
        config_dict=config_dict,
        config_path=config_path,
        overrides=overrides,
        set_values=set_values,
        request_dict=request_dict,
    )
    if request is None:
        request, request_payload = load_request(
            input_path=input_path,
            pdf_path=pdf_path,
            text_path=text_path,
            request_dict=request_dict,
            source_id=source_id,
            title=title,
            request_id=request_id,
            option_overrides=_request_option_overrides(runtime_config, checkpoint_path=checkpoint_path, resume=resume),
            constraint_overrides=_request_constraint_overrides(runtime_config, domain=domain),
        )
        _ = request_payload
    llm_client = llm or _build_llm_client(runtime_config)
    response = await run_pipeline_async(request=request, llm=llm_client, verbose=verbose)
    return _format_result(request, response, output_format or runtime_config.output.format)


# ============================================================================
# Experiment Gate API
# ============================================================================


def load_gate_request(
    input_path: str | Path | None = None,
    request_dict: dict[str, Any] | None = None,
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
    request_dict: dict[str, Any] | None = None,
    input_path: str | Path | None = None,
    score_breakdown: ScoreBreakdown | None = None,
    rationale: Rationale | None = None,
    config: ScoringConfig | None = None,
    config_dict: dict[str, Any] | None = None,
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
    request_dict: dict[str, Any] | None = None,
    input_path: str | Path | None = None,
    score_breakdown: ScoreBreakdown | None = None,
    rationale: Rationale | None = None,
    config: ScoringConfig | None = None,
    config_dict: dict[str, Any] | None = None,
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
