from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from hlm_kg.entity_resolver import ResolvedEntity
from hlm_kg.question_planner import QuestionSemantics


MAX_KNOWN_SUBJECT_ALIASES = 8
MAX_KNOWN_SUBJECT_AMBIGUITY = 8


class SemanticQuestionAnalyzerError(RuntimeError):
    """Raised when semantic question analysis cannot return a usable JSON plan."""


@dataclass(frozen=True)
class OpenAIQuestionAnalyzerConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 20.0
    max_tokens: int = 300

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "OpenAIQuestionAnalyzerConfig | None":
        base_url = _first_env(env, "HLM_ASK_PLANNER_BASE_URL", "LLM_BINDING_HOST").rstrip("/")
        model = _first_env(env, "HLM_ASK_PLANNER_MODEL", "LLM_MODEL")
        api_key = _first_env(env, "HLM_ASK_PLANNER_API_KEY", "LLM_BINDING_API_KEY") or None
        if not base_url or not model or _is_placeholder(model):
            return None
        if api_key is not None and _is_placeholder(api_key):
            api_key = None
        timeout_seconds = _float_env(env, "HLM_ASK_PLANNER_TIMEOUT_SECONDS", default=20.0)
        max_tokens = _int_env(env, "HLM_ASK_PLANNER_MAX_TOKENS", default=300)
        return cls(base_url=base_url, model=model, api_key=api_key, timeout_seconds=timeout_seconds, max_tokens=max_tokens)


class OpenAIQuestionAnalyzer:
    def __init__(self, config: OpenAIQuestionAnalyzerConfig) -> None:
        self.config = config

    def analyze(self, question: str, *, subjects: tuple[ResolvedEntity, ...]) -> QuestionSemantics:
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是《红楼梦》阅读产品的问题理解器。"
                        "只把用户问题转成开放证据合同 JSON，不回答事实，不补写证据，"
                        "不要把问题归入固定枚举类别。"
                        "question_focus 用一句话描述用户真正要问的事实焦点。"
                        "question_focus 和 required_evidence 只能描述证据类型，不得写候选答案、"
                        "不得加入用户未提及且尚未由候选证据提供的事实词。"
                        "required_evidence 写明候选证据必须满足的条件。"
                        "constraints 是字符串数组，可记录 first_mention 等约束。"
                        "known_subjects 是本地实体解析候选，可能包含 ambiguity；"
                        "你只能用它们帮助判断 subject_type_hint 和证据合同，不能把它们当作事实答案。"
                        "subject_type_hint 只能是 null、person、place、object、event、literary_text、concept。"
                        "answer_shape 只能是 null、short_direct、explanatory。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "known_subjects": [
                                _known_subject_payload(subject)
                                for subject in subjects
                            ],
                            "required_output": {
                                "question_focus": None,
                                "required_evidence": [],
                                "constraints": [],
                                "intent": "ask_fact",
                                "answer_shape": None,
                                "subject_type_hint": None,
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
        return QuestionSemantics(
            question_focus=_optional_string(data.get("question_focus")),
            required_evidence=_string_tuple(data.get("required_evidence")),
            constraints=_string_tuple(data.get("constraints")),
            intent=_optional_string(data.get("intent")),
            answer_shape=_optional_string(data.get("answer_shape")),
            subject_type_hint=_optional_string(data.get("subject_type_hint")),
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
            raise SemanticQuestionAnalyzerError(f"planner HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SemanticQuestionAnalyzerError(f"planner request failed: {exc.reason}") from exc
        if not body:
            raise SemanticQuestionAnalyzerError("planner returned an empty response")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SemanticQuestionAnalyzerError("planner returned invalid JSON") from exc

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers


def build_question_analyzer_from_env(env: Mapping[str, str]) -> OpenAIQuestionAnalyzer | None:
    config = OpenAIQuestionAnalyzerConfig.from_env(env)
    return OpenAIQuestionAnalyzer(config) if config is not None else None


def _known_subject_payload(subject: ResolvedEntity) -> dict[str, Any]:
    return {
        "mention": subject.mention,
        "canonical_name": subject.canonical_name,
        "canonical_type": subject.canonical_type,
        "confidence": subject.confidence,
        "aliases": list(subject.aliases[:MAX_KNOWN_SUBJECT_ALIASES]),
        "ambiguity": [
            {
                "name": candidate.name,
                "type": candidate.type,
            }
            for candidate in subject.ambiguity[:MAX_KNOWN_SUBJECT_AMBIGUITY]
        ],
    }


def _message_content(response: Any) -> str:
    if not isinstance(response, dict):
        raise SemanticQuestionAnalyzerError("planner response was not a JSON object")
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise SemanticQuestionAnalyzerError("planner response did not contain choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise SemanticQuestionAnalyzerError("planner response did not contain message content")
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
        raise SemanticQuestionAnalyzerError("planner message content was not JSON") from exc
    if not isinstance(data, dict):
        raise SemanticQuestionAnalyzerError("planner JSON was not an object")
    return data


def _first_env(env: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = str(env.get(name, "") or "").strip()
        if value:
            return value
    return ""


def _float_env(env: Mapping[str, str], name: str, *, default: float) -> float:
    value = str(env.get(name, "") or "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise SemanticQuestionAnalyzerError(f"invalid {name}; expected a number") from exc


def _int_env(env: Mapping[str, str], name: str, *, default: int) -> int:
    value = str(env.get(name, "") or "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise SemanticQuestionAnalyzerError(f"invalid {name}; expected an integer") from exc


def _is_placeholder(value: str) -> bool:
    clean = value.strip().lower()
    return clean in {"replace-me", "replace-with-your-llm-api-key"} or clean.startswith("replace-")


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        clean = value.strip()
        return (clean,) if clean else ()
    if not isinstance(value, list):
        return ()
    terms: list[str] = []
    for item in value:
        clean = str(item or "").strip()
        if clean and clean not in terms:
            terms.append(clean)
    return tuple(terms)
