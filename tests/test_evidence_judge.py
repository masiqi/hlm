import json

from hlm_kg.chapter_sources import ChapterSource
from hlm_kg.evidence_adapter import EvidenceCandidate
from hlm_kg.evidence_judge import EvidenceContract, OpenAIEvidenceJudge, OpenAIEvidenceJudgeConfig


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_openai_evidence_judge_parses_supported_decision(monkeypatch):
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
                                    "supported": True,
                                    "answer_text": "林黛玉的病症线索是“不足之症”。",
                                    "evidence_text": "众人见黛玉身体面貌虽弱不胜衣，便知他有不足之症。",
                                    "claim_type": "quotable_fact",
                                    "refusal_reason": "",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    judge = OpenAIEvidenceJudge(
        OpenAIEvidenceJudgeConfig(base_url="http://judge.local/v1", model="judge-model", api_key="test-key", timeout_seconds=3)
    )
    candidate = EvidenceCandidate(
        kind="chunk",
        title="第三回",
        description="众人见黛玉身体面貌虽弱不胜衣，便知他有不足之症。",
        query_mode="original_text",
        chapter_sources=[
            ChapterSource(
                chapter_number=3,
                chapter_label="第三回",
                chapter_title="托内兄如海荐西宾 接外孙贾母惜孤女",
                source_file="003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
            )
        ],
    )
    contract = EvidenceContract(
        question="林黛玉生的什么病",
        subject_terms=("林黛玉", "黛玉"),
        question_focus="林黛玉的病症或身体状况",
        required_evidence=("候选证据必须直接说明林黛玉的病症、身体状况或长期服药线索",),
        answer_shape="short_direct",
    )

    judgment = judge.judge(candidate, contract)

    assert judgment.supported is True
    assert "不足之症" in judgment.answer_text
    assert "不足之症" in judgment.evidence_text
    assert captured["timeout"] == 3
    assert captured["payload"]["max_tokens"] == 500
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["messages"][0]["role"] == "system"
    user_payload = json.loads(captured["payload"]["messages"][1]["content"])
    assert user_payload["contract"]["question_focus"] == "林黛玉的病症或身体状况"
    assert user_payload["candidate"]["description"] == candidate.description


def test_openai_evidence_judge_config_uses_judge_env_before_planner_env():
    config = OpenAIEvidenceJudgeConfig.from_env(
        {
            "HLM_ASK_PLANNER_BASE_URL": "http://planner.local/v1",
            "HLM_ASK_PLANNER_MODEL": "planner-model",
            "HLM_ASK_EVIDENCE_JUDGE_BASE_URL": "http://judge.local/v1",
            "HLM_ASK_EVIDENCE_JUDGE_MODEL": "judge-model",
            "HLM_ASK_EVIDENCE_JUDGE_TIMEOUT_SECONDS": "5",
        }
    )

    assert config is not None
    assert config.base_url == "http://judge.local/v1"
    assert config.model == "judge-model"
    assert config.timeout_seconds == 5
