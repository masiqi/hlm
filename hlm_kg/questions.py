from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


CAPABILITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("人物关系与身份别称", re.compile(r"人物|关系|别称|取名|名字|丫鬟|家族|贾府|宝玉|黛玉|宝钗|王熙凤")),
    ("章回情节与内容概括", re.compile(r"章|回|情节|概括|内容|故事|事件|经过|前后")),
    ("诗词判词与人物命运", re.compile(r"诗|词|判词|曲|金陵十二钗|册|命运|结局")),
    ("主题意象与象征", re.compile(r"主题|意象|象征|寓意|理解|评价|艺术|俗中不俗")),
    ("事件因果与伏笔照应", re.compile(r"原因|为什么|作用|伏笔|照应|铺垫|导致|影响")),
    ("制度礼俗与文化常识", re.compile(r"礼|俗|制度|文化|称谓|婚姻|科举|礼法|规矩")),
    ("比较鉴赏与论述", re.compile(r"比较|分析|赏析|谈谈|评价|看法|观点|结合")),
]

EXAMPLE_QUERIES = [
    "用 mix 模式概括第三回林黛玉进贾府的主要情节，并列出关键人物。",
    "用 hybrid 模式说明贾宝玉、林黛玉、薛宝钗之间的关系及其情节依据。",
    "查询金陵十二钗判词中某句对应的人物、出处章回和命运暗示。",
    "说明某个物件或意象在前后章回中的伏笔与照应关系。",
    "分析某一事件的起因、经过、结果，以及牵涉的人物关系。",
]


def load_questions(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"expected object at {path}:{line_number}")
            records.append(record)
    return records


def analyze_questions(records: list[dict[str, Any]]) -> dict[str, Any]:
    field_counter = Counter[str]()
    type_counter = Counter[str]()
    capability_counter = Counter[str]()
    source_counter = Counter[str]()

    for record in records:
        field_counter.update(record.keys())
        type_counter.update([str(record.get("type", "<missing>"))])
        source_counter.update([str(record.get("source", "<missing>"))])
        text = str(record.get("text", ""))
        matched = False
        for label, pattern in CAPABILITY_PATTERNS:
            if pattern.search(text):
                capability_counter.update([label])
                matched = True
        if not matched:
            capability_counter.update(["其他整本书阅读能力"])

    return {
        "record_count": len(records),
        "fields": dict(sorted(field_counter.items())),
        "type_counts": dict(type_counter.most_common()),
        "top_sources": dict(source_counter.most_common(12)),
        "capability_counts": dict(capability_counter.most_common()),
        "example_queries": EXAMPLE_QUERIES,
    }


def write_question_types_doc(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 《红楼梦》题目样例类型盘点",
        "",
        "本文件由 `python -m hlm_kg.questions` 根据 `questions/zujuan_questions_2026-06-30.jsonl` 生成。题目样例只用于校准关系图谱的实体、关系和检索能力，不用于批量解题。",
        "",
        "## JSONL 字段结构",
        "",
    ]
    for field, count in summary["fields"].items():
        lines.append(f"- `{field}`：{count} 条记录出现")

    lines.extend(["", "## 题型字段分布", ""])
    for type_name, count in summary["type_counts"].items():
        lines.append(f"- {type_name}：{count}")

    lines.extend(["", "## 常见来源", ""])
    for source, count in summary["top_sources"].items():
        lines.append(f"- {source}：{count}")

    lines.extend(["", "## 图谱需要支持的能力", ""])
    for capability, count in summary["capability_counts"].items():
        lines.append(f"- {capability}：{count}")

    lines.extend(
        [
            "",
            "## 示例查询模板",
            "",
            "这些模板面向未来查询，不代表对题库逐题作答：",
            "",
        ]
    )
    for query in summary["example_queries"]:
        lines.append(f"- {query}")

    lines.extend(
        [
            "",
            "## 对领域提示词的校准结论",
            "",
            "- 实体抽取需要覆盖人物、别称、家族、居所、地点、事件、章回、诗词/判词、物件、制度礼俗和主题意象。",
            "- 关系抽取需要突出亲属、主仆、婚恋、冲突、事件因果、伏笔照应、章回出处、象征/主题等可追溯关系。",
            "- 每个实体和关系描述应尽量包含来源章回或上下文，方便用 `mix` / `hybrid` 模式回答整本书阅读题。",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Hongloumeng question JSONL samples.")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path("questions/zujuan_questions_2026-06-30.jsonl"),
    )
    parser.add_argument("--output", type=Path, default=Path("docs/question_types.md"))
    args = parser.parse_args()

    questions_path = resolve_questions_path(args.questions)
    records = load_questions(questions_path)
    summary = analyze_questions(records)
    write_question_types_doc(summary, args.output)
    print(f"Parsed {summary['record_count']} question records; wrote {args.output}")
    return 0


def resolve_questions_path(path: Path) -> Path:
    if path.exists():
        return path
    text = str(path)
    if "questions" in text:
        typo_path = Path(text.replace("questions", "quesitons", 1))
        if typo_path.exists():
            return typo_path
    raise FileNotFoundError(path)


if __name__ == "__main__":
    raise SystemExit(main())
