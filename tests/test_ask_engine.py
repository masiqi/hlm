from pathlib import Path

from hlm_kg.evidence_adapter import normalize_query_data_response
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


class FakeLightRAGClient:
    def __init__(self, response):
        self.response = response
        self.queries = []

    def query_data(self, query: str, mode: str = "hybrid", **options):
        self.queries.append((query, mode, options))
        return self.response


def test_ask_engine_answers_chapter_location_from_normalized_query_data():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "宝黛初会",
                    "tgt_id": "第三回",
                    "keywords": "发生章回",
                    "description": "宝黛初会发生在第三回，林黛玉进贾府后与贾宝玉在贾母处相见。",
                    "source_id": "doc-003-chunk-001",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }
    client = FakeLightRAGClient(response)
    answer = make_engine().ask("宝黛初会发生在哪一回？", retrieval_client=client)

    validate_answer(answer)
    assert client.queries == [("宝黛初会发生在哪一回？", "hybrid", {"only_need_context": True})]
    assert answer.status == "answered"
    assert "第三回" in answer.short_conclusion[0].text
    assert any(evidence.chapter == 3 for evidence in answer.evidence)
    assert any(evidence.source_type == "graph_relation" for evidence in answer.evidence)
    assert answer.continuation_links[0].target_type == "chapter"
    assert answer.continuation_links[0].target_id == "3"


def test_ask_engine_refuses_when_query_data_has_no_chapter_source():
    response = {
        "status": "success",
        "data": {
            "entities": [
                {
                    "entity_name": "宝黛初会",
                    "entity_type": "ChapterEpisode",
                    "description": "只说明相关，但没有可回溯章回来源。",
                }
            ],
            "relationships": [],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"
    assert "没有找到足够依据" in answer.refusal.message


def test_ask_engine_does_not_turn_interpretive_retrieval_hit_into_location_answer():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "王熙凤",
                    "tgt_id": "协理宁国府",
                    "keywords": "人物表现",
                    "description": "王熙凤协理宁国府表现其管家才干。",
                    "source_id": "doc-013-chunk-001",
                    "file_path": "013-第十三回-秦可卿死封龙禁尉 王熙凤协理宁国府.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("王熙凤的性格体现在哪里？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert "王熙凤协理宁国府表现其管家才干" in answer.short_conclusion[0].text
    assert answer.evidence[0].chapter == 13
    assert answer.evidence[0].source_type == "graph_relation"


def test_ask_engine_answers_relationship_question_from_query_data_evidence():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "林黛玉",
                    "tgt_id": "贾宝玉",
                    "keywords": "表兄妹,知己关系",
                    "description": "林黛玉和贾宝玉是姑表兄妹，第三回初见，后文多次互为知己。",
                    "source_id": "doc-003-chunk-001<SEP>doc-005-chunk-001",
                    "file_path": (
                        "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt<SEP>"
                        "005-第五回-贾宝玉神游太虚境 警幻仙曲演红楼梦.txt"
                    ),
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }
    client = FakeLightRAGClient(response)

    answer = make_engine().ask("林黛玉和贾宝玉的关系是什么？", retrieval_client=client)

    validate_answer(answer)
    assert client.queries == [("林黛玉和贾宝玉的关系是什么？", "hybrid", {"only_need_context": True})]
    assert answer.status == "answered"
    assert "姑表兄妹" in answer.short_conclusion[0].text
    assert [link.target_id for link in answer.continuation_links] == ["3", "5"]
    assert answer.quotable_facts is not None
    assert "第3回" in answer.quotable_facts.claims[0].text


def test_ask_engine_falls_back_to_original_text_when_retrieval_hits_do_not_answer_age_question():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "王熙凤",
                    "tgt_id": "贾宝玉",
                    "keywords": "人物关系",
                    "description": "王熙凤与贾宝玉在《红楼梦》中是堂嫂与堂弟的关系。",
                    "source_id": "doc-007-chunk-001",
                    "file_path": "007-第七回-送宫花贾琏戏熙凤 宴宁府宝玉会秦钟.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("贾宝玉最早被资料介绍时多大年纪？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert "十来岁" in answer.short_conclusion[0].text
    assert "王熙凤" not in answer.short_conclusion[0].text
    assert answer.evidence[0].chapter == 2
    assert answer.evidence[0].source_type == "original_text"
    assert "如今长了十来岁" in answer.evidence[0].evidence_text
    assert answer.continuation_links[0].target_id == "2"


def test_ask_engine_rejects_age_evidence_about_another_person():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [],
            "chunks": [
                {
                    "chunk_id": "doc-012-chunk-001",
                    "content": "贾瑞二十来岁的人，尚未娶亲，想着麝月不得到手，因而相思成病。",
                    "file_path": "012-第十二回-王熙凤毒设相思局 贾天祥正照风月鉴.txt",
                }
            ],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("麝月这时候是几岁？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"


def test_ask_engine_refuses_age_question_when_candidates_do_not_contain_age_evidence():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "王熙凤",
                    "tgt_id": "贾宝玉",
                    "keywords": "人物关系",
                    "description": "王熙凤与贾宝玉在《红楼梦》中是堂嫂与堂弟的关系。",
                    "source_id": "doc-007-chunk-001",
                    "file_path": "007-第七回-送宫花贾琏戏熙凤 宴宁府宝玉会秦钟.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("王熙凤第一次在书中出现的时候是几岁？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"


def test_ask_engine_extracts_death_answer_instead_of_returning_relationship_essay():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "林黛玉",
                    "tgt_id": "贾宝玉",
                    "keywords": "知己关系,爱情悲剧",
                    "description": (
                        "林黛玉与贾宝玉的关系是以姑表兄妹血缘为纽带、刻骨铭心的知己之恋。"
                        "二人自幼一同长大，初见便觉面善。"
                        "宝玉说亲的消息直接导致黛玉病情加重，使其急怒攻心，惟求速死。"
                        "黛玉最终撕毁宝玉所赠之帕以断情，临终前直声呼唤“宝玉！宝玉！你好……”。"
                        "黛玉死后，宝玉悲痛如刀搅。"
                    ),
                    "source_id": "doc-097-chunk-001",
                    "file_path": "097-第九十七回-林黛玉焚稿断痴情 薛宝钗出闺成大礼.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("林黛玉是怎么死的？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    conclusion = answer.short_conclusion[0].text
    assert "急怒攻心" in conclusion
    assert "病情加重" in conclusion
    assert "临终" in conclusion
    assert "姑表兄妹" not in conclusion
    assert len(conclusion) < 220
    assert "姑表兄妹" not in answer.evidence[0].evidence_text
    assert "急怒攻心" in answer.evidence[0].evidence_text


def test_ask_engine_resolves_short_subject_before_extracting_death_answer():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "林黛玉",
                    "tgt_id": "贾宝玉",
                    "keywords": "知己关系,爱情悲剧",
                    "description": (
                        "林黛玉与贾宝玉的关系是以姑表兄妹血缘为纽带。"
                        "宝玉说亲的消息直接导致黛玉病情加重，使其急怒攻心，惟求速死。"
                        "黛玉最终撕毁宝玉所赠之帕以断情，临终前直声呼唤“宝玉！宝玉！你好……”。"
                    ),
                    "source_id": "doc-097-chunk-001",
                    "file_path": "097-第九十七回-林黛玉焚稿断痴情 薛宝钗出闺成大礼.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("黛玉是怎么死的？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert "林黛玉的死亡经过" in answer.short_conclusion[0].text
    assert "急怒攻心" in answer.short_conclusion[0].text
    assert "姑表兄妹" not in answer.short_conclusion[0].text


def test_ask_engine_rejects_death_evidence_about_another_person():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "晴雯",
                    "tgt_id": "贾宝玉",
                    "keywords": "死亡,人物关系",
                    "description": "晴雯病重后被撵出，最终痨死，宝玉未及临终相见。",
                    "source_id": "doc-078-chunk-001",
                    "file_path": "078-第七十八回-老学士闲征姽婳词 痴公子杜撰芙蓉诔.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("林黛玉是怎么死的？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"


def test_ask_engine_rejects_candidate_about_different_subject_for_definition_question():
    response = {
        "status": "success",
        "data": {
            "entities": [
                {
                    "entity_name": "贾宝玉",
                    "entity_type": "person",
                    "description": "贾宝玉是荣国府贾政与王夫人的儿子，居于怡红院。",
                    "source_id": "doc-002-chunk-001",
                    "file_path": "002-第二回-贾夫人仙逝扬州城 冷子兴演说荣国府.txt",
                }
            ],
            "relationships": [],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("通灵宝玉是什么？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"


def test_ask_engine_returns_partial_for_mixed_query_data_question():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "林黛玉",
                    "tgt_id": "贾宝玉",
                    "keywords": "表兄妹,知己关系",
                    "description": "林黛玉和贾宝玉是姑表兄妹，第三回初见。",
                    "source_id": "doc-003-chunk-001",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("林黛玉和贾宝玉的关系是什么？再说明一个没有资料的后文细节", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "partial"
    assert "姑表兄妹" in answer.short_conclusion[0].text
    assert answer.refusal is not None
    assert answer.refusal.reason == "UNSUPPORTED_SUBCLAIM"
    assert "没有资料的后文细节" in answer.refusal.message


def test_ask_engine_refuses_location_answer_with_conflicting_chapter_sources():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "宝黛初会",
                    "tgt_id": "第三回",
                    "keywords": "发生章回",
                    "description": "宝黛初会发生在第三回。",
                    "source_id": "doc-003-chunk-001",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                },
                {
                    "src_id": "宝黛初会",
                    "tgt_id": "第五回",
                    "keywords": "发生章回",
                    "description": "错误候选说宝黛初会发生在第五回。",
                    "source_id": "doc-005-chunk-001",
                    "file_path": "005-第五回-贾宝玉神游太虚境 警幻仙曲演红楼梦.txt",
                },
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "SOURCE_CONFLICT"


def test_ask_engine_requires_location_candidate_keywords_for_location_answer():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "宝黛初会",
                    "tgt_id": "贾宝玉",
                    "keywords": "人物关系",
                    "description": "贾宝玉和林黛玉初见相关。",
                    "source_id": "doc-003-chunk-001",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"


def test_ask_engine_refuses_location_answer_from_reference_file_path_only():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [],
            "chunks": [],
            "references": [
                {
                    "reference_id": "1",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"


def test_ask_engine_refuses_location_answer_from_chunk_without_location_content():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [],
            "chunks": [
                {
                    "chunk_id": "doc-003-chunk-001",
                    "content": "林黛玉进贾府后与众人相见，贾宝玉随后出场。",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"


def test_ask_engine_refuses_single_candidate_with_multiple_chapter_sources():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "宝黛初会",
                    "tgt_id": "第三回",
                    "keywords": "发生章回",
                    "description": "宝黛初会发生在第三回。",
                    "source_id": "doc-003-chunk-001<SEP>doc-005-chunk-001",
                    "file_path": (
                        "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt<SEP>"
                        "005-第五回-贾宝玉神游太虚境 警幻仙曲演红楼梦.txt"
                    ),
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine().ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "SOURCE_CONFLICT"


def test_ask_engine_normalized_candidates_keep_query_data_as_only_generated_source():
    response = {
        "status": "success",
        "data": {
            "entities": [
                {
                    "entity_name": "宝黛初会",
                    "entity_type": "ChapterEpisode",
                    "description": "宝黛初会是宝玉和黛玉初次见面的情节。",
                    "source_id": "doc-003-chunk-001",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "relationships": [],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    [candidate] = normalize_query_data_response(response, question="宝黛初会发生在哪一回？")

    assert candidate.chapter_sources[0].chapter_number == 3
    assert candidate.raw["file_path"].startswith("003-")
