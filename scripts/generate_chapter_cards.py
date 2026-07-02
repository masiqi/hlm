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
DISPLAY_CARD_FIELDS = (
    "plain_summary",
    "plot_chain",
    "key_events",
    "current_chapter_foreshadowing_signals",
    "retrieval_tags",
    "understanding_focus",
    *EXTENDED_APP_IMPORT_LIST_FIELDS,
)


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
        prompt = build_prompt(
            chapter_number=chapter_number,
            chapter_title=str(item["title"]),
            source_file=str(item["file_path"]),
            chapter_text=chapter_text,
            lightrag_evidence=evidence,
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
        validation_errors = validate_generated_card_output(markdown, card)
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
    query = (
        f"第{chapter_number}回 {chapter_title} 的主要人物、事件、地点、物件、意象、"
        "伏笔、后文关联、人物关系和命运线索"
    )
    return lightrag_client.query_data(query, mode="hybrid", only_need_context=True)


def build_prompt(
    *,
    chapter_number: int,
    chapter_title: str,
    source_file: str,
    chapter_text: str,
    lightrag_evidence: Mapping[str, Any],
    generated_at: str,
) -> str:
    evidence_text = json.dumps(lightrag_evidence, ensure_ascii=False, indent=2)[:30000]
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
9. 必须直接从标题行“# 第{chapter_number}回 {chapter_title} 章节复习卡”开始输出，不要输出寒暄、解释、免责声明或“好的同学”之类开场白。

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

第一部分：完整 Markdown 章节复习卡

必须从下面标题行开始，不要在标题前添加任何文字：

# 第{chapter_number}回 {chapter_title} 章节复习卡

必须包含以下栏目：

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

第二部分：AppImportJSON

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
  "later_associations": [
    {{
      "topic": "后文关联对象",
      "description": "后文关联说明",
      "source_chapters": [74],
      "evidence": "必须来自系统提供的全书关系线索或明确后续章回证据",
      "relation_id": null
    }}
  ],
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
- plain_summary、plot_chain、key_events、current_chapter_foreshadowing_signals、understanding_focus、characters、relationships、places、objects、literary_texts、modern_explanations、later_associations、annotations 中不得出现禁用词。
"""


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
  "later_associations": [
    {{
      "topic": "后文关联对象",
      "description": "后文关联说明",
      "source_chapters": [],
      "evidence": "必须来自系统提供的全书关系线索或明确后续章回证据",
      "relation_id": null
    }}
  ],
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


def validate_generated_card_output(markdown: str, card: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    stripped = markdown.lstrip()
    first_line = stripped.splitlines()[0].strip() if stripped else ""
    if not first_line.startswith("# 第"):
        errors.append("完整 Markdown 不得以寒暄开头，必须直接从章节标题开始。")

    for term in STUDENT_FORBIDDEN_TERMS:
        if term in markdown:
            errors.append(f"完整 Markdown 包含学生端禁用词：{term}")

    for field in REQUIRED_APP_IMPORT_FIELDS:
        if field not in card:
            errors.append(f"AppImportJSON 缺少必填字段：{field}")

    for field in EXTENDED_APP_IMPORT_LIST_FIELDS:
        if field in card and not isinstance(card[field], list):
            errors.append(f"AppImportJSON 字段 {field} 必须是数组。")

    for path, text in _iter_display_text(card, DISPLAY_CARD_FIELDS):
        for term in STUDENT_FORBIDDEN_TERMS:
            if term in text:
                errors.append(f"AppImportJSON 学生可见字段 {path} 包含禁用词：{term}")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Hongloumeng chapter review cards.")
    parser.add_argument("--chapters", default="", help="Comma-separated chapter numbers. Default is the 10-chapter sample set.")
    parser.add_argument("--all", action="store_true", help="Generate all 120 chapters.")
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--manifest", type=Path, default=Path("book/chapters_manifest.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("generated"))
    parser.add_argument("--generated-at", default=date.today().isoformat())
    parser.add_argument("--overwrite", action="store_true")
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
