import json

from experiment_gate.cli import main


def test_main_accepts_gate_without_explicit_subcommand(monkeypatch, tmp_path, capsys):
    request_path = tmp_path / "gate_request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "req_cli_001",
                "hypothesis": "CLI test hypothesis",
                "poc_spec": {
                    "objective": "Test objective",
                    "problem": "Test problem",
                    "target_user_or_context": "Test user",
                    "minimum_scope": "Test scope",
                    "validation_plan": "Test validation"
                },
                "evidence_bundle": {
                    "claims": ["claim"],
                    "sources": ["source"]
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "experiment_gate.cli.run_gate",
        lambda **kwargs: {"decision": {"verdict": "hold"}, "run": {"request_id": "req_cli_001"}},
    )

    exit_code = main(["-i", str(request_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"verdict": "hold"' in captured.out
