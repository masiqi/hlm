from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate chapter cards, import runtime data, and precompute entity trace cache "
            "for Hongloumeng chapters."
        )
    )
    parser.add_argument("--chapters", default="1-120", help="Chapter selection, e.g. 1-120, 1-3, or 27.")
    parser.add_argument("--output-dir", type=Path, default=Path("generated"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/app"))
    parser.add_argument("--manifest", type=Path, default=Path("book/chapters_manifest.json"))
    parser.add_argument("--static-dir", type=Path, default=Path("static"))
    parser.add_argument("--trace-output", type=Path, default=Path("data/app/entity_trace_cache.json"))
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--generated-at", default="", help="Optional generation date passed to chapter card generation.")
    parser.add_argument("--llm-timeout", type=float, default=None, help="Override chapter-card LLM timeout in seconds.")
    parser.add_argument("--lightrag-timeout", type=float, default=None, help="Override LightRAG request timeout in seconds.")
    parser.add_argument("--json-only", action="store_true", help="Generate only AppImportJSON, without full Markdown cards.")
    parser.add_argument("--overwrite-cards", action="store_true", help="Regenerate existing chapter card files.")
    parser.add_argument("--force-trace-cache", action="store_true", help="Rebuild selected trace cache chapters instead of skipping existing cache.")
    parser.add_argument("--include-generated-trace", action="store_true", help="Let trace cache builder scan generated chapter-card files too.")
    parser.add_argument("--max-evidence-candidates", type=int, default=None, help="Limit evidence candidates passed into card-generation prompts.")
    parser.add_argument("--skip-cards", action="store_true", help="Skip chapter card generation/import and only build trace cache.")
    parser.add_argument("--skip-trace-cache", action="store_true", help="Skip entity trace cache generation.")
    parser.add_argument("--no-postgres", action="store_true", help="Do not import/sync PostgreSQL; update JSON files only.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them.")
    return parser.parse_args(argv)


def build_commands(args: argparse.Namespace) -> list[list[str]]:
    commands: list[list[str]] = []

    if not args.skip_cards:
        card_command = [
            "python",
            "scripts/generate_chapter_cards.py",
            "--chapters",
            args.chapters,
            "--output-dir",
            str(args.output_dir),
        ]
        if args.env != Path(".env"):
            card_command.extend(["--env", str(args.env)])
        if args.manifest != Path("book/chapters_manifest.json"):
            card_command.extend(["--manifest", str(args.manifest)])
        if args.generated_at:
            card_command.extend(["--generated-at", args.generated_at])
        if args.llm_timeout is not None:
            card_command.extend(["--llm-timeout", str(args.llm_timeout)])
        if args.lightrag_timeout is not None:
            card_command.extend(["--lightrag-timeout", str(args.lightrag_timeout)])
        if args.overwrite_cards:
            card_command.append("--overwrite")
        if args.json_only:
            card_command.append("--json-only")
        if args.max_evidence_candidates is not None:
            card_command.extend(["--max-evidence-candidates", str(args.max_evidence_candidates)])
        commands.append(card_command)

        checked_path = args.output_dir / "chapter_review_cards.checked.json"
        runtime_cards_path = args.data_dir / "chapter_review_cards.json"
        commands.append(
            [
                "python",
                "scripts/import_chapter_cards.py",
                str(checked_path),
                str(runtime_cards_path),
                str(args.data_dir),
            ]
        )
        if not args.no_postgres:
            commands.append(["python", "scripts/import_postgres_seed.py"])

    if not args.skip_trace_cache:
        trace_command = [
            "python",
            "scripts/build_entity_trace_cache.py",
            "--chapters",
            args.chapters,
        ]
        if args.manifest != Path("book/chapters_manifest.json"):
            trace_command.extend(["--manifest", str(args.manifest)])
        if args.data_dir != Path("data/app"):
            trace_command.extend(["--data-dir", str(args.data_dir)])
        if args.static_dir != Path("static"):
            trace_command.extend(["--static-dir", str(args.static_dir)])
        if not args.no_postgres:
            trace_command.extend(["--postgres", "--sync-postgres"])
        trace_command.append("--flush-each-chapter")
        if not args.force_trace_cache:
            trace_command.append("--skip-existing")
        if args.include_generated_trace:
            trace_command.append("--include-generated")
        if args.lightrag_timeout is not None:
            trace_command.extend(["--lightrag-timeout", str(args.lightrag_timeout)])
        trace_command.extend(["--output", str(args.trace_output)])
        commands.append(trace_command)

    return commands


def run_commands(commands: list[list[str]], *, dry_run: bool) -> int:
    total_start = time.monotonic()
    total = len(commands)
    for index, command in enumerate(commands, start=1):
        step_start = time.monotonic()
        print(f"[{index}/{total}] start: {' '.join(command)}", flush=True)
        print("$ " + " ".join(command), flush=True)
        if dry_run:
            print(f"[{index}/{total}] skipped by dry-run", flush=True)
            continue
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            elapsed = time.monotonic() - step_start
            print(f"[{index}/{total}] failed after {elapsed:.1f}s: exit {completed.returncode}", flush=True)
            return completed.returncode
        elapsed = time.monotonic() - step_start
        print(f"[{index}/{total}] done ({elapsed:.1f}s)", flush=True)
    total_elapsed = time.monotonic() - total_start
    print(f"All material-generation steps finished ({total_elapsed:.1f}s)", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    commands = build_commands(args)
    if not commands:
        print("Nothing to do: both chapter cards and trace cache were skipped.")
        return 0
    return run_commands(commands, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
