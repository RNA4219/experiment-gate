---
name: experiment-gate-codex
description: Experiment Gate リポジトリで Codex が作業するときの最小ガイド。Gate CLI の改善、`run_gate()` 周辺の修正、スコアリングや Persona 評価の確認、`python -m experiment_gate` の実行検証、設定反映や受け入れ確認を行うときに使う。
---

# Codex Skill for experiment-gate

## 目的

この repo で Codex が迷わず Gate 本体に入れるようにするための最小ガイド。

## 最初に見る場所

1. `README.md`
2. `experiment_gate/cli.py`
3. `experiment_gate/runner.py`
4. `experiment_gate/gate_pipeline.py`
5. `experiment_gate/scorer.py`
6. `experiment_gate/schemas.py`
7. `config/defaults.yaml`

## 正規入口

- API の本命は `run_gate()`
- CLI の本命は `python -m experiment_gate gate ...`
- サブコマンド省略実行は `python -m experiment_gate -i ...`
- スコア設定の読み込みは `load_scoring_config()`

## 変更方針

- 入口を増やすより `run_gate()` に寄せる
- CLI は薄い adapter に保つ
- Persona 評価の並列実行と集約は `gate_pipeline.py` に閉じ込める
- スコア計算と閾値判定は `scorer.py` に集約する
- README の例と実装のズレを残さない

## 触るときの注意

- LLM 障害時は保守的フォールバックを崩さない
- `dependency_risk` と `operational_risk` は「低リスクほど高得点」
- `--config` / `--set` は CLI から `run_gate()` まで通す
- 実 API 確認が必要なら `python -m experiment_gate -i examples/sample_gate_request.json --raw` を使う

## よく使う確認

```bash
python -m pytest tests/ -q
python -m experiment_gate --help
python -m experiment_gate -i examples/sample_gate_request.json --raw
python -m experiment_gate -i examples/sample_gate_request.json --set gate.scoring.thresholds.hold_min=49 --raw
```

## 変更後チェック

- GateRequest / GateResponse の契約を壊していないか
- LLM 失敗時に `hold` か `no_go` 側へ倒れるか
- 閾値上書きが CLI から効くか
- sample request でローカル fallback と実 API の両方が不自然な結果になっていないか
