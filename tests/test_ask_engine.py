from pathlib import Path

from hlm_kg.ask_engine import AskEngine
from hlm_kg.content_store import ContentStore
from hlm_kg.domain import validate_answer


def make_engine() -> AskEngine:
    store = ContentStore.from_paths(Path("book/chapters_manifest.json"), Path("data/app"))
    return AskEngine(store)


def test_ask_engine_answers_supported_daiyu_question():
    answer = make_engine().ask("黛玉葬花体现了什么？")

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.short_conclusion
    assert any(evidence.chapter == 27 for evidence in answer.evidence)
    assert any(evidence.source_type == "graph_relation" for evidence in answer.evidence)
    assert answer.quotable_facts is not None
    assert any("第 27 回" in claim.text for claim in answer.quotable_facts.claims)


def test_ask_engine_returns_refusal_for_out_of_scope_question():
    answer = make_engine().ask("请帮我写一篇作文")

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "OUT_OF_SCOPE"


def test_ask_engine_answers_supported_tanchun_question():
    answer = make_engine().ask("探春理家体现了什么性格？")

    validate_answer(answer)
    assert answer.status == "answered"
    assert any(evidence.chapter == 56 for evidence in answer.evidence)
    assert answer.quotable_facts is not None


def test_ask_engine_returns_partial_for_mixed_supported_and_unsupported_question():
    answer = make_engine().ask("黛玉葬花体现了什么？再说明一个没有资料的后文细节")

    validate_answer(answer)
    assert answer.status == "partial"
    assert answer.refusal is not None
    assert answer.refusal.reason == "UNSUPPORTED_SUBCLAIM"
    assert "没有资料的后文细节" in answer.refusal.message
