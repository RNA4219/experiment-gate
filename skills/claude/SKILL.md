---
name: experiment-gate-claude
description: Experiment Gate リポジトリで Claude 系エージェントが作業するときの最小ガイド。GateRequest の確認、`python -m experiment_gate` CLI 実行、`config/defaults.yaml` や `--set` による閾値調整、LLM 接続確認、README と実装整合の点検が必要なときに使う。
---

# Claude Skill for experiment-gate

## 目的

Claude がこの repo を読むときに、Experiment Gate の入口と操作方法を短時間で掴めるようにする。

## 最初に見る場所

1. `README.md`
2. `experiment_gate/cli.py`
3. `experiment_gate/runner.py`
4. `experiment_gate/gate_pipeline.py`
5. `experiment_gate/scorer.py`
6. `config/defaults.yaml`

## 正規入口

- CLI の本命は `python -m experiment_gate gate ...`
- サブコマンド省略でも `python -m experiment_gate -i ...` で動く
- Python API の本命は `run_gate()`
- 設定変更は `config/defaults.yaml` または `--set gate.scoring...` を使う

## よく使う確認

```bash
python -m pytest tests/ -q
python -m experiment_gate --help
python -m experiment_gate -i examples/sample_gate_request.json --raw
python -m experiment_gate -i examples/sample_gate_request.json --set gate.scoring.thresholds.go_min=80 --raw
```

## 読み方のポイント

- 判定ロジックは `scorer.py`
- Persona ごとの評価と集約は `gate_pipeline.py`
- フォールバックや config 適用は `runner.py`
- CLI の扱いやすさは `cli.py`
- 入力契約は `GateRequest`、出力契約は `GateResponse`

## レビュー観点

- LLM 失敗時に `go` へ倒れないか
- `dependency_risk` / `operational_risk` の向きが仕様どおりか
- CLI の `--config` / `--set` が `run_gate()` に届いているか
- README の実行例が現行 CLI と一致しているか
