from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Mapping

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from hlm_kg.evidence_adapter import EvidenceCandidate, normalize_query_data_response
from hlm_kg.lightrag_client import LightRAGClient, LightRAGConfig
from scripts.import_chapter_cards import load_import_cards, write_import_cards


PROMPT_NAME = "hongloumeng_chapter_review_card"
PROMPT_VERSION = "2026-07-01"
DEFAULT_SAMPLE_CHAPTERS = [3, 5, 8, 27, 31, 33, 56, 63, 74, 97]
JSON_BLOCK_RE = re.compile(r"```json\s*(?P<json>\{.*?\})\s*```", re.DOTALL)
STUDENT_FORBIDDEN_TERMS = (
    "LightRAG",
    "RAG",
    "知识图谱",
    "向量检索",
    "置信度",
    "模型分数",
    "标准答案",
    "题库",
    "下一题",
    "提交答案",
    "批改",
)
REQUIRED_APP_IMPORT_FIELDS = (
    "id",
    "chapter",
    "source",
    "plain_summary",
    "plot_chain",
    "key_events",
    "key_characters",
    "current_chapter_foreshadowing_signals",
    "later_association_relation_ids",
    "quotable_fact_ids",
    "retrieval_tags",
    "understanding_focus",
)
EXTENDED_APP_IMPORT_LIST_FIELDS = (
    "characters",
    "relationships",
    "places",
    "objects",
    "literary_texts",
    "modern_explanations",
    "later_associations",
    "annotations",
)
REQUIRED_NON_EMPTY_RICH_FIELDS = ("characters", "relationships", "annotations")
SUMMARY_MIN_CHARS = 250
SUMMARY_MAX_CHARS = 400
DISPLAY_CARD_FIELDS = (
    "plain_summary",
    "plot_chain",
    "key_events",
    "current_chapter_foreshadowing_signals",
    "retrieval_tags",
    "understanding_focus",
    *EXTENDED_APP_IMPORT_LIST_FIELDS,
)
LATER_ASSOCIATION_TERMS = ("后文", "后续", "后来", "照应", "伏笔", "命运", "关联", "跨章")
LATER_ASSOCIATION_STOP_TERMS = {
    "本回",
    "后文",
    "后续",
    "后来",
    "照应",
    "伏笔",
    "命运",
    "关联",
    "跨章",
    "关系",
    "线索",
    "证据",
    "情节",
    "结构",
}


class LLMConfig:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: float = 240.0):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "LLMConfig":
        base_url = env.get("LLM_BINDING_HOST", "").strip().rstrip("/")
        api_key = env.get("LLM_BINDING_API_KEY", "").strip()
        model = env.get("LLM_MODEL", "").strip()
        missing = [name for name, value in {"LLM_BINDING_HOST": base_url, "LLM_BINDING_API_KEY": api_key, "LLM_MODEL": model}.items() if not value]
        if missing:
            raise ValueError(f"missing LLM env keys: {', '.join(missing)}")
        for key, value in {"LLM_BINDING_API_KEY": api_key, "LLM_MODEL": model}.items():
            lowered = value.lower()
            if any(marker in lowered for marker in ("replace-with", "replace-me", "your-", "your_", "changeme")):
                raise ValueError(f"{key} still contains a placeholder value")
        timeout_seconds = float(env.get("LLM_TIMEOUT", "240") or "240")
        return cls(base_url=base_url, api_key=api_key, model=model, timeout_seconds=timeout_seconds)


class OpenAICompatibleLLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是严格依据输入材料生成《红楼梦》章节复习卡的语文老师。不得编造事实。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "stream": False,
        }
        response = self._post_json("/chat/completions", payload)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("LLM response did not contain choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise ValueError("LLM response did not contain a message")
        content = str(message.get("content") or "").strip()
        if not content:
            raise ValueError("LLM response content was empty")
        return content

    def _post_json(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.config.base_url + path,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
        payload = json.loads(body.decode("utf-8")) if body else {}
        if not isinstance(payload, dict):
            raise ValueError("LLM response was not a JSON object")
        return payload


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def parse_chapter_selection(value: str, *, all_chapters: bool) -> list[int]:
    if all_chapters:
        return list(range(1, 121))
    if not value.strip():
        return list(DEFAULT_SAMPLE_CHAPTERS)
    chapters = []
    for part in value.split(","):
        chapter = int(part.strip())
        if chapter < 1 or chapter > 120:
            raise ValueError("chapters must be in 1..120")
        chapters.append(chapter)
    return sorted(set(chapters))


def generate_cards(
    *,
    manifest_path: Path,
    output_dir: Path,
    chapters: list[int],
    lightrag_client: Any,
    llm_client: Any,
    generated_at: str,
    overwrite: bool = False,
    json_only: bool = False,
    max_evidence_candidates: int | None = None,
) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_number = {int(item["number"]): item for item in manifest["chapters"]}
    markdown_dir = output_dir / "chapter_cards_markdown"
    import_dir = output_dir / "chapter_cards_import"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    import_dir.mkdir(parents=True, exist_ok=True)

    cards: list[dict[str, Any]] = []
    for chapter_number in chapters:
        item = by_number[chapter_number]
        markdown_path = markdown_dir / f"{chapter_number:03d}.md"
        json_path = import_dir / f"{chapter_number:03d}.json"
        if not overwrite and markdown_path.exists() and json_path.exists():
            cards.append(json.loads(json_path.read_text(encoding="utf-8")))
            continue

        chapter_text = Path(item["file_path"]).read_text(encoding="utf-8")
        evidence = fetch_lightrag_evidence(lightrag_client, chapter_number, str(item["title"]))
        evidence_pack = build_evidence_pack(
            evidence,
            question=_chapter_evidence_question(chapter_number, str(item["title"])),
            chapter_number=chapter_number,
            max_candidates=max_evidence_candidates,
        )
        prompt = build_json_only_prompt(
            chapter_number=chapter_number,
            chapter_title=str(item["title"]),
            source_file=str(item["file_path"]),
            chapter_text=chapter_text,
            lightrag_evidence=evidence_pack,
            generated_at=generated_at,
        ) if json_only else build_prompt(
            chapter_number=chapter_number,
            chapter_title=str(item["title"]),
            source_file=str(item["file_path"]),
            chapter_text=chapter_text,
            lightrag_evidence=evidence_pack,
            generated_at=generated_at,
        )
        markdown = llm_client.complete(prompt)
        try:
            card = extract_app_import_json(markdown)
        except ValueError:
            failed_dir = output_dir / "failed"
            failed_dir.mkdir(parents=True, exist_ok=True)
            failed_path = failed_dir / f"{chapter_number:03d}.md"
            failed_path.write_text(markdown, encoding="utf-8")
            repair_prompt = build_repair_prompt(
                chapter_number=chapter_number,
                chapter_title=str(item["title"]),
                generated_at=generated_at,
                previous_output=markdown,
            )
            repaired = llm_client.complete(repair_prompt)
            card = extract_app_import_json("AppImportJSON\n" + repaired)
            markdown = markdown.rstrip() + "\n\n## AppImportJSON 修复输出\n\n" + repaired
        card["chapter"] = chapter_number
        card.setdefault("id", f"review-{chapter_number:03d}")
        card.setdefault(
            "source",
            {
                "prompt_name": PROMPT_NAME,
                "prompt_version": PROMPT_VERSION,
                "generated_at": generated_at,
            },
        )
        _attach_evidence_audit(card, evidence_pack, evidence)
        validation_errors = validate_generated_card_output(markdown, card, evidence_pack=evidence_pack)
        if validation_errors:
            failed_dir = output_dir / "failed"
            failed_dir.mkdir(parents=True, exist_ok=True)
            failed_path = failed_dir / f"{chapter_number:03d}.md"
            failed_path.write_text(markdown, encoding="utf-8")
            raise ValueError(f"generated chapter {chapter_number:03d} failed quality gate: {'; '.join(validation_errors[:3])}")
        markdown_path.write_text(markdown, encoding="utf-8")
        json_path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cards.append(card)
        print(f"generated chapter {chapter_number:03d}: {item['title']}")

    combined_cards = load_generated_import_cards(import_dir)
    combined_path = output_dir / "chapter_review_cards.raw.json"
    write_import_cards(combined_cards, combined_path)
    return sorted(combined_cards, key=lambda card: int(card["chapter"]))


def load_generated_import_cards(import_dir: Path) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for path in sorted(import_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path} must contain a JSON object")
        cards.append(payload)
    return sorted(cards, key=lambda card: int(card["chapter"]))


def fetch_lightrag_evidence(lightrag_client: Any, chapter_number: int, chapter_title: str) -> dict[str, Any]:
    query = _chapter_evidence_question(chapter_number, chapter_title)
    return lightrag_client.query_data(query, mode="hybrid", only_need_context=True)


def _chapter_evidence_question(chapter_number: int, chapter_title: str) -> str:
    return (
        f"第{chapter_number}回 {chapter_title} 的主要人物、事件、地点、物件、意象、"
        "伏笔、后文关联、人物关系和命运线索"
    )


def build_evidence_pack(
    query_data_response: Mapping[str, Any],
    *,
    question: str = "",
    chapter_number: int | None = None,
    max_candidates: int | None = None,
) -> dict[str, Any]:
    candidates = normalize_query_data_response(query_data_response, question=question)
    if max_candidates is not None and max_candidates > 0:
        candidates = candidates[:max_candidates]
    safe_candidates = [_candidate_to_prompt_item(candidate) for candidate in candidates]
    later_candidates = [
        item
        for candidate, item in zip(candidates, safe_candidates)
        if _candidate_supports_later_association(candidate, item, chapter_number=chapter_number)
    ]
    return {
        "name": "全书关系线索",
        "candidate_count": len(safe_candidates),
        "candidates": safe_candidates,
        "later_association_evidence": later_candidates,
    }


def _candidate_to_prompt_item(candidate: EvidenceCandidate) -> dict[str, Any]:
    item: dict[str, Any] = {
        "kind": candidate.kind,
        "title": candidate.title,
        "description": candidate.description,
        "source_chapters": [source.chapter_number for source in candidate.chapter_sources],
    }
    if candidate.relationship_keywords:
        item["relationship_keywords"] = candidate.relationship_keywords
    if candidate.entity_type:
        item["entity_type"] = candidate.entity_type
    if candidate.source_ids:
        item["source_ids"] = candidate.source_ids
    if candidate.reference_id:
        item["reference_id"] = candidate.reference_id
    if candidate.chunk_id:
        item["chunk_id"] = candidate.chunk_id
    return item


def _candidate_supports_later_association(
    candidate: EvidenceCandidate,
    item: Mapping[str, Any],
    *,
    chapter_number: int | None,
) -> bool:
    source_chapters = [source.chapter_number for source in candidate.chapter_sources]
    has_later_chapter = chapter_number is None or any(source > chapter_number for source in source_chapters)
    if not has_later_chapter:
        return False
    text = " ".join(
        str(value)
        for value in (
            item.get("title"),
            item.get("description"),
            item.get("relationship_keywords"),
            item.get("entity_type"),
        )
        if value is not None
    )
    return any(term in text for term in LATER_ASSOCIATION_TERMS)


def _attach_evidence_audit(card: dict[str, Any], evidence_pack: Mapping[str, Any], raw_evidence: Mapping[str, Any]) -> None:
    internal = card.setdefault("internal", {})
    if not isinstance(internal, dict):
        internal = {}
        card["internal"] = internal
    internal["evidence_audit"] = {
        "source": "LightRAG /query/data",
        "normalized_candidate_count": evidence_pack.get("candidate_count", 0),
        "later_association_evidence_count": len(evidence_pack.get("later_association_evidence") or []),
        "raw_response_status": raw_evidence.get("status"),
    }


def build_prompt(
    *,
    chapter_number: int,
    chapter_title: str,
    source_file: str,
    chapter_text: str,
    lightrag_evidence: Mapping[str, Any],
    generated_at: str,
) -> str:
    evidence_pack = lightrag_evidence
    if not (
        isinstance(evidence_pack, Mapping)
        and evidence_pack.get("name") == "全书关系线索"
        and isinstance(evidence_pack.get("candidates"), list)
    ):
        evidence_pack = build_evidence_pack(
            lightrag_evidence,
            question=_chapter_evidence_question(chapter_number, chapter_title),
            chapter_number=chapter_number,
        )
    evidence_text = json.dumps(evidence_pack, ensure_ascii=False, indent=2)[:30000]
    return f"""你是一位精通《红楼梦》整本书阅读、高中语文名著阅读命题、人物关系分析、叙事结构分析和考试答题训练的语文老师。

你的任务是基于以下材料，为《红楼梦》某一回生成章节复习卡。目标是帮助高中生在有限时间内快速理解本回内容，并最终支撑“8小时读懂全书”。

你必须严格遵守：

1. 本回事实必须来自“本回原文”。
2. 后文关联、跨章伏笔、命运照应必须来自“系统提供的全书关系线索”或明确后续章回证据。
3. 如果系统提供的全书关系线索不足，不要编造，写“本回暂不能确定”或“需结合后文”。
4. 不要把影视剧、续书、脂批争议内容混成本回原文事实。
5. 输出中文。
6. 不要写空泛套话；每个重要判断都要绑定具体情节或文本依据。
7. 完整 Markdown 章节复习卡和 AppImportJSON 的学生可见文字都不得出现这些词：LightRAG、RAG、知识图谱、向量检索、置信度、模型分数、标准答案、题库、下一题、提交答案、批改。
8. 生成内容不是题库，不要设计刷题流程，不要写评分标准。
9. 必须直接从“AppImportJSON”开始输出，不要输出寒暄、解释、免责声明或“好的同学”之类开场白。

章节编号：
{chapter_number}

章节标题：
{chapter_title}

章节文件：
{source_file}

本回原文：
{chapter_text}

系统提供的全书关系线索：
{evidence_text}

请输出两部分。

第一部分：AppImportJSON

必须从下面这一行开始，不要在它前面添加任何文字：

AppImportJSON

输出一个 JSON 对象，字段必须完全符合下面结构：

```json
{{
  "id": "review-{chapter_number:03d}",
  "chapter": {chapter_number},
  "source": {{
    "prompt_name": "{PROMPT_NAME}",
    "prompt_version": "{PROMPT_VERSION}",
    "generated_at": "{generated_at}"
  }},
  "plain_summary": "250—400 字本回梗概，不能出现禁用词",
  "plot_chain": ["关键情节节点，按原文顺序"],
  "key_events": ["本回关键事件"],
  "key_characters": [],
  "current_chapter_foreshadowing_signals": ["本回原文中能看出的伏笔或暗示"],
  "later_association_relation_ids": [],
  "quotable_fact_ids": [],
  "retrieval_tags": ["#红楼梦", "#第{chapter_number}回", "#{chapter_title}"],
  "understanding_focus": ["本回最该怎么读、抓什么关系、答题时注意什么"],
  "characters": [
    {{
      "name": "人物名",
      "aliases": ["称谓或别名"],
      "role": "身份/关系",
      "actions": ["本回主要行为"],
      "traits": ["有情节支撑的性格特点"],
      "evidence": ["具体情节或短依据"],
      "importance": "本回作用"
    }}
  ],
  "relationships": [
    {{
      "source": "人物/事件/物件",
      "type": "关系类型",
      "target": "人物/事件/物件",
      "description": "具体关系说明",
      "chapter_evidence": "本回依据"
    }}
  ],
  "places": [
    {{
      "name": "地点名",
      "scenes": ["出现的情节场景"],
      "function": "对人物/主题/情节的作用"
    }}
  ],
  "objects": [
    {{
      "name": "物件/意象名",
      "context": "原文情境",
      "meaning": "象征或作用",
      "related_entities": ["相关人物或事件"]
    }}
  ],
  "literary_texts": [
    {{
      "title": "诗词曲文/对联/判词/语言细节",
      "short_quote": "不超过80字的短摘录",
      "explanation": "现代解释",
      "function": "作用分析"
    }}
  ],
  "modern_explanations": [
    {{
      "quote": "原文语句",
      "modern_text": "现代汉语解释",
      "value": "理解重点或考查价值"
    }}
  ],
  "later_associations": [],
  "annotations": [
    {{
      "text": "原文中可点击的词语",
      "kind": "person/event/object/place/foreshadowing/literary_text",
      "target": "对应信息卡或实体名",
      "note": "点击后展示的简要说明"
    }}
  ]
}}
```

注意：
- AppImportJSON 必须是合法 JSON。
- key_characters、later_association_relation_ids、quotable_fact_ids 暂时留空数组，除非输入材料明确提供了已经存在的 ID。
- later_associations 默认输出空数组；只有系统提供的全书关系线索或明确后续章回证据足以支撑时，才可填入对象。
- plain_summary、plot_chain、key_events、current_chapter_foreshadowing_signals、understanding_focus、characters、relationships、places、objects、literary_texts、modern_explanations、later_associations、annotations 中不得出现禁用词。

第二部分：完整 Markdown 章节复习卡

AppImportJSON 输出完整后，再输出完整 Markdown 章节复习卡。

Markdown 部分必须从下面标题行开始：

# 第{chapter_number}回 {chapter_title} 章节复习卡

Markdown 必须包含以下栏目：

# 第{chapter_number}回 {chapter_title} 章节复习卡

## 1. 本回一句话概括
## 2. 本回梗概
250—400 字，按情节发展顺序写。
## 3. 情节链梳理
列出 8—15 个关键情节节点，说明涉及人物、起因、经过、结果、作用/意义、是否伏笔。
## 4. 主要人物与本回表现
## 5. 人物关系图谱
## 6. 关键地点与环境描写
## 7. 关键物件、意象与象征
## 8. 诗词曲文、对联、判词、灯谜、花签、题额与语言细节
## 9. 主题与艺术手法
## 10. 伏笔、照应与后文关联
后文关联必须引用系统提供的全书关系线索；没有可靠线索时写“本回暂不能确定”。
## 11. 高频考点整理
只整理考点，不要变成题库。
## 12. 易错点与辨析
## 13. 关键语句现代汉语解释
## 14. 本回核心知识卡片
## 15. 关系线索三元组
## 16. 实体清单
## 17. 检索标签
## 18. 本回复习建议
## 19. 待补充说明
"""


def build_json_only_prompt(
    *,
    chapter_number: int,
    chapter_title: str,
    source_file: str,
    chapter_text: str,
    lightrag_evidence: Mapping[str, Any],
    generated_at: str,
) -> str:
    full_prompt = build_prompt(
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        source_file=source_file,
        chapter_text=chapter_text,
        lightrag_evidence=lightrag_evidence,
        generated_at=generated_at,
    )
    marker = "第二部分：完整 Markdown 章节复习卡"
    json_prompt = full_prompt.split(marker, 1)[0].rstrip()
    return (
        json_prompt
        + "\n\n只输出第一部分 AppImportJSON，不要输出 Markdown 章节复习卡。"
        + "\n输出必须从 AppImportJSON 开始，并包含一个合法 JSON 代码块。"
    )


def build_repair_prompt(*, chapter_number: int, chapter_title: str, generated_at: str, previous_output: str) -> str:
    return f"""上一次输出没有包含可解析的 AppImportJSON。请只输出 AppImportJSON 的 JSON 代码块，不要输出解释文字。

章节编号：{chapter_number}
章节标题：{chapter_title}

必须输出：

```json
{{
  "id": "review-{chapter_number:03d}",
  "chapter": {chapter_number},
  "source": {{
    "prompt_name": "{PROMPT_NAME}",
    "prompt_version": "{PROMPT_VERSION}",
    "generated_at": "{generated_at}"
  }},
  "plain_summary": "250—400 字本回梗概，不能出现禁用词",
  "plot_chain": ["关键情节节点，按原文顺序"],
  "key_events": ["本回关键事件"],
  "key_characters": [],
  "current_chapter_foreshadowing_signals": ["本回原文中能看出的伏笔或暗示"],
  "later_association_relation_ids": [],
  "quotable_fact_ids": [],
  "retrieval_tags": ["#红楼梦", "#第{chapter_number}回", "#{chapter_title}"],
  "understanding_focus": ["本回最该怎么读、抓什么关系、答题时注意什么"],
  "characters": [],
  "relationships": [],
  "places": [],
  "objects": [],
  "literary_texts": [],
  "modern_explanations": [],
  "later_associations": [],
  "annotations": []
}}
```

禁止在 plain_summary、plot_chain、key_events、current_chapter_foreshadowing_signals、understanding_focus、characters、relationships、places、objects、literary_texts、modern_explanations、later_associations、annotations 中出现：LightRAG、RAG、知识图谱、向量检索、置信度、模型分数、标准答案、题库、下一题、提交答案、批改。
如果没有可靠的系统提供的全书关系线索，later_associations 输出空数组，不要编造后文关联。

上一次输出如下，可用于提取内容：

{previous_output[:20000]}
"""


def extract_app_import_json(markdown: str) -> dict[str, Any]:
    marker_index = markdown.find("AppImportJSON")
    if marker_index == -1:
        raise ValueError("LLM output did not contain AppImportJSON")
    tail = markdown[marker_index:]
    match = JSON_BLOCK_RE.search(tail)
    raw_json = match.group("json") if match else _extract_balanced_json(tail)
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AppImportJSON is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("AppImportJSON must be a JSON object")
    return payload


def validate_generated_card_output(
    markdown: str,
    card: Mapping[str, Any],
    *,
    evidence_pack: Mapping[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    stripped = markdown.lstrip()
    first_line = stripped.splitlines()[0].strip() if stripped else ""
    if not (first_line.startswith("# 第") or first_line == "AppImportJSON"):
        errors.append("输出不得以寒暄开头，必须直接从 AppImportJSON 或章节标题开始。")

    for term in STUDENT_FORBIDDEN_TERMS:
        if term in markdown:
            errors.append(f"完整 Markdown 包含学生端禁用词：{term}")

    for field in REQUIRED_APP_IMPORT_FIELDS:
        if field not in card:
            errors.append(f"AppImportJSON 缺少必填字段：{field}")

    summary = str(card.get("plain_summary") or "").strip()
    if not summary:
        errors.append("AppImportJSON 字段 plain_summary 不能为空。")
    elif not SUMMARY_MIN_CHARS <= len(summary) <= SUMMARY_MAX_CHARS:
        errors.append("AppImportJSON 字段 plain_summary 必须为 250—400 字。")

    list_fields = (
        "plot_chain",
        "key_events",
        "key_characters",
        "current_chapter_foreshadowing_signals",
        "later_association_relation_ids",
        "quotable_fact_ids",
        "retrieval_tags",
        "understanding_focus",
    )
    for field in list_fields:
        if field in card and not isinstance(card[field], list):
            errors.append(f"AppImportJSON 字段 {field} 必须是数组。")
    if isinstance(card.get("plot_chain"), list) and not card["plot_chain"]:
        errors.append("AppImportJSON 字段 plot_chain 不能为空。")

    for field in EXTENDED_APP_IMPORT_LIST_FIELDS:
        if field not in card:
            errors.append(f"AppImportJSON 缺少必填字段：{field}")
        elif not isinstance(card[field], list):
            errors.append(f"AppImportJSON 字段 {field} 必须是数组。")
    for field in REQUIRED_NON_EMPTY_RICH_FIELDS:
        if isinstance(card.get(field), list) and not card[field]:
            errors.append(f"AppImportJSON 字段 {field} 不能为空，网站需要它展示人物、关系或原文链接。")

    for path, text in _iter_display_text(card, DISPLAY_CARD_FIELDS):
        for term in STUDENT_FORBIDDEN_TERMS:
            if term in text:
                errors.append(f"AppImportJSON 学生可见字段 {path} 包含禁用词：{term}")
    if evidence_pack is not None:
        later_associations = card.get("later_associations")
        if isinstance(later_associations, list) and later_associations:
            later_evidence = evidence_pack.get("later_association_evidence")
            if not later_evidence:
                errors.append("AppImportJSON 字段 later_associations 缺少规范化证据支持，必须留空。")
            else:
                chapter_number = _card_chapter_number(card)
                for index, association in enumerate(later_associations):
                    if not _later_association_supported(association, later_evidence, chapter_number=chapter_number):
                        errors.append(f"AppImportJSON 字段 later_associations[{index}] 缺少匹配证据引用支持。")
    return errors


def _iter_display_text(value: Any, display_fields: tuple[str, ...], path: str = ""):
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if path or key in display_fields:
                yield from _iter_display_text(item, display_fields, key_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_display_text(item, display_fields, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def _extract_balanced_json(text: str) -> str:
    start = text.find("{")
    if start == -1:
        raise ValueError("AppImportJSON JSON object was not found")
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError("AppImportJSON JSON object was incomplete")


def _card_chapter_number(card: Mapping[str, Any]) -> int | None:
    try:
        return int(card.get("chapter"))
    except (TypeError, ValueError):
        return None


def _later_association_supported(association: Any, evidence_items: Any, *, chapter_number: int | None) -> bool:
    if not isinstance(association, Mapping) or not isinstance(evidence_items, list):
        return False
    association_chapters = _int_set(association.get("source_chapters"))
    if not association_chapters:
        return False
    if chapter_number is not None and not any(chapter > chapter_number for chapter in association_chapters):
        return False
    association_text = _association_text(association)
    association_terms = _support_terms(association_text)
    association_refs = _association_reference_tokens(association)
    if not association_refs:
        return False
    for evidence in evidence_items:
        if not isinstance(evidence, Mapping):
            continue
        evidence_chapters = _int_set(evidence.get("source_chapters"))
        if not association_chapters.intersection(evidence_chapters):
            continue
        evidence_refs = _association_reference_tokens(evidence)
        if not association_refs.intersection(evidence_refs):
            continue
        evidence_text = _association_text(evidence)
        if not association_terms or any(term in evidence_text for term in association_terms):
            return True
    return False


def _int_set(value: Any) -> set[int]:
    if not isinstance(value, list):
        return set()
    output: set[int] = set()
    for item in value:
        try:
            output.add(int(item))
        except (TypeError, ValueError):
            continue
    return output


def _association_text(value: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("topic", "description", "evidence", "title", "relationship_keywords", "entity_type"):
        raw = value.get(key)
        if isinstance(raw, str):
            parts.append(raw)
    return "\n".join(parts)


def _association_reference_tokens(value: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in ("reference_id", "chunk_id", "evidence_id", "relation_id"):
        raw = value.get(key)
        if isinstance(raw, str) and raw.strip():
            refs.add(f"{key}:{raw.strip()}")
    for key in ("source_ids", "source_id"):
        raw = value.get(key)
        if isinstance(raw, str) and raw.strip():
            refs.add(f"source_id:{raw.strip()}")
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    refs.add(f"source_id:{item.strip()}")
    return refs


def _support_terms(text: str) -> set[str]:
    terms = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text))
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        max_size = min(4, len(run))
        for size in range(2, max_size + 1):
            for index in range(0, len(run) - size + 1):
                terms.add(run[index : index + size])
    return {
        term
        for term in terms
        if term not in LATER_ASSOCIATION_STOP_TERMS
        and not term.startswith("第")
        and not any(stop in term for stop in LATER_ASSOCIATION_STOP_TERMS)
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Hongloumeng chapter review cards.")
    parser.add_argument("--chapters", default="", help="Comma-separated chapter numbers. Default is the 10-chapter sample set.")
    parser.add_argument("--all", action="store_true", help="Generate all 120 chapters.")
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--manifest", type=Path, default=Path("book/chapters_manifest.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("generated"))
    parser.add_argument("--generated-at", default=date.today().isoformat())
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json-only", action="store_true", help="Only generate AppImportJSON for faster website/database trials.")
    parser.add_argument("--max-evidence-candidates", type=int, default=None, help="Limit normalized evidence candidates passed to the LLM.")
    args = parser.parse_args(argv)

    try:
        env = parse_env_file(args.env)
        chapters = parse_chapter_selection(args.chapters, all_chapters=args.all)
        lightrag_config = LightRAGConfig.from_env(env)
        if lightrag_config is None:
            raise ValueError("LIGHTRAG_BASE_URL is required")
        cards = generate_cards(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            chapters=chapters,
            lightrag_client=LightRAGClient(lightrag_config),
            llm_client=OpenAICompatibleLLMClient(LLMConfig.from_env(env)),
            generated_at=args.generated_at,
            overwrite=args.overwrite,
            json_only=args.json_only,
            max_evidence_candidates=args.max_evidence_candidates,
        )
        checked_path = args.output_dir / "chapter_review_cards.checked.json"
        valid_cards = load_import_cards(args.output_dir / "chapter_review_cards.raw.json", data_dir=Path("data/app"))
        write_import_cards(valid_cards, checked_path)
        print(f"generated {len(cards)} cards")
        print(f"raw: {args.output_dir / 'chapter_review_cards.raw.json'}")
        print(f"checked: {checked_path}")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI should return actionable errors
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
