from pathlib import Path

from hlm_kg.ask_engine import AskEngine
from hlm_kg.content_store import ContentStore
from hlm_kg.domain import Evidence, validate_answer


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


class ConflictStore:
    def __init__(self, base: ContentStore) -> None:
        self.base = base

    def evidence(self, evidence_id: str) -> Evidence:
        if evidence_id == "ev-rel-daiyu-burying-flowers-fate":
            return Evidence(
                id="ev-rel-daiyu-burying-flowers-fate",
                source_type="graph_relation",
                chapter=27,
                location="关系线索：第二十七回",
                quote=None,
                evidence_text="黛玉葬花完全没有后文关联。",
                entity_ids=["card-lindaiyu"],
                relation_id="rel-daiyu-burying-flowers-fate",
                confidence="explicit",
                provenance="test-fixture",
                derived_from_ids=[],
            )
        return self.base.evidence(evidence_id)

    def __getattr__(self, name: str):
        return getattr(self.base, name)


def test_ask_engine_refuses_determinate_answer_when_sources_conflict():
    store = ConflictStore(ContentStore.from_paths(Path("book/chapters_manifest.json"), Path("data/app")))

    answer = AskEngine(store).ask("黛玉葬花体现了什么？")

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "SOURCE_CONFLICT"
    assert "资料存在不一致，优先查看原文依据。" in answer.refusal.message
    assert answer.short_conclusion == []
