from dataclasses import dataclass, field

from hlm_kg.entity_resolver import EntityResolver
from hlm_kg.question_planner import QuestionPlanner, QuestionSemantics


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    type: str
    brief: str = ""
    text_understanding: list[str] = field(default_factory=list)
    understanding_angles: list[str] = field(default_factory=list)
    graph_relation_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    related_card_ids: list[str] = field(default_factory=list)


class Store:
    def __init__(self, cards):
        self.knowledge_cards = cards


class StaticSemanticAnalyzer:
    def __init__(self, semantics: QuestionSemantics):
        self.semantics = semantics

    def analyze(self, question: str, *, subjects):
        return self.semantics


class CapturingSemanticAnalyzer:
    def __init__(self, semantics: QuestionSemantics):
        self.semantics = semantics
        self.calls = []

    def analyze(self, question: str, *, subjects):
        self.calls.append((question, subjects))
        return self.semantics


class FailingSemanticAnalyzer:
    def analyze(self, question: str, *, subjects):
        raise RuntimeError("planner unavailable")


def make_planner(semantics: QuestionSemantics | None = None) -> QuestionPlanner:
    resolver = EntityResolver(
        Store(
            [
                Card(id="card-lindaiyu", name="林黛玉", type="person", brief="主要人物。"),
                Card(id="card-daiyu-image", name="黛玉", type="image", brief="黛玉相关意象。"),
                Card(id="card-jiabaoyu", name="贾宝玉", type="person", brief="荣国府公子。"),
                Card(id="card-tonglingbaoyu", name="通灵宝玉", type="object", brief="宝玉所佩之玉。"),
            ]
        )
    )
    analyzer = StaticSemanticAnalyzer(semantics) if semantics is not None else None
    return QuestionPlanner(resolver, semantic_analyzer=analyzer)


def open_semantics(
    focus: str,
    *,
    evidence_terms: tuple[str, ...] = (),
    required_evidence: tuple[str, ...] = (),
    retrieval_queries: tuple[str, ...] = (),
    constraints: tuple[str, ...] = (),
    answer_dimensions: tuple[str, ...] = (),
    subject_type_hint: str | None = "person",
) -> QuestionSemantics:
    return QuestionSemantics(
        question_focus=focus,
        evidence_terms=evidence_terms,
        required_evidence=required_evidence,
        retrieval_queries=retrieval_queries,
        constraints=constraints,
        answer_dimensions=answer_dimensions,
        subject_type_hint=subject_type_hint,
    )


def test_planner_does_not_infer_fixed_question_type_from_question_text_without_semantic_analyzer():
    plan = make_planner().plan("林黛玉是怎么死的？")

    assert [subject.canonical_name for subject in plan.subjects] == ["林黛玉"]
    assert plan.question_focus == ""
    assert plan.evidence_terms == ("死",)
    assert plan.constraints == ()
    assert plan.answer_dimensions == ()
    assert plan.answer_shape == "explanatory"


def test_planner_degrades_to_unclassified_plan_when_semantic_analyzer_fails():
    resolver = EntityResolver(Store([Card(id="card-lindaiyu", name="林黛玉", type="person", brief="主要人物。")]))
    plan = QuestionPlanner(resolver, semantic_analyzer=FailingSemanticAnalyzer()).plan("林黛玉到底得的是什么病？")

    assert [subject.canonical_name for subject in plan.subjects] == ["林黛玉"]
    assert plan.question_focus == ""
    assert "病" in plan.evidence_terms
    assert plan.constraints == ()
    assert plan.answer_dimensions == ()


def test_planner_maps_open_question_to_evidence_contract():
    plan = make_planner(
        open_semantics(
            "林黛玉的死亡经过或原因",
            evidence_terms=("病情加重", "急怒攻心", "临终"),
            required_evidence=("候选证据必须直接说明林黛玉死亡的经过、原因或临终状态",),
            answer_dimensions=("death",),
        )
    ).plan("林黛玉是怎么死的？")

    assert [subject.canonical_name for subject in plan.subjects] == ["林黛玉"]
    assert plan.intent == "ask_fact"
    assert plan.question_focus == "林黛玉的死亡经过或原因"
    assert plan.evidence_terms == ("死",)
    assert plan.answer_dimensions == ("death",)
    assert any("林黛玉" in requirement for requirement in plan.required_evidence)
    assert any("死亡" in requirement for requirement in plan.required_evidence)


def test_planner_uses_resolver_for_short_name_subject():
    plan = make_planner(open_semantics("黛玉的死亡经过或原因")).plan("黛玉是怎么死的？")

    assert [subject.canonical_name for subject in plan.subjects] == ["林黛玉"]
    assert plan.subject_terms == ("林黛玉", "黛玉")
    assert plan.question_focus == "黛玉的死亡经过或原因"


def test_planner_passes_preliminary_resolved_subjects_to_semantic_analyzer():
    analyzer = CapturingSemanticAnalyzer(open_semantics("黛玉的死亡经过或原因"))
    resolver = EntityResolver(
        Store(
            [
                Card(id="card-lindaiyu", name="林黛玉", type="person", brief="主要人物。"),
                Card(id="card-daiyu-image", name="黛玉", type="image", brief="黛玉相关意象。"),
            ]
        )
    )

    plan = QuestionPlanner(resolver, semantic_analyzer=analyzer).plan("黛玉是怎么死的？")

    assert [subject.canonical_name for subject in plan.subjects] == ["林黛玉"]
    assert len(analyzer.calls) == 1
    question, subjects = analyzer.calls[0]
    assert question == "黛玉是怎么死的？"
    assert [subject.mention for subject in subjects] == ["黛玉"]
    assert subjects[0].confidence == "ambiguous"
    assert {candidate.name for candidate in subjects[0].ambiguity} == {"黛玉", "林黛玉"}


def test_planner_keeps_object_subject_for_definition_question():
    plan = make_planner(open_semantics("通灵宝玉的身份或定义", subject_type_hint=None)).plan("通灵宝玉是什么？")

    assert [subject.canonical_name for subject in plan.subjects] == ["通灵宝玉"]
    assert plan.subjects[0].canonical_type == "object"
    assert plan.question_focus == "通灵宝玉的身份或定义"
    assert "贾宝玉" not in plan.subject_terms


def test_planner_records_first_mention_constraint_for_age_question():
    plan = make_planner(
        open_semantics(
            "贾宝玉首次出场时的年龄线索",
            evidence_terms=("岁",),
            constraints=("first_mention",),
            answer_dimensions=("age",),
        )
    ).plan("贾宝玉第一次在书中出现的时候是几岁？")

    assert [subject.canonical_name for subject in plan.subjects] == ["贾宝玉"]
    assert plan.question_focus == "贾宝玉首次出场时的年龄线索"
    assert "first_mention" in plan.constraints
    assert plan.answer_dimensions == ("age",)


def test_planner_maps_health_question_to_open_evidence_contract():
    plan = make_planner(
        open_semantics(
            "林黛玉的病症或身体状况",
            evidence_terms=("病", "症", "药"),
            required_evidence=("候选证据必须直接说明林黛玉的病症、身体状况或长期服药线索",),
            answer_dimensions=("health",),
        )
    ).plan("林黛玉生的什么病")

    assert [subject.canonical_name for subject in plan.subjects] == ["林黛玉"]
    assert plan.intent == "ask_fact"
    assert plan.question_focus == "林黛玉的病症或身体状况"
    assert plan.evidence_terms == ("生病", "病")
    assert plan.answer_dimensions == ("health",)
    assert any("病症" in requirement for requirement in plan.required_evidence)


def test_planner_ignores_invalid_answer_dimensions_from_semantic_analyzer():
    plan = make_planner(
        open_semantics(
            "林黛玉的病症或身体状况",
            answer_dimensions=("health", "unknown", "health", " death "),
        )
    ).plan("林黛玉生的什么病")

    assert plan.answer_dimensions == ("health", "death")


def test_planner_does_not_trust_llm_answer_terms_or_retrieval_queries():
    plan = make_planner(
        open_semantics(
            "林黛玉的病症或身体状况",
            evidence_terms=("林黛玉", "病", "不足之症", "太医", "人参养荣丸"),
            required_evidence=("候选证据必须直接说明林黛玉的病症、身体状况或长期服药线索",),
            retrieval_queries=("林黛玉 不足之症 症状 原文", "太医 诊视 林黛玉 病情"),
        )
    ).plan("林黛玉生的什么病")

    assert [subject.canonical_name for subject in plan.subjects] == ["林黛玉"]
    assert "病" in plan.evidence_terms
    assert "不足之症" not in plan.evidence_terms
    assert "太医" not in plan.evidence_terms
    assert "人参养荣丸" not in plan.evidence_terms
    assert plan.retrieval_queries == ()
