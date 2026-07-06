from pathlib import Path

from scripts.generate_all_chapter_materials import build_commands, run_commands, parse_args


def test_build_commands_generates_cards_imports_seed_and_builds_trace_cache_by_default():
    args = parse_args(["--chapters", "1-120"])

    commands = build_commands(args)

    assert commands == [
        [
            "python",
            "scripts/generate_chapter_cards.py",
            "--chapters",
            "1-120",
            "--output-dir",
            "generated",
        ],
        [
            "python",
            "scripts/import_chapter_cards.py",
            "generated/chapter_review_cards.checked.json",
            "data/app/chapter_review_cards.json",
            "data/app",
        ],
        ["python", "scripts/import_postgres_seed.py"],
        [
            "python",
            "scripts/build_entity_trace_cache.py",
            "--chapters",
            "1-120",
            "--postgres",
            "--sync-postgres",
            "--flush-each-chapter",
            "--skip-existing",
            "--output",
            "data/app/entity_trace_cache.json",
        ],
    ]


def test_build_commands_can_force_rebuild_and_skip_chapter_card_generation():
    args = parse_args(["--chapters", "27", "--skip-cards", "--force-trace-cache", "--include-generated-trace"])

    commands = build_commands(args)

    assert commands == [
        [
            "python",
            "scripts/build_entity_trace_cache.py",
            "--chapters",
            "27",
            "--postgres",
            "--sync-postgres",
            "--flush-each-chapter",
            "--include-generated",
            "--output",
            "data/app/entity_trace_cache.json",
        ],
    ]


def test_build_commands_can_run_without_postgres_sync_for_local_json_only_trials():
    args = parse_args(["--chapters", "1-3", "--no-postgres", "--json-only", "--max-evidence-candidates", "30"])

    commands = build_commands(args)

    assert commands == [
        [
            "python",
            "scripts/generate_chapter_cards.py",
            "--chapters",
            "1-3",
            "--output-dir",
            "generated",
            "--json-only",
            "--max-evidence-candidates",
            "30",
        ],
        [
            "python",
            "scripts/import_chapter_cards.py",
            "generated/chapter_review_cards.checked.json",
            "data/app/chapter_review_cards.json",
            "data/app",
        ],
        [
            "python",
            "scripts/build_entity_trace_cache.py",
            "--chapters",
            "1-3",
            "--flush-each-chapter",
            "--skip-existing",
            "--output",
            "data/app/entity_trace_cache.json",
        ],
    ]


def test_build_commands_respects_custom_paths_and_overwrite():
    args = parse_args(
        [
            "--chapters",
            "1,2",
            "--output-dir",
            "generated/full",
            "--data-dir",
            "data/runtime",
            "--trace-output",
            "data/runtime/cache.json",
            "--overwrite-cards",
            "--env",
            ".env.local",
        ]
    )

    commands = build_commands(args)

    assert commands[0] == [
        "python",
        "scripts/generate_chapter_cards.py",
        "--chapters",
        "1,2",
        "--output-dir",
        "generated/full",
        "--env",
        ".env.local",
        "--overwrite",
    ]
    assert commands[1] == [
        "python",
        "scripts/import_chapter_cards.py",
        "generated/full/chapter_review_cards.checked.json",
        "data/runtime/chapter_review_cards.json",
        "data/runtime",
    ]
    assert commands[3][-2:] == ["--output", "data/runtime/cache.json"]


def test_parse_args_defaults_to_full_book_and_common_paths():
    args = parse_args([])

    assert args.chapters == "1-120"
    assert args.output_dir == Path("generated")
    assert args.data_dir == Path("data/app")
    assert args.trace_output == Path("data/app/entity_trace_cache.json")
    assert args.llm_timeout is None
    assert args.lightrag_timeout is None


def test_build_commands_passes_llm_timeout_to_card_generation_only():
    args = parse_args(["--chapters", "1-3", "--llm-timeout", "600"])

    commands = build_commands(args)

    assert commands[0] == [
        "python",
        "scripts/generate_chapter_cards.py",
        "--chapters",
        "1-3",
        "--output-dir",
        "generated",
        "--llm-timeout",
        "600.0",
    ]
    assert "--llm-timeout" not in commands[-1]


def test_build_commands_passes_lightrag_timeout_to_card_generation_and_trace_cache():
    args = parse_args(["--chapters", "12-120", "--lightrag-timeout", "180"])

    commands = build_commands(args)

    assert commands[0] == [
        "python",
        "scripts/generate_chapter_cards.py",
        "--chapters",
        "12-120",
        "--output-dir",
        "generated",
        "--lightrag-timeout",
        "180.0",
    ]
    assert "--lightrag-timeout" in commands[-1]
    assert commands[-1][commands[-1].index("--lightrag-timeout") + 1] == "180.0"


def test_makefile_documents_full_material_generation_command():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "generate-all-chapter-materials:" in makefile
    assert "python scripts/generate_all_chapter_materials.py" in makefile
    assert "build-static-chapter-cache:" in makefile
    assert "python scripts/build_static_chapter_cache.py" in makefile


def test_run_commands_prints_step_progress_in_dry_run(capsys):
    exit_code = run_commands([["python", "one.py"], ["python", "two.py"]], dry_run=True)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "[1/2] start:" in output
    assert "[1/2] skipped by dry-run" in output
    assert "[2/2] start:" in output
    assert "All material-generation steps finished" in output
