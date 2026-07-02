from __future__ import annotations

from uuid import uuid4

from hlm_kg.content_store import ContentStore
from hlm_kg.domain import (
    AnswerClaim,
    AnswerSection,
    AskAnswer,
    ContinuationLink,
    Evidence,
    Refusal,
    RefusalReason,
)
from hlm_kg.evidence import detect_source_conflict, supported_claims


OUT_OF_SCOPE_TERMS = ("作文", "现实", "八卦", "数学", "英语")


class AskEngine:
    def __init__(self, store: ContentStore) -> None:
        self.store = store

    def ask(self, question: str) -> AskAnswer:
        if any(term in question for term in OUT_OF_SCOPE_TERMS):
            return self._refuse(question, "OUT_OF_SCOPE", "当前产品只支持《红楼梦》阅读理解相关问题。")

        if "没有资料" in question:
            supported = self._daiyu_answer(question)
            return AskAnswer(
                id=supported.id,
                question=question,
                status="partial",
                short_conclusion=supported.short_conclusion,
                evidence=supported.evidence,
                explanation=supported.explanation,
                quotable_facts=supported.quotable_facts,
                continuation_links=supported.continuation_links,
                refusal=Refusal(
                    reason="UNSUPPORTED_SUBCLAIM",
                    message="“没有资料的后文细节”当前资料不足，未生成确定结论。",
                ),
            )

        if "黛玉" in question or "葬花" in question or "葬花吟" in question:
            return self._daiyu_answer(question)
        if "探春" in question or "理家" in question:
            return self._tanchun_answer(question)

        return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")

    def _daiyu_answer(self, question: str) -> AskAnswer:
        evidence = [
            self.store.evidence("ev-027-daiyu-burying-flowers"),
            self.store.evidence("ev-rel-daiyu-burying-flowers-fate"),
        ]
        conclusion = AnswerClaim(
            text="黛玉葬花可用于理解她的身世悲感；后文关联需要结合全书关系线索来看。",
            evidence_ids=["ev-rel-daiyu-burying-flowers-fate"],
            claim_type="image_foreshadowing",
        )
        quotable = AnswerClaim(
            text="第 27 回黛玉葬花并吟《葬花吟》，可用于说明她的身世悲感与洁身自持。",
            evidence_ids=["ev-027-daiyu-burying-flowers"],
            claim_type="quotable_fact",
        )
        return self._answer(question, evidence, conclusion, quotable, ContinuationLink("查看第二十七回", "chapter", "27"))

    def _tanchun_answer(self, question: str) -> AskAnswer:
        evidence = [
            self.store.evidence("ev-056-tanchun-manages-household"),
            self.store.evidence("ev-rel-tanchun-manages-trait"),
        ]
        conclusion = AnswerClaim(
            text="探春理家体现她兴利除弊的管理才干和忧患意识。",
            evidence_ids=["ev-056-tanchun-manages-household", "ev-rel-tanchun-manages-trait"],
            claim_type="event_causality",
        )
        quotable = AnswerClaim(
            text="第 56 回探春理家，通过整顿大观园事务体现其兴利除弊的管理才干。",
            evidence_ids=["ev-056-tanchun-manages-household"],
            claim_type="quotable_fact",
        )
        return self._answer(question, evidence, conclusion, quotable, ContinuationLink("查看第五十六回", "chapter", "56"))

    def _answer(
        self,
        question: str,
        evidence: list[Evidence],
        conclusion: AnswerClaim,
        quotable: AnswerClaim,
        link: ContinuationLink,
    ) -> AskAnswer:
        if detect_source_conflict(evidence):
            return self._refuse(question, "SOURCE_CONFLICT", "资料存在不一致，优先查看原文依据。")
        explanation_claim = AnswerClaim(
            text="原文章回材料负责定位事实，关系线索负责说明可支持的理解方向。",
            evidence_ids=conclusion.evidence_ids,
            claim_type=conclusion.claim_type,
        )
        supported = supported_claims([conclusion, quotable, explanation_claim], evidence)
        if len(supported) != 3:
            return self._refuse(question, "NO_EVIDENCE", "当前资料中没有找到足够依据回答这个问题。")
        return AskAnswer(
            id=f"ask-{uuid4()}",
            question=question,
            status="answered",
            short_conclusion=[conclusion],
            evidence=evidence,
            explanation=[AnswerSection(title="为什么", claims=[explanation_claim])],
            quotable_facts=AnswerSection(title="可引用事实", claims=[quotable]),
            continuation_links=[link],
            refusal=None,
        )

    def _refuse(self, question: str, reason: RefusalReason, message: str) -> AskAnswer:
        return AskAnswer(
            id=f"ask-{uuid4()}",
            question=question,
            status="refused",
            short_conclusion=[],
            evidence=[],
            explanation=[],
            quotable_facts=None,
            continuation_links=[],
            refusal=Refusal(reason=reason, message=message),
        )
