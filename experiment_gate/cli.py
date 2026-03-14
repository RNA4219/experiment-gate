"""CLI entry point for Experiment Gate."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from experiment_gate.runner import run_gate


OUTPUT_FORMAT_RESULT = "result"
OUTPUT_FORMAT_RAW = "raw"


@contextmanager
def spinner(message: str, enabled: bool = True):
    if not enabled:
        yield
        return

    stop_event = threading.Event()

    def _run() -> None:
        for frame in itertools.cycle("|/-\\"):
            if stop_event.wait(0.12):
                break
            print(f"\r{message} {frame}", end="", file=sys.stderr, flush=True)
        print(f"\r{message} done", file=sys.stderr, flush=True)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join()


def _normalized_argv(argv: list[str] | None = None) -> list[str]:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return ["gate"]
    if argv[0] in {"gate", "-h", "--help"}:
        return argv
    return ["gate", *argv]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Experiment Gate - A hypothesis evaluation agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    gate_parser = subparsers.add_parser("gate", help="Run experiment gate evaluation")
    gate_parser.add_argument("-i", "--input", type=Path, required=True, help="Path to GateRequest JSON file")
    gate_parser.add_argument("-o", "--output", type=Path, default=None, help="Path to output JSON file")
    gate_parser.add_argument("--config", type=Path, default=None, help="Path to YAML/JSON gate config file")
    gate_parser.add_argument("--raw", action="store_true", help="Output raw GateResponse instead of result format")
    gate_parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        default=[],
        help="Override config value, e.g. --set gate.scoring.weights.novelty=0.3",
    )
    return parser


def serialize_result(result: object, output_format: str) -> str:
    if output_format == OUTPUT_FORMAT_RAW and hasattr(result, "model_dump_json"):
        return result.model_dump_json(indent=2)
    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return json.dumps(result, ensure_ascii=False, indent=2)


def run_gate_command(args: argparse.Namespace) -> int:
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        with spinner("Experiment Gate evaluating", enabled=sys.stderr.isatty()):
            result = run_gate(
                input_path=args.input,
                config_path=args.config,
                set_values=args.set_values,
                verbose=True,
            )
    except Exception as exc:
        print(f"Error running gate: {exc}", file=sys.stderr)
        return 1

    output_format = OUTPUT_FORMAT_RAW if args.raw else OUTPUT_FORMAT_RESULT
    output_json = serialize_result(result, output_format)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json, encoding="utf-8")
        print(f"Response written to: {args.output}")
    else:
        sys.stdout.buffer.write(output_json.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(_normalized_argv(argv))

    if args.command == "gate":
        return run_gate_command(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
