import json

from hlm_kg.entity_resolver import CandidateEntity, ResolvedEntity
from hlm_kg.semantic_question_analyzer import OpenAIQuestionAnalyzer, OpenAIQuestionAnalyzerConfig


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_openai_question_analyzer_parses_structured_semantics(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "question_focus": "林黛玉的病症或身体状况",
                                    "evidence_terms": ["病", "症", "药", "不足之症"],
                                    "required_evidence": ["候选证据必须直接说明林黛玉的病症、身体状况或长期服药线索"],
                                    "retrieval_queries": ["林黛玉 病症 服药 不足之症"],
                                    "constraints": [],
                                    "answer_dimensions": ["health"],
                                    "intent": "ask_fact",
                                    "answer_shape": "short_direct",
                                    "subject_type_hint": "person",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    analyzer = OpenAIQuestionAnalyzer(
        OpenAIQuestionAnalyzerConfig(base_url="http://planner.local/v1", model="test-model", api_key="test-key", timeout_seconds=3)
    )

    semantics = analyzer.analyze("林黛玉到底得的是什么病？", subjects=())

    assert semantics.question_focus == "林黛玉的病症或身体状况"
    assert semantics.evidence_terms == ()
    assert semantics.required_evidence == ("候选证据必须直接说明林黛玉的病症、身体状况或长期服药线索",)
    assert semantics.retrieval_queries == ()
    assert semantics.intent == "ask_fact"
    assert semantics.answer_shape == "short_direct"
    assert semantics.answer_dimensions == ("health",)
    assert semantics.subject_type_hint == "person"
    assert captured["timeout"] == 3
    assert captured["payload"]["max_tokens"] == 300
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert "retrieval_queries" not in captured["payload"]["messages"][0]["content"]
    assert "evidence_terms" not in captured["payload"]["messages"][0]["content"]
    assert captured["payload"]["messages"][1]["role"] == "user"
    assert "retrieval_queries" not in captured["payload"]["messages"][1]["content"]
    assert "evidence_terms" not in captured["payload"]["messages"][1]["content"]
    assert "answer_dimensions" in captured["payload"]["messages"][1]["content"]


def test_openai_question_analyzer_accepts_string_contract_fields(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "question_focus": "贾母临终前完成的最后一项具体事务或行为",
                                    "required_evidence": "原著中描写贾母病重弥留之际及交代后事的章节内容",
                                    "constraints": "严格依据原著，不使用影视改编",
                                    "answer_dimensions": "terminal_chronology",
                                    "intent": "ask_fact",
                                    "answer_shape": "short_direct",
                                    "subject_type_hint": "person",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    analyzer = OpenAIQuestionAnalyzer(
        OpenAIQuestionAnalyzerConfig(base_url="http://planner.local/v1", model="test-model", api_key="test-key")
    )

    semantics = analyzer.analyze("贾母生前做的最后一件事儿是什么", subjects=())

    assert semantics.question_focus == "贾母临终前完成的最后一项具体事务或行为"
    assert semantics.required_evidence == ("原著中描写贾母病重弥留之际及交代后事的章节内容",)
    assert semantics.constraints == ("严格依据原著，不使用影视改编",)
    assert semantics.answer_dimensions == ("terminal_chronology",)


def test_openai_question_analyzer_sends_known_subject_candidates(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "question_focus": "黛玉的死亡经过或原因",
                                    "required_evidence": ["候选证据必须直接说明所问人物的死亡经过或原因"],
                                    "constraints": [],
                                    "answer_dimensions": ["death"],
                                    "intent": "ask_fact",
                                    "answer_shape": "short_direct",
                                    "subject_type_hint": "person",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    analyzer = OpenAIQuestionAnalyzer(
        OpenAIQuestionAnalyzerConfig(base_url="http://planner.local/v1", model="test-model", api_key="test-key")
    )
    subjects = (
        ResolvedEntity(
            mention="黛玉",
            canonical_id=None,
            canonical_name=None,
            canonical_type=None,
            aliases=("黛玉",),
            confidence="ambiguous",
            ambiguity=(
                CandidateEntity(name="黛玉", type="image"),
                CandidateEntity(name="林黛玉", type="person"),
            ),
        ),
    )

    semantics = analyzer.analyze("黛玉是怎么死的？", subjects=subjects)

    user_payload = json.loads(captured["payload"]["messages"][1]["content"])
    assert user_payload["known_subjects"] == [
        {
            "mention": "黛玉",
            "canonical_name": None,
            "canonical_type": None,
            "confidence": "ambiguous",
            "aliases": ["黛玉"],
            "ambiguity": [
                {"name": "黛玉", "type": "image"},
                {"name": "林黛玉", "type": "person"},
            ],
        }
    ]
    assert semantics.subject_type_hint == "person"
    assert semantics.answer_dimensions == ("death",)


def test_openai_question_analyzer_config_uses_ask_planner_env_before_general_llm_env():
    config = OpenAIQuestionAnalyzerConfig.from_env(
        {
            "LLM_BINDING_HOST": "http://general.local/v1",
            "LLM_MODEL": "general-model",
            "HLM_ASK_PLANNER_BASE_URL": "http://planner.local/v1",
            "HLM_ASK_PLANNER_MODEL": "planner-model",
            "HLM_ASK_PLANNER_TIMEOUT_SECONDS": "7",
        }
    )

    assert config is not None
    assert config.base_url == "http://planner.local/v1"
    assert config.model == "planner-model"
    assert config.timeout_seconds == 7
