"""Gate Pipeline module.

Orchestrates the experiment gate evaluation pipeline:
1. Normalize request
2. Evidence check
3. Persona-based scoring
4. Consolidation
5. Summary generation
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_gate.llm_client import LLMClient, complete_json_async_compat, get_stage_max_tokens
from experiment_gate.schemas import (
    GateRequest,
    GateResponse,
    PersonaDefinition,
    Rationale,
    ScoreBreakdown,
)


GATE_SCORING_MAX_TOKENS = get_stage_max_tokens("gate_scoring", 1500)

# Gate personas file path
GATE_PERSONAS_PATH = Path(__file__).parent.parent / "config" / "personas" / "gate_personas.json"


def _log(message: str) -> None:
    """Print progress message."""
    print(f"[GatePipeline] {message}", file=sys.stderr, flush=True)


def load_gate_personas() -> list[PersonaDefinition]:
    """Load gate personas from JSON file."""
    if not GATE_PERSONAS_PATH.exists():
        raise FileNotFoundError(f"Gate personas file not found: {GATE_PERSONAS_PATH}")

    with open(GATE_PERSONAS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    return [PersonaDefinition(**p) for p in data.get("personas", [])]


def build_scoring_prompt(
    request: GateRequest,
    persona: PersonaDefinition,
) -> tuple[str, str]:
    """Build prompt for persona-based scoring."""

    evidence_text = ""
    if request.evidence_bundle:
        claims = request.evidence_bundle.claims or []
        sources = request.evidence_bundle.sources or []
        gaps = request.evidence_bundle.gaps or []

        evidence_text = f"""
## 提示された根拠
### 主張
{chr(10).join(['- ' + c for c in claims]) if claims else '（なし）'}

### ソース
{chr(10).join(['- ' + s for s in sources]) if sources else '（なし）'}

### ギャップ・不足
{chr(10).join(['- ' + g for g in gaps]) if gaps else '（なし）'}
"""

    poc_text = f"""
## PoC仕様
- 目的: {request.poc_spec.objective}
- 問題: {request.poc_spec.problem}
- 対象: {request.poc_spec.target_user_or_context}
- 成功指標: {', '.join(request.poc_spec.success_metrics) if request.poc_spec.success_metrics else '未指定'}
- 失敗基準: {', '.join(request.poc_spec.failure_or_abort_criteria) if request.poc_spec.failure_or_abort_criteria else '未指定'}
- 最小スコープ: {request.poc_spec.minimum_scope}
"""

    system_prompt = f"""あなたは「{persona.name}」という視点で仮説・PoC案を評価する専門家です。

## あなたの役割
{persona.role or '専門的な観点から評価を行う'}

## あなたの特徴
{persona.description or '専門的な評価を行う'}

## このPersonaの執着
{persona.obsession or '特に指定なし'}

## このPersonaの盲点
{persona.blind_spot or '特に指定なし'}

## 重視する観点（優先軸）
{', '.join(persona.priorities) if persona.priorities else '特に指定なし'}

## 減点対象
{', '.join(persona.penalties) if persona.penalties else '特に指定なし'}

## リスク許容度
{persona.risk_tolerance or '特に指定なし'}

## 有望とみなすトリガー
{chr(10).join(['- ' + s for s in persona.trigger_signals]) if persona.trigger_signals else '特に指定なし'}

## 強く警戒するレッドフラグ
{chr(10).join(['- ' + s for s in persona.red_flags]) if persona.red_flags else '特に指定なし'}

---

以下の8軸で0-20点のスコアを付けてください：

- **impact** (影響度): 事業や組織への影響の大きさ
- **feasibility** (実現可能性): 技術的・リソース的に実現可能か
- **learning_value** (学習価値): 成功・失敗問わず得られる知見
- **reusability** (再利用性): 他のプロジェクトや領域への展開可能性
- **time_to_signal** (信号までの時間): 結果が早く得られるほど高スコア
- **dependency_risk** (依存リスク): 外部依存が少ないほど高スコア
- **operational_risk** (運用リスク): 運用負荷が低いほど高スコア
- **novelty** (新規性): 新しいアプローチや発見の可能性

**注意**: dependency_risk と operational_risk は「低いほど良い」軸ですが、
スコアは「リスクが低い＝高スコア」で評価してください。

JSONフォーマット：
```json
{{
  "scores": {{
    "impact": 0-20,
    "feasibility": 0-20,
    "learning_value": 0-20,
    "reusability": 0-20,
    "time_to_signal": 0-20,
    "dependency_risk": 0-20,
    "operational_risk": 0-20,
    "novelty": 0-20
  }},
  "why_now": ["今やるべき理由"],
  "why_not_now": ["今やるべきでない理由"],
  "critical_uncertainties": ["重要な不確実性"],
  "summary": "このPersona視点での簡潔な評価まとめ"
}}
```"""

    user_prompt = f"""以下の仮説・PoC案を「{persona.name}」の視点で評価してください。

## 仮説
{request.hypothesis}
{poc_text}
{evidence_text}

## 既知のリスク
{chr(10).join(['- ' + r for r in request.known_risks]) if request.known_risks else '（なし）'}

## 判断コンテキスト
{request.decision_context or '特に指定なし'}

---

JSON形式で評価結果を出力してください。あなたの視点（{persona.name}）での評価を反映させてください。"""

    return system_prompt, user_prompt


async def evaluate_with_persona(
    request: GateRequest,
    persona: PersonaDefinition,
    llm: LLMClient,
) -> dict[str, Any]:
    """Evaluate with a single persona."""
    system_prompt, user_prompt = build_scoring_prompt(request, persona)

    try:
        response = await complete_json_async_compat(
            llm,
            system_prompt,
            user_prompt,
            max_tokens=GATE_SCORING_MAX_TOKENS,
        )
        return {
            "persona_id": persona.persona_id,
            "persona_name": persona.name,
            "scores": response.get("scores", {}),
            "why_now": response.get("why_now", []),
            "why_not_now": response.get("why_not_now", []),
            "critical_uncertainties": response.get("critical_uncertainties", []),
            "summary": response.get("summary", ""),
        }
    except Exception as e:
        _log(f"  - Warning: {persona.persona_id} evaluation failed: {e}")
        return {
            "persona_id": persona.persona_id,
            "persona_name": persona.name,
            "scores": {},
            "why_now": [],
            "why_not_now": [],
            "critical_uncertainties": [f"評価エラー: {str(e)[:50]}"],
            "summary": "評価を完了できませんでした",
        }


async def evaluate_with_all_personas(
    request: GateRequest,
    personas: list[PersonaDefinition],
    llm: LLMClient,
    verbose: bool = True,
) -> list[dict[str, Any]]:
    """Evaluate with all personas in parallel."""
    if verbose:
        _log(f"Evaluating with {len(personas)} personas...")

    tasks = [
        evaluate_with_persona(request, persona, llm)
        for persona in personas
    ]

    results = await asyncio.gather(*tasks)

    if verbose:
        for result in results:
            scores = result.get("scores", {})
            if scores:
                total = sum(scores.values()) / 8 if scores else 0
                _log(f"  - {result['persona_name']}: avg={total:.1f}")

    return results


def aggregate_scores(
    persona_results: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> ScoreBreakdown:
    """Aggregate scores from all personas."""
    if weights is None:
        weights = {
            "impact": 1.0,
            "feasibility": 1.0,
            "learning_value": 1.0,
            "reusability": 0.8,
            "time_to_signal": 0.8,
            "dependency_risk": 1.0,
            "operational_risk": 1.0,
            "novelty": 0.6,
        }

    # Collect scores per axis
    axis_scores: dict[str, list[int]] = {
        "impact": [],
        "feasibility": [],
        "learning_value": [],
        "reusability": [],
        "time_to_signal": [],
        "dependency_risk": [],
        "operational_risk": [],
        "novelty": [],
    }

    persona_weights: dict[str, float] = {}
    total_weight = 0.0
    for persona_result in persona_results:
        persona_id = persona_result["persona_id"]
        # Default equal weight for each persona
        persona_weights[persona_id] = 1.0
        total_weight += 1.0

        scores = persona_result.get("scores", {})
        for axis in axis_scores:
            if axis in scores:
                value = scores[axis]
                if isinstance(value, (int, float)) and 0 <= value <= 20:
                    axis_scores[axis].append(int(value))

    # Compute weighted average for each axis
    final_scores = {}
    for axis, values in axis_scores.items():
        if values:
            avg = sum(values) / len(values)
            final_scores[axis] = int(round(avg))
        else:
            final_scores[axis] = 10  # Default middle score

    return ScoreBreakdown(**final_scores)


def aggregate_rationale(
    persona_results: list[dict[str, Any]],
) -> Rationale:
    """Aggregate rationale from all personas."""
    why_now_all = []
    why_not_now_all = []
    uncertainties_all = []

    for result in persona_results:
        why_now_all.extend(result.get("why_now", []))
        why_not_now_all.extend(result.get("why_not_now", []))
        uncertainties_all.extend(result.get("critical_uncertainties", []))

    # Deduplicate and limit
    def dedupe_and_limit(items: list[str], limit: int = 5) -> list[str]:
        seen = set()
        unique = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                unique.append(item)
        return unique[:limit]

    return Rationale(
        why_now=dedupe_and_limit(why_now_all),
        why_not_now=dedupe_and_limit(why_not_now_all),
        critical_uncertainties=dedupe_and_limit(uncertainties_all, 4),
    )


async def run_gate_pipeline(
    request: GateRequest,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> tuple[ScoreBreakdown, Rationale, list[str]]:
    """Run the gate evaluation pipeline.

    Returns:
        Tuple of (ScoreBreakdown, Rationale, list of applied persona IDs)
    """
    if llm is None:
        llm = LLMClient()

    # Load personas
    personas = load_gate_personas()

    if verbose:
        _log(f"Loaded {len(personas)} gate personas")
        _log(f"Hypothesis: {request.hypothesis[:80]}...")

    # Evaluate with all personas
    persona_results = await evaluate_with_all_personas(request, personas, llm, verbose)

    # Aggregate scores and rationale
    score_breakdown = aggregate_scores(persona_results)
    rationale = aggregate_rationale(persona_results)

    applied_persona_ids = [p["persona_id"] for p in persona_results]

    return score_breakdown, rationale, applied_persona_ids


def run_gate_pipeline_sync(
    request: GateRequest,
    llm: LLMClient | None = None,
    verbose: bool = True,
) -> tuple[ScoreBreakdown, Rationale, list[str]]:
    """Sync wrapper for gate pipeline."""
    return asyncio.run(run_gate_pipeline(request, llm, verbose))