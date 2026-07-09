from pathlib import Path

from hlm_kg.evidence_adapter import normalize_query_data_response
from hlm_kg.ask_engine import AskEngine
from hlm_kg.content_store import ContentStore
from hlm_kg.domain import Evidence, validate_answer
from hlm_kg.evidence_judge import EvidenceJudgment
from hlm_kg.question_planner import QuestionSemantics


class StaticSemanticAnalyzer:
    def __init__(self, semantics: QuestionSemantics):
        self.semantics = semantics

    def analyze(self, question: str, *, subjects):
        return self.semantics


def make_engine(semantics: QuestionSemantics | None = None, *, evidence_judge=None) -> AskEngine:
    store = ContentStore.from_paths(Path("book/chapters_manifest.json"), Path("data/app"))
    analyzer = StaticSemanticAnalyzer(semantics) if semantics is not None else None
    return AskEngine(store, semantic_analyzer=analyzer, evidence_judge=evidence_judge)


def open_person_semantics(
    focus: str,
    *,
    evidence_terms: tuple[str, ...] = (),
    required_evidence: tuple[str, ...] = (),
    constraints: tuple[str, ...] = (),
    answer_shape: str | None = None,
    answer_dimensions: tuple[str, ...] = (),
) -> QuestionSemantics:
    return QuestionSemantics(
        question_focus=focus,
        evidence_terms=evidence_terms,
        required_evidence=required_evidence,
        constraints=constraints,
        answer_shape=answer_shape,
        answer_dimensions=answer_dimensions,
        subject_type_hint="person",
    )


def location_semantics() -> QuestionSemantics:
    return QuestionSemantics(
        question_focus="相关内容发生或出现的章回",
        evidence_terms=("发生章回", "发生在", "出现于", "出现在", "第", "回"),
        required_evidence=("候选证据必须直接说明相关内容发生或出现的章回",),
        answer_dimensions=("chapter_location",),
    )


class KeywordEvidenceJudge:
    def __init__(
        self,
        *,
        must_contain: tuple[str, ...],
        answer_text: str,
        evidence_text: str,
        claim_type: str = "quotable_fact",
    ) -> None:
        self.must_contain = must_contain
        self.answer_text = answer_text
        self.evidence_text = evidence_text
        self.claim_type = claim_type
        self.calls = []

    def judge(self, candidate, contract):
        self.calls.append((candidate, contract))
        text = "\n".join([candidate.title, candidate.description, candidate.relationship_keywords or ""])
        if all(term in text for term in self.must_contain):
            return EvidenceJudgment(
                supported=True,
                answer_text=self.answer_text,
                evidence_text=self.evidence_text,
                claim_type=self.claim_type,
            )
        return EvidenceJudgment(supported=False, refusal_reason="NO_DIRECT_SUPPORT")


class RejectAllEvidenceJudge:
    def judge(self, candidate, contract):
        return EvidenceJudgment(supported=False, refusal_reason="NO_DIRECT_SUPPORT")


class SupportFirstEvidenceJudge:
    def __init__(self) -> None:
        self.calls = []

    def judge(self, candidate, contract):
        self.calls.append(candidate.title)
        return EvidenceJudgment(
            supported=True,
            answer_text="林黛玉的病症线索是“不足之症”。",
            evidence_text="候选证据直接说明林黛玉有不足之症。",
            claim_type="direct_answer",
        )


class KeywordEchoEvidenceJudge:
    def __init__(self, supported_terms: tuple[str, ...]) -> None:
        self.supported_terms = supported_terms
        self.calls = []

    def judge(self, candidate, contract):
        self.calls.append(candidate.title)
        text = "\n".join([candidate.title, candidate.description, candidate.relationship_keywords or ""])
        if any(term in text for term in self.supported_terms):
            return EvidenceJudgment(
                supported=True,
                answer_text=candidate.description,
                evidence_text=candidate.description,
                claim_type="event_sequence",
            )
        return EvidenceJudgment(supported=False, refusal_reason="NO_DIRECT_SUPPORT")


class TerminalChronologyEvidenceJudge:
    def __init__(self) -> None:
        self.calls = []

    def judge(self, candidate, contract):
        self.calls.append(candidate)
        text = "\n".join([candidate.title, candidate.description, candidate.relationship_keywords or ""])
        if "满屋里瞧了一瞧" in text:
            return EvidenceJudgment(
                supported=True,
                answer_text="若按最后可见动作看，贾母是回光返照后睁眼满屋里瞧了一瞧；随后喉间略一响动，脸变笑容而去。",
                evidence_text="贾母合了一回眼，又睁着满屋里瞧了一瞧；听见贾母喉间略一响动，脸变笑容，竟是去了。",
                claim_type="event_sequence",
            )
        if candidate.kind in {"relationship", "entity"} and "史丫头没良心" in text:
            return EvidenceJudgment(
                supported=True,
                answer_text="贾母临终前说“最可恶的是史丫头没良心，怎么总不来瞧我”。",
                evidence_text="候选图谱资料称贾母临终前说“最可恶的是史丫头没良心，怎么总不来瞧我”。",
                claim_type="event_sequence",
            )
        return EvidenceJudgment(supported=False, refusal_reason="NO_DIRECT_SUPPORT")


def test_ask_engine_does_not_return_hardcoded_daiyu_sample_answer_without_retrieval():
    answer = make_engine().ask("黛玉葬花体现了什么？")

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"
    assert answer.short_conclusion == []


def test_ask_engine_returns_refusal_for_out_of_scope_question():
    answer = make_engine().ask("请帮我写一篇作文")

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "OUT_OF_SCOPE"


def test_ask_engine_does_not_return_hardcoded_tanchun_sample_answer_without_retrieval():
    answer = make_engine().ask("探春理家体现了什么性格？")

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"
    assert answer.short_conclusion == []


def test_ask_engine_does_not_make_partial_answer_from_hardcoded_daiyu_sample():
    answer = make_engine().ask("黛玉葬花体现了什么？再说明一个没有资料的后文细节")

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"
    assert answer.short_conclusion == []


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


def test_ask_engine_does_not_load_hardcoded_daiyu_evidence_without_retrieval():
    store = ConflictStore(ContentStore.from_paths(Path("book/chapters_manifest.json"), Path("data/app")))

    answer = AskEngine(store).ask("黛玉葬花体现了什么？")

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"
    assert answer.short_conclusion == []


class FakeLightRAGClient:
    def __init__(self, response):
        self.response = response
        self.queries = []

    def query_data(self, query: str, mode: str = "hybrid", **options):
        self.queries.append((query, mode, options))
        return self.response


EXPECTED_ASK_RETRIEVAL_OPTIONS = {
    "only_need_context": True,
    "top_k": 40,
    "chunk_top_k": 20,
    "enable_rerank": True,
    "max_entity_tokens": 6000,
    "max_relation_tokens": 8000,
    "max_total_tokens": 30000,
}


class FailingRetrievalClient:
    def query_data(self, query: str, mode: str = "hybrid", **options):
        raise AssertionError("retrieval should not be called when local judged evidence answers")


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
    answer = make_engine(location_semantics()).ask("宝黛初会发生在哪一回？", retrieval_client=client)

    validate_answer(answer)
    assert client.queries == [("宝黛初会发生在哪一回？", "mix", EXPECTED_ASK_RETRIEVAL_OPTIONS)]
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

    answer = make_engine(location_semantics()).ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

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
    assert client.queries == [("林黛玉和贾宝玉的关系是什么？", "mix", EXPECTED_ASK_RETRIEVAL_OPTIONS)]
    assert answer.status == "answered"
    assert "姑表兄妹" in answer.short_conclusion[0].text
    assert [link.target_id for link in answer.continuation_links] == ["3", "5"]
    assert answer.quotable_facts is not None
    assert "第3回" in answer.quotable_facts.claims[0].text


def test_ask_engine_stops_judging_after_first_supported_candidate():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [],
            "chunks": [
                {
                    "chunk_id": "doc-003-chunk-001",
                    "content": "林黛玉有不足之症，从会吃饭时便吃药。",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                },
                {
                    "chunk_id": "doc-003-chunk-002",
                    "content": "黛玉如今还是吃人参养荣丸。",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                },
                {
                    "chunk_id": "doc-003-chunk-003",
                    "content": "林黛玉身体面貌弱不胜衣。",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                },
            ],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }
    judge = SupportFirstEvidenceJudge()

    answer = make_engine(
        open_person_semantics(
            "林黛玉的病症或身体状况",
            evidence_terms=("不足之症", "人参养荣丸", "弱不胜衣"),
            answer_dimensions=("health",),
        ),
        evidence_judge=judge,
    ).ask("林黛玉生的什么病", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert len(judge.calls) == 1
    assert answer.evidence[0].evidence_text == "候选证据直接说明林黛玉有不足之症。"


def test_ask_engine_answers_from_local_judged_evidence_before_retrieval():
    judge = KeywordEvidenceJudge(
        must_contain=("不足之症",),
        answer_text="林黛玉的病症线索是“不足之症”。",
        evidence_text="第三回原文直接说明林黛玉有不足之症。",
    )

    answer = make_engine(
        open_person_semantics(
            "林黛玉的病症或身体状况",
            evidence_terms=("不足之症", "人参养荣丸"),
            answer_dimensions=("health",),
        ),
        evidence_judge=judge,
    ).ask("林黛玉生的什么病", retrieval_client=FailingRetrievalClient())

    validate_answer(answer)
    assert answer.status == "answered"
    assert "不足之症" in answer.short_conclusion[0].text
    assert answer.evidence[0].source_type == "original_text"


def test_ask_engine_does_not_use_subject_name_as_local_evidence_term():
    judge = KeywordEvidenceJudge(
        must_contain=("不足之症",),
        answer_text="林黛玉的病症线索是“不足之症”。",
        evidence_text="第三回原文直接说明林黛玉有不足之症。",
    )

    answer = make_engine(
        open_person_semantics(
            "林黛玉的病症或身体状况",
            evidence_terms=("林黛玉", "病症", "疾病", "不足之症", "肺疾", "咳嗽", "痰喘", "先天不足", "太医诊断", "药方"),
            answer_dimensions=("health",),
        ),
        evidence_judge=judge,
    ).ask("林黛玉生的什么病", retrieval_client=FailingRetrievalClient())

    validate_answer(answer)
    assert answer.status == "answered"
    assert any("不足之症" in candidate.description for candidate, _contract in judge.calls)


def test_ask_engine_does_not_use_planner_answer_terms_for_local_original_text():
    judge = KeywordEvidenceJudge(
        must_contain=("不足之症",),
        answer_text="林黛玉的病症线索是“不足之症”。",
        evidence_text="第三回原文直接说明林黛玉有不足之症。",
    )
    response = {"status": "success", "data": {"entities": [], "relationships": [], "chunks": [], "references": []}}

    answer = make_engine(
        QuestionSemantics(
            question_focus="林黛玉喜欢的颜色",
            evidence_terms=("不足之症", "人参养荣丸"),
            required_evidence=("候选证据必须直接说明林黛玉喜欢什么颜色",),
            subject_type_hint="person",
        ),
        evidence_judge=judge,
    ).ask("林黛玉喜欢什么颜色？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "refused"
    assert answer.refusal is not None
    assert answer.refusal.reason == "NO_EVIDENCE"


def test_ask_engine_does_not_call_planner_generated_retrieval_queries():
    response = {"status": "success", "data": {"entities": [], "relationships": [], "chunks": [], "references": []}}
    client = FakeLightRAGClient(response)

    answer = make_engine(
        QuestionSemantics(
            question_focus="林黛玉喜欢的颜色",
            evidence_terms=("不足之症",),
            required_evidence=("候选证据必须直接说明林黛玉喜欢什么颜色",),
            retrieval_queries=("林黛玉 不足之症 症状 原文", "太医 诊视 林黛玉 病情"),
            subject_type_hint="person",
        ),
        evidence_judge=RejectAllEvidenceJudge(),
    ).ask("林黛玉喜欢什么颜色？", retrieval_client=client)

    validate_answer(answer)
    assert answer.status == "refused"
    assert client.queries == [("林黛玉喜欢什么颜色？", "mix", EXPECTED_ASK_RETRIEVAL_OPTIONS)]


def test_ask_engine_prefers_chunk_evidence_over_broad_graph_summary():
    evidence_judge = SupportFirstEvidenceJudge()
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "林黛玉",
                    "tgt_id": "贾宝玉",
                    "keywords": "知己关系,病情",
                    "description": "林黛玉与贾宝玉关系很深。林黛玉有不足之症。",
                    "source_id": "doc-003-chunk-001",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "chunks": [
                {
                    "chunk_id": "doc-003-chunk-001",
                    "content": "众人见黛玉身体面貌虽弱不胜衣，便知他有不足之症。",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "references": [],
        },
        "metadata": {"query_mode": "mix"},
    }

    answer = make_engine(
        open_person_semantics(
            "林黛玉的病症、身体状况、人物关系、知己关系",
            evidence_terms=("不足之症",),
            required_evidence=("候选证据必须直接说明林黛玉的病症和身体状况，不要只概括人物关系",),
        ),
        evidence_judge=evidence_judge,
    ).ask("林黛玉得了什么病？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.evidence[0].source_type == "original_text"
    assert "不足之症" in answer.evidence[0].evidence_text
    assert "贾宝玉" not in answer.evidence[0].evidence_text
    assert evidence_judge.calls[0] == "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt"


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

    judge = KeywordEvidenceJudge(
        must_contain=("十来岁",),
        answer_text="贾宝玉最早被明确介绍的年龄线索是“十来岁”，可理解为十岁左右。",
        evidence_text="原文说“如今长了十来岁”，这是贾宝玉早期出场相关的年龄线索。",
    )
    answer = make_engine(
        open_person_semantics(
            "贾宝玉首次出场时的年龄线索",
            evidence_terms=("岁", "衔玉"),
            required_evidence=("候选证据必须直接说明贾宝玉首次出场或早期介绍中的年龄线索",),
            constraints=("first_mention",),
            answer_dimensions=("age",),
        ),
        evidence_judge=judge,
    ).ask("贾宝玉最早被资料介绍时多大年纪？", retrieval_client=FakeLightRAGClient(response))

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

    answer = make_engine(
        open_person_semantics(
            "麝月这时候的年龄线索",
            evidence_terms=("岁",),
            answer_dimensions=("age",),
        ),
        evidence_judge=RejectAllEvidenceJudge(),
    ).ask("麝月这时候是几岁？", retrieval_client=FakeLightRAGClient(response))

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

    answer = make_engine(
        open_person_semantics(
            "王熙凤首次出场时的年龄线索",
            evidence_terms=("岁",),
            constraints=("first_mention",),
            answer_dimensions=("age",),
        ),
        evidence_judge=RejectAllEvidenceJudge(),
    ).ask("王熙凤第一次在书中出现的时候是几岁？", retrieval_client=FakeLightRAGClient(response))

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

    judge = KeywordEvidenceJudge(
        must_contain=("急怒攻心", "临终"),
        answer_text="林黛玉的死亡经过可概括为：宝玉说亲的消息使她病情加重，急怒攻心，临终前直呼“宝玉”。",
        evidence_text="宝玉说亲的消息直接导致黛玉病情加重，使其急怒攻心，惟求速死；临终前直声呼唤“宝玉”。",
        claim_type="event_causality",
    )
    answer = make_engine(
        open_person_semantics(
            "林黛玉的死亡经过或原因",
            evidence_terms=("病情加重", "急怒攻心", "临终"),
            required_evidence=("候选证据必须直接说明林黛玉死亡的经过、原因或临终状态",),
            answer_dimensions=("death",),
        ),
        evidence_judge=judge,
    ).ask("林黛玉是怎么死的？", retrieval_client=FakeLightRAGClient(response))

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
    assert len(judge.calls) == 1


def test_ask_engine_chooses_death_chapter_from_broad_relationship_sources():
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
                    "source_id": "doc-003-chunk-001<SEP>doc-097-chunk-001<SEP>doc-098-chunk-001",
                    "file_path": (
                        "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt<SEP>"
                        "097-第九十七回-林黛玉焚稿断痴情 薛宝钗出闺成大礼.txt<SEP>"
                        "098-第九十八回-苦绛珠魂归离恨天 病神瑛泪洒相思地.txt"
                    ),
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    judge = KeywordEvidenceJudge(
        must_contain=("急怒攻心", "临终"),
        answer_text="林黛玉的死亡经过可概括为：宝玉说亲的消息使她病情加重，急怒攻心，临终前直呼“宝玉”。",
        evidence_text="宝玉说亲的消息直接导致黛玉病情加重，使其急怒攻心，惟求速死；临终前直声呼唤“宝玉”。",
        claim_type="event_causality",
    )
    answer = make_engine(
        open_person_semantics(
            "林黛玉的死亡经过或原因",
            required_evidence=("候选证据必须直接说明林黛玉死亡的经过、原因或临终状态",),
            answer_dimensions=("death",),
        ),
        evidence_judge=judge,
    ).ask("黛玉是怎么死的？", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.evidence[0].chapter == 97
    assert answer.evidence[0].location.startswith("第九十七回")
    assert [link.target_id for link in answer.continuation_links] == ["97"]


def test_ask_engine_answers_terminal_sequence_from_original_before_retrieval_noise():
    distractors = [
        {
            "src_id": "贾母",
            "tgt_id": f"泛泛关系{i}",
            "keywords": "人物关系",
            "description": f"贾母与泛泛关系{i}有关，但这里只说明日常关系和家族背景。",
            "source_id": f"doc-{i:03d}-chunk-001",
            "file_path": f"{i:03d}-测试回目.txt",
        }
        for i in range(2, 11)
    ]
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                *distractors,
                {
                    "src_id": "贾母",
                    "tgt_id": "临终场景",
                    "keywords": "临终,去世前,最后记录",
                    "description": (
                        "贾母临终前拉着宝玉、贾兰、凤姐说话，又问金刚经和史湘云。"
                        "随后回光返照，合眼又睁眼满屋里瞧了一瞧，喉间略一响动，脸变笑容而去。"
                    ),
                    "source_id": "doc-110-chunk-001",
                    "file_path": "110-第一百十回-史太君寿终归地府 王凤姐力诎失人心.txt",
                },
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }
    judge = KeywordEvidenceJudge(
        must_contain=("回光返照", "满屋里瞧了一瞧"),
        answer_text=(
            "原文没有单独标注“最后一件事”。若按最后清醒交代看，是临终前拉着宝玉、贾兰、凤姐说话，"
            "又问金刚经和史湘云；若按最后可见动作看，是回光返照后睁眼满屋里瞧了一瞧。"
        ),
        evidence_text=(
            "贾母临终前拉着宝玉、贾兰、凤姐说话，又问金刚经和史湘云；"
            "随后回光返照，合眼又睁眼满屋里瞧了一瞧。"
        ),
        claim_type="event_sequence",
    )

    client = FakeLightRAGClient(response)
    answer = make_engine(
        open_person_semantics(
            "贾母临终前最后被记录的行动、话语或状态",
            required_evidence=("候选证据必须直接说明贾母临终或去世前后的行动、话语或状态，并支持判断最后记录的事情",),
            answer_dimensions=("terminal_chronology",),
        ),
        evidence_judge=judge,
    ).ask("贾母生前做的最后一件事儿是什么", retrieval_client=client)

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.evidence[0].chapter == 110
    assert "满屋里瞧了一瞧" in answer.short_conclusion[0].text
    assert "泛泛关系" not in answer.short_conclusion[0].text
    assert client.queries == []
    assert any(candidate.kind == "chunk" and "满屋里瞧了一瞧" in candidate.description for candidate, _contract in judge.calls)


def test_ask_engine_prefers_later_supported_candidate_for_terminal_sequence_questions():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "贾母",
                    "tgt_id": "散余资",
                    "keywords": "临终前,最后记录,后事安排,分派财物,行动,话语,状态",
                    "description": (
                        "贾母临终前最后被记录的行动、话语或状态可理解为分派自己剩余的金银财物，"
                        "并交代家族产业与身后安排。"
                    ),
                    "source_id": "doc-107-chunk-001",
                    "file_path": "107-第一百七回-散馀资贾母明大义 复世职政老沐天恩.txt",
                },
                {
                    "src_id": "贾母",
                    "tgt_id": "临终分嘱",
                    "keywords": "临终,最后记录",
                    "description": "贾母临终前拉着宝玉、贾兰、凤姐说话；随后回光返照，睁眼满屋里瞧了一瞧。",
                    "source_id": "doc-110-chunk-001",
                    "file_path": "110-第一百十回-史太君寿终归地府 王凤姐力诎失人心.txt",
                },
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine(
        QuestionSemantics(
            question_focus="贾母临终前最后被记录的行动、话语或状态",
            required_evidence=("候选证据必须直接说明贾母临终或去世前后的行动、话语或状态，并支持判断最后记录的事情",),
            constraints=("time_bound_before_death", "final_in_sequence", "direct_action"),
            answer_dimensions=("terminal_chronology",),
            subject_type_hint="person",
            answer_shape="short_direct",
        ),
        evidence_judge=KeywordEchoEvidenceJudge(("分派", "满屋里瞧了一瞧")),
    ).ask("贾母生前做的最后一件事儿是什么", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.evidence[0].chapter == 110
    assert "满屋里瞧了一瞧" in answer.short_conclusion[0].text
    assert "分派自己剩余的金银财物" not in answer.short_conclusion[0].text


def test_ask_engine_verifies_terminal_graph_answer_against_original_text():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "贾母",
                    "tgt_id": "史湘云",
                    "keywords": "临终,最后记录",
                    "description": "贾母临终前说最可恶的是史丫头没良心，怎么总不来瞧我。",
                    "source_id": "doc-108-chunk-001",
                    "file_path": "108-第一百八回-强欢笑蘅芜庆生辰 死缠绵潇湘闻鬼哭.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }
    judge = TerminalChronologyEvidenceJudge()

    answer = make_engine(
        QuestionSemantics(
            question_focus="贾母临终前最后被记录的行动、话语或状态",
            required_evidence=("候选证据必须直接说明贾母临终或去世前后的行动、话语或状态，并支持判断最后记录的事情",),
            constraints=("time_bound_before_death", "final_in_sequence", "direct_action"),
            answer_dimensions=("terminal_chronology",),
            subject_type_hint="person",
            answer_shape="short_direct",
        ),
        evidence_judge=judge,
    ).ask("贾母生前做的最后一件事儿是什么", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.evidence[0].source_type == "original_text"
    assert answer.evidence[0].chapter == 110
    assert "满屋里瞧了一瞧" in answer.short_conclusion[0].text
    assert "史丫头没良心" not in answer.short_conclusion[0].text
    assert any(candidate.kind == "chunk" and "满屋里瞧了一瞧" in candidate.description for candidate in judge.calls)


def test_ask_engine_answers_terminal_question_from_local_original_before_retrieval():
    judge = TerminalChronologyEvidenceJudge()

    answer = make_engine(
        QuestionSemantics(
            question_focus="贾母临终前最后被记录的行动、话语或状态",
            required_evidence=("候选证据必须直接说明贾母临终或去世前后的行动、话语或状态，并支持判断最后记录的事情",),
            constraints=("time_bound_before_death", "final_in_sequence", "direct_action"),
            answer_dimensions=("terminal_chronology",),
            subject_type_hint="person",
            answer_shape="short_direct",
        ),
        evidence_judge=judge,
    ).ask("贾母生前做的最后一件事儿是什么", retrieval_client=FailingRetrievalClient())

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.evidence[0].source_type == "original_text"
    assert answer.evidence[0].chapter == 110
    assert "满屋里瞧了一瞧" in answer.short_conclusion[0].text


def test_ask_engine_chooses_terminal_source_from_broad_terminal_relationship():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "贾母",
                    "tgt_id": "史湘云",
                    "keywords": "临终,最后记录",
                    "description": "贾母临终前说最可恶的是史丫头没良心，怎么总不来瞧我。",
                    "source_id": "doc-107-chunk-001<SEP>doc-108-chunk-001<SEP>doc-110-chunk-001",
                    "file_path": (
                        "107-第一百七回-散馀资贾母明大义 复世职政老沐天恩.txt<SEP>"
                        "108-第一百八回-强欢笑蘅芜庆生辰 死缠绵潇湘闻鬼哭.txt<SEP>"
                        "110-第一百十回-史太君寿终归地府 王凤姐力诎失人心.txt"
                    ),
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine(
        QuestionSemantics(
            question_focus="贾母临终前最后被记录的行动、话语或状态",
            required_evidence=("候选证据必须直接说明贾母临终或去世前后的行动、话语或状态，并支持判断最后记录的事情",),
            constraints=("time_bound_before_death", "final_in_sequence", "direct_action"),
            answer_dimensions=("terminal_chronology",),
            subject_type_hint="person",
            answer_shape="short_direct",
        ),
        evidence_judge=KeywordEchoEvidenceJudge(("史丫头",)),
    ).ask("贾母生前做的最后一件事儿是什么", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.evidence[0].chapter == 110
    assert answer.evidence[0].location.startswith("第一百十回")
    assert [link.target_id for link in answer.continuation_links] == ["110"]


def test_ask_engine_does_not_apply_health_filter_from_excluded_evidence_requirement():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "贾母",
                    "tgt_id": "临终分嘱",
                    "keywords": "临终,最后记录",
                    "description": "贾母临终前说最可恶的是史丫头没良心，怎么总不来瞧我。",
                    "source_id": "doc-110-chunk-001",
                    "file_path": "110-第一百十回-史太君寿终归地府 王凤姐力诎失人心.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    answer = make_engine(
        QuestionSemantics(
            question_focus="贾母去世前最后完成的具体行为或事件",
            required_evidence=(
                "候选证据需明确记载贾母临终时间线，且能锁定其生前最后实施的具体事项。",
                "证据须直接对应去世前的时序终点，排除临终关怀、病情描写或非最终步骤的日常活动。",
            ),
            answer_dimensions=("terminal_chronology",),
            subject_type_hint="person",
            answer_shape="short_direct",
        ),
        evidence_judge=KeywordEchoEvidenceJudge(("史丫头",)),
    ).ask("贾母生前做的最后一件事儿是什么", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert answer.evidence[0].chapter == 110


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

    judge = KeywordEvidenceJudge(
        must_contain=("急怒攻心", "临终"),
        answer_text="林黛玉的死亡经过可概括为：宝玉说亲的消息使她病情加重，急怒攻心，临终前直呼“宝玉”。",
        evidence_text="宝玉说亲的消息直接导致黛玉病情加重，使其急怒攻心，惟求速死；临终前直声呼唤“宝玉”。",
        claim_type="event_causality",
    )
    answer = make_engine(
        open_person_semantics(
            "黛玉的死亡经过或原因",
            evidence_terms=("病情加重", "急怒攻心", "临终"),
            required_evidence=("候选证据必须直接说明黛玉死亡的经过、原因或临终状态",),
            answer_dimensions=("death",),
        ),
        evidence_judge=judge,
    ).ask("黛玉是怎么死的？", retrieval_client=FakeLightRAGClient(response))

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

    answer = make_engine(
        open_person_semantics(
            "林黛玉的死亡经过或原因",
            evidence_terms=("病情加重", "急怒攻心", "临终"),
            answer_dimensions=("death",),
        ),
        evidence_judge=RejectAllEvidenceJudge(),
    ).ask("林黛玉是怎么死的？", retrieval_client=FakeLightRAGClient(response))

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


def test_ask_engine_falls_back_to_original_text_when_relationship_hit_does_not_answer_health_question():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [
                {
                    "src_id": "林黛玉",
                    "tgt_id": "贾宝玉",
                    "keywords": "知己关系,病情",
                    "description": (
                        "林黛玉与贾宝玉的关系是以姑表兄妹血缘为纽带、刻骨铭心的知己之恋。"
                        "病中仍互问安好，紫鹃更指出黛玉之病多因宝玉，足见用情之深。"
                    ),
                    "source_id": "doc-003-chunk-001",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    judge = KeywordEvidenceJudge(
        must_contain=("不足之症",),
        answer_text="林黛玉的病症线索是“不足之症”；原文还说她从会吃饭时便吃药，仍吃人参养荣丸。",
        evidence_text="众人见黛玉身体面貌虽弱不胜衣，便知他有不足之症；黛玉说自己从会吃饭时便吃药，到如今还是吃人参养荣丸。",
    )
    answer = make_engine(
        open_person_semantics(
            "林黛玉的病症或身体状况",
            evidence_terms=("病", "症", "药"),
            required_evidence=("候选证据必须直接说明林黛玉的病症、身体状况或长期服药线索",),
            answer_dimensions=("health",),
        ),
        evidence_judge=judge,
    ).ask("林黛玉生的什么病", retrieval_client=FakeLightRAGClient(response))

    validate_answer(answer)
    assert answer.status == "answered"
    assert "不足之症" in answer.short_conclusion[0].text
    assert "便知他有不足之症" not in answer.short_conclusion[0].text
    assert "姑表兄妹" not in answer.short_conclusion[0].text
    assert len(answer.short_conclusion[0].text) < 180
    assert answer.evidence[0].chapter == 3
    assert answer.evidence[0].source_type == "original_text"
    assert "不足之症" in answer.evidence[0].evidence_text
    assert "从会吃饭时便吃药" in answer.evidence[0].evidence_text


def test_ask_engine_answers_health_question_from_original_text_without_retrieval_client():
    judge = KeywordEvidenceJudge(
        must_contain=("不足之症",),
        answer_text="林黛玉的病症线索是“不足之症”；原文还说她从会吃饭时便吃药，仍吃人参养荣丸。",
        evidence_text="众人见黛玉身体面貌虽弱不胜衣，便知他有不足之症；黛玉说自己从会吃饭时便吃药，到如今还是吃人参养荣丸。",
    )
    answer = make_engine(
        open_person_semantics(
            "林黛玉的病症或身体状况",
            evidence_terms=("病", "症", "药"),
            required_evidence=("候选证据必须直接说明林黛玉的病症、身体状况或长期服药线索",),
            answer_dimensions=("health",),
        ),
        evidence_judge=judge,
    ).ask("林黛玉生的什么病")

    validate_answer(answer)
    assert answer.status == "answered"
    assert "不足之症" in answer.short_conclusion[0].text
    assert "便知他有不足之症" not in answer.short_conclusion[0].text
    assert "葬花" not in answer.short_conclusion[0].text
    assert len(answer.short_conclusion[0].text) < 180
    assert answer.evidence[0].chapter == 3
    assert answer.evidence[0].source_type == "original_text"
    assert "从会吃饭时便吃药" in answer.evidence[0].evidence_text


def test_ask_engine_does_not_infer_dimensions_from_planner_text_markers():
    profile = make_engine(
        QuestionSemantics(
            question_focus="林黛玉的病症或身体状况",
            required_evidence=("候选证据必须直接说明林黛玉的病症、身体状况或长期服药线索",),
            subject_type_hint="person",
        )
    )._question_profile("林黛玉生的什么病")

    assert profile.dimensions == frozenset()


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

    answer = make_engine(location_semantics()).ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

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

    answer = make_engine(location_semantics()).ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

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

    answer = make_engine(location_semantics()).ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

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

    answer = make_engine(location_semantics()).ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

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

    answer = make_engine(location_semantics()).ask("宝黛初会发生在哪一回？", retrieval_client=FakeLightRAGClient(response))

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
