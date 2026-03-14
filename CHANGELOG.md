# Changelog

## v0.1.0

### Added
- Experiment Gate 用の repo-local Skill を Claude / Codex 向けに追加
- README 冒頭に Skill 案内を追加し、CLI の入口を見つけやすく改善
- `python -m experiment_gate` を中心にした Gate 専用 CLI ガイドを整備

### Changed
- repo を Experiment Gate 専用構成へ整理し、`run_gate()` と Gate CLI を正規入口に統一
- 判定ロジックを見直し、LLM / Persona 評価失敗時は保守的フォールバックで `go` に倒れないよう修正
- `dependency_risk` / `operational_risk` の採点方向を仕様どおりに修正
- Gate の `--config` / `--set` がスコア設定へ反映されるよう改善
- `schemas.py` を Gate で使う型に絞り、不要な後方互換型を整理

### Removed
- 旧 insight Agent 向けの CLI / API / pipeline / formatter / router / tests 一式
- insight 互換サンプル、設定、persona 定義などの後方互換ファイル

### Validation
- `python -m pytest tests/ -q` で 34 件すべて成功
- `python -m experiment_gate -i examples/sample_gate_request.json --raw` のローカル fallback 動作を確認
- 実 API 接続ありでも sample gate request が正常完走することを確認
