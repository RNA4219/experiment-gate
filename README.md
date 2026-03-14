# Experiment Gate

仮説・PoC案・参考根拠を入力として、「今試す価値があるか」を判定する仮説評価エージェントです。8つの評価軸でスコアリングし、go/hold/no_go の3値判定を返します。

## 何ができるか

- 仮説の事業価値・技術的実現可能性の多角的評価
- 8評価軸スコアリング（各0-20点、最大160点）
- 根拠束の不足・矛盾・弱さの検出
- 閾値による自動判定（go_min: 70点、hold_min: 45点）
- 次アクションの推奨（run_minimal_probe / gather_evidence / defer / reject）

## 最短導線

### インストール

```bash
cd experiment-gate
pip install -e .
```

### CLI

```bash
# 仮説評価の実行
python -m experiment_gate gate -i examples/sample_gate_request.json

# 出力先を指定
python -m experiment_gate gate -i request.json -o result.json

# Raw形式で出力
python -m experiment_gate gate -i request.json --raw
```

### Python API

```python
from experiment_gate import (
    GateRequest, GateResponse, PocSpec, EvidenceBundle,
    run_gate
)

# 仮説評価リクエストの作成
request = GateRequest(
    request_id="req_001",
    hypothesis="RAGの検索精度を上げるためにハイブリッド検索を導入する",
    poc_spec=PocSpec(
        objective="ハイブリッド検索がRAGの再現率を向上させることを検証する",
        problem="セマンティック検索のみでは専門用語の再現率が低い",
        target_user_or_context="技術文書を検索する社内ナレッジベースユーザー",
        success_metrics=["再現率15%向上"],
        failure_or_abort_criteria=["向上5%未満"],
        minimum_scope="BM25を追加し100件のテストクエリで評価",
        non_goals=["本番デプロイ"],
        required_inputs_or_tools=["既存RAGパイプライン", "テストクエリセット"],
        validation_plan="ベースライン計測→実装→比較評価"
    ),
    evidence_bundle=EvidenceBundle(
        claims=["ハイブリッド検索は単一手法を上回る"],
        sources=["Apache Lucene documentation", "arXiv paper"],
        gaps=["日本語技術文書での評価結果がない"]
    )
)

# 評価実行
response = run_gate(request=request)
print(f"判定: {response.decision.verdict.value}")
print(f"スコア: {response.decision.total_score}/160")
print(f"推奨: {response.next_step.recommended_action}")
```

## 入力スキーマ: GateRequest

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `request_id` | str | リクエストID |
| `hypothesis` | str | 評価対象の仮説 |
| `poc_spec` | PocSpec | 最小PoC仕様 |
| `evidence_bundle` | EvidenceBundle | 根拠束 |
| `assumptions` | list[str] \| None | 前提条件 |
| `known_risks` | list[str] \| None | 既知のリスク |
| `decision_context` | str \| None | 判断コンテキスト |

### PocSpec（最小PoC仕様）

| フィールド | 説明 |
|-----------|------|
| `objective` | 目的 |
| `problem` | 解決する問題 |
| `target_user_or_context` | 対象ユーザー/コンテキスト |
| `success_metrics` | 成功指標 |
| `failure_or_abort_criteria` | 失敗/中止基準 |
| `minimum_scope` | 最小スコープ |
| `non_goals` | 非対象 |
| `required_inputs_or_tools` | 必要な入力/ツール |
| `validation_plan` | 検証計画 |

### EvidenceBundle（根拠束）

| フィールド | 説明 |
|-----------|------|
| `claims` | 主張のリスト |
| `sources` | ソースのリスト |
| `confidence_notes` | 信頼度注記（任意） |
| `gaps` | ギャップ・不足（任意） |

## 出力スキーマ: GateResponse

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `run` | RunInfo | 実行情報 |
| `decision` | DecisionInfo | 判定結果 |
| `score_breakdown` | ScoreBreakdown | 8軸スコア内訳 |
| `rationale` | Rationale | 判定理由 |
| `next_step` | NextStep | 次アクション |
| `evidence_refs` | list[str] | 参照した根拠 |
| `reasoning_summary` | str | 推論要約 |

### DecisionInfo（判定情報）

| フィールド | 説明 |
|-----------|------|
| `verdict` | 判定（go / hold / no_go） |
| `total_score` | 総合スコア（0-160） |
| `confidence` | 信頼度（0.0-1.0） |

## 8評価軸

各軸0-20点で評価し、加重平均で総合スコアを算出します。

| 軸 | 説明 | 重み |
|----|------|------|
| `impact` | 影響度・事業価値 | 1.0 |
| `feasibility` | 技術的実現可能性 | 1.0 |
| `learning_value` | 学習価値 | 1.0 |
| `reusability` | 再利用性 | 0.8 |
| `time_to_signal` | 信号までの時間（短いほど良い） | 0.8 |
| `dependency_risk` | 依存リスク（低いほど良い） | 1.0 |
| `operational_risk` | 運用リスク（低いほど良い） | 1.0 |
| `novelty` | 新規性 | 0.6 |

## 判定閾値

```
total_score >= 70  → go
total_score >= 45  → hold
total_score <  45  → no_go
```

- **go**: 今すぐ最小PoCを開始すべき
- **hold**: 追加の根拠収集または前提の検証が必要
- **no_go**: 現時点では進めるべきではない

## Gate Persona

4つの専門Personaが多角的に評価します。

| Persona ID | 役割 | 重点評価軸 |
|------------|------|-----------|
| `product_strategist` | 事業性・価値評価 | impact, reusability |
| `technical_reviewer` | 技術的実現可能性 | feasibility, dependency_risk |
| `skeptical_reviewer` | 飛躍・不足根拠の指摘 | dependency_risk, operational_risk |
| `delivery_operator` | 運用現実性 | time_to_signal, operational_risk |

## 設定

`config/defaults.yaml` で重みと閾値をカスタマイズできます。

```yaml
gate:
  scoring:
    weights:
      impact: 1.0
      feasibility: 1.0
      learning_value: 1.0
      reusability: 0.8
      time_to_signal: 0.8
      dependency_risk: 1.0
      operational_risk: 1.0
      novelty: 0.6
    thresholds:
      go_min: 70
      hold_min: 45
  decision:
    require_minimum_evidence: true
    allow_go_with_major_unknowns: false
```

## ルート構成

```text
experiment-gate/
  config/
    defaults.yaml           デフォルト設定
    personas/
      gate_personas.json    Gate用Persona定義
      default_personas.json Insight用Persona定義（後方互換）
    routing.yaml            ルーティング設定
  examples/
    sample_gate_request.json  GateRequestサンプル
  experiment_gate/          実装本体
    __init__.py
    cli.py                  CLIエントリポイント
    runner.py               run_gate() 公開API
    scorer.py               スコアリングエンジン
    schemas.py              Pydanticモデル定義
    pipeline.py             パイプライン（後方互換）
    ...
  tests/
    test_gate.py            Gate機能テスト
```

## テスト

```bash
# 全テスト実行
python -m pytest tests/ -v

# Gate関連テストのみ
python -m pytest tests/test_gate.py -v
```

## 後方互換性

従来の `insight` モードも引き続き利用可能です。

```bash
# Insight分析（従来機能）
python -m experiment_gate run -i examples/sample_request.json
python -m experiment_gate run --pdf material/sample.pdf
```

```python
from experiment_gate import run, InsightRequest

result = run(request=insight_request)
```

## 開発メモ

- 公開APIの本命は `run_gate()`
- スコアリングロジックは `scorer.py` に集約
- 新しい評価軸を追加する場合は schemas.py の ScoreBreakdown と scorer.py の重み定義を更新
- Personaの振る舞いは `config/personas/gate_personas.json` で定義

## ライセンス

MIT License