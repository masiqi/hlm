from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "import_chapter_cards.py"


def _import_script_module():
    assert SCRIPT_PATH.exists(), f"{SCRIPT_PATH} does not exist"
    spec = importlib.util.spec_from_file_location("import_chapter_cards", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _card(chapter: int, **overrides):
    card = {
        "chapter": chapter,
        "plain_summary": f"第{chapter}回梗概",
        "plot_chain": [f"第{chapter}回情节"],
        "key_events": [f"event-{chapter:03d}"],
        "key_characters": [f"card-character-{chapter:03d}"],
        "current_chapter_foreshadowing_signals": [f"第{chapter}回伏笔"],
        "later_association_relation_ids": [f"rel-{chapter:03d}"],
        "quotable_fact_ids": [f"ev-{chapter:03d}"],
        "retrieval_tags": [f"第{chapter}回"],
        "understanding_focus": ["人物关系"],
    }
    card.update(overrides)
    return card


def _write_input(path: Path, cards: list[dict]) -> None:
    path.write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")


def test_load_import_cards_normalizes_defaults_and_sorts_by_chapter(tmp_path):
    module = _import_script_module()
    input_path = tmp_path / "cards.json"
    provided_source = {
        "prompt_name": "custom_prompt",
        "prompt_version": "2026-06-30",
        "generated_at": "2026-07-01T00:00:00Z",
    }
    _write_input(
        input_path,
        [
            _card(3, id="custom-review-003", source=provided_source),
            _card(1),
        ],
    )

    cards = module.load_import_cards(input_path)

    assert [card["chapter"] for card in cards] == [1, 3]
    assert cards[0]["id"] == "review-001"
    assert cards[0]["source"] == {
        "prompt_name": "hongloumeng_chapter_review_card",
        "prompt_version": "2026-07-01",
        "generated_at": None,
    }
    assert cards[1]["id"] == "custom-review-003"
    assert cards[1]["source"] == provided_source


def test_write_import_cards_outputs_sorted_pretty_utf8_json(tmp_path):
    module = _import_script_module()
    output_path = tmp_path / "chapter_review_cards.json"

    module.write_import_cards([_card(2, id="review-002"), _card(1, id="review-001")], output_path)

    output_text = output_path.read_text(encoding="utf-8")
    assert "\\u" not in output_text
    assert "\n  {" in output_text
    assert [card["chapter"] for card in json.loads(output_text)] == [1, 2]


@pytest.mark.parametrize(
    ("bad_card", "message_parts"),
    [
        (_card(0), ["chapter", "1..120"]),
        (_card(121), ["chapter", "1..120"]),
        (_card(1, plain_summary=""), ["plain_summary", "non-empty"]),
        (_card(1, plot_chain=[]), ["plot_chain", "non-empty"]),
    ],
)
def test_load_import_cards_rejects_invalid_required_values(tmp_path, bad_card, message_parts):
    module = _import_script_module()
    input_path = tmp_path / "cards.json"
    _write_input(input_path, [bad_card])

    with pytest.raises(ValueError) as exc_info:
        module.load_import_cards(input_path)

    message = str(exc_info.value)
    for part in message_parts:
        assert part in message


def test_cli_imports_cards_to_requested_output_path(tmp_path):
    input_path = tmp_path / "cards.json"
    output_path = tmp_path / "out.json"
    _write_input(input_path, [_card(2), _card(1)])

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(input_path), str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert [card["chapter"] for card in json.loads(output_path.read_text(encoding="utf-8"))] == [1, 2]


def test_cli_reports_validation_errors_with_nonzero_exit(tmp_path):
    input_path = tmp_path / "cards.json"
    output_path = tmp_path / "out.json"
    _write_input(input_path, [_card(1, plot_chain=[])])

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(input_path), str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "plot_chain" in result.stderr
    assert not output_path.exists()


def test_makefile_documents_chapter_card_import_command():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "import-chapter-cards:" in makefile
    assert "python scripts/import_chapter_cards.py" in makefile
