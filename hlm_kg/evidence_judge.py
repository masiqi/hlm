from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from hlm_kg.evidence_adapter import EvidenceCandidate
from hlm_kg.semantic_question_analyzer import _first_env, _float_env, _int_env, _is_placeholder


class EvidenceJudgeError(RuntimeError):
    """Raised when an evidence judge cannot return a usable decision."""


@dataclass(frozen=True)
class EvidenceContract:
    question: str
    subject_terms: tuple[str, ...]
    question_focus: str
    required_evidence: tuple[str, ...]
    answer_shape: str


@dataclass(frozen=True)
class EvidenceJudgment:
    supported: bool
    answer_text: str = ""
    evidence_text: str = ""
    claim_type: str = "quotable_fact"
    refusal_reason: str = ""


class EvidenceJudge(Protocol):
    def judge(self, candidate: EvidenceCandidate, contract: EvidenceContract) -> EvidenceJudgment:
        """Decide whether a candidate directly supports the user's open question."""


@dataclass(frozen=True)
class OpenAIEvidenceJudgeConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 20.0
    max_tokens: int = 500

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "OpenAIEvidenceJudgeConfig | None":
        base_url = _first_env(
            env,
            "HLM_ASK_EVIDENCE_JUDGE_BASE_URL",
            "HLM_ASK_PLANNER_BASE_URL",
            "LLM_BINDING_HOST",
        ).rstrip("/")
        model = _first_env(env, "HLM_ASK_EVIDENCE_JUDGE_MODEL", "HLM_ASK_PLANNER_MODEL", "LLM_MODEL")
        api_key = _first_env(
            env,
            "HLM_ASK_EVIDENCE_JUDGE_API_KEY",
            "HLM_ASK_PLANNER_API_KEY",
            "LLM_BINDING_API_KEY",
        ) or None
        if not base_url or not model or _is_placeholder(model):
            return None
        if api_key is not None and _is_placeholder(api_key):
            api_key = None
        timeout_seconds = _float_env(env, "HLM_ASK_EVIDENCE_JUDGE_TIMEOUT_SECONDS", default=20.0)
        max_tokens = _int_env(env, "HLM_ASK_EVIDENCE_JUDGE_MAX_TOKENS", default=500)
        return cls(base_url=base_url, model=model, api_key=api_key, timeout_seconds=timeout_seconds, max_tokens=max_tokens)


class OpenAIEvidenceJudge:
    def __init__(self, config: OpenAIEvidenceJudgeConfig) -> None:
        self.config = config

    def judge(self, candidate: EvidenceCandidate, contract: EvidenceContract) -> EvidenceJudgment:
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是《红楼梦》阅读产品的证据判定器。"
                        "只判断候选资料是否直接回答用户问题，不补写事实，不使用候选资料以外的信息。"
                        "如果候选资料只能说明相关人物关系、背景或泛泛相关，但不能回答问题，supported 必须为 false。"
                        "answer_text 必须只包含候选资料直接支持的结论；evidence_text 必须摘取或概括候选资料中的支撑片段。"
                        "返回 JSON：supported、answer_text、evidence_text、claim_type、refusal_reason。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "contract": {
                                "question": contract.question,
                                "subject_terms": list(contract.subject_terms),
                                "question_focus": contract.question_focus,
                                "required_evidence": list(contract.required_evidence),
                                "answer_shape": contract.answer_shape,
                            },
                            "candidate": {
                                "kind": candidate.kind,
                                "title": candidate.title,
                                "description": candidate.description,
                                "relationship_keywords": candidate.relationship_keywords,
                                "chapter_sources": [
                                    {
                                        "chapter_number": source.chapter_number,
                                        "chapter_label": source.chapter_label,
                                        "chapter_title": source.chapter_title,
                                    }
                                    for source in candidate.chapter_sources
                                ],
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        response = self._post_json("/chat/completions", payload)
        content = _message_content(response)
        data = _json_object(content)
        return EvidenceJudgment(
            supported=bool(data.get("supported")),
            answer_text=str(data.get("answer_text") or "").strip(),
            evidence_text=str(data.get("evidence_text") or "").strip(),
            claim_type=str(data.get("claim_type") or "quotable_fact").strip() or "quotable_fact",
            refusal_reason=str(data.get("refusal_reason") or "").strip(),
        )

    def _post_json(self, path: str, payload: Mapping[str, Any]) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.base_url}{path}",
            data=data,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500] if exc.fp else ""
            raise EvidenceJudgeError(f"judge HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise EvidenceJudgeError(f"judge request failed: {exc.reason}") from exc
        if not body:
            raise EvidenceJudgeError("judge returned an empty response")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceJudgeError("judge returned invalid JSON") from exc

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers


def build_evidence_judge_from_env(env: Mapping[str, str]) -> OpenAIEvidenceJudge | None:
    config = OpenAIEvidenceJudgeConfig.from_env(env)
    return OpenAIEvidenceJudge(config) if config is not None else None


def _message_content(response: Any) -> str:
    if not isinstance(response, dict):
        raise EvidenceJudgeError("judge response was not a JSON object")
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise EvidenceJudgeError("judge response did not contain choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise EvidenceJudgeError("judge response did not contain message content")
    return content


def _json_object(content: str) -> dict[str, Any]:
    clean = content.strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        if clean.startswith("json"):
            clean = clean[4:].strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError as exc:
        raise EvidenceJudgeError("judge message content was not JSON") from exc
    if not isinstance(data, dict):
        raise EvidenceJudgeError("judge JSON was not an object")
    return data
