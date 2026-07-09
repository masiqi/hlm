from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hlm_kg.domain import EvidenceSourceType


FORBIDDEN_ASK_QUALITY_FIELDS = {"standard_answer", "answer", "score"}
ALLOWED_ASK_STATUSES = {"answered", "partial", "refused"}
ALLOWED_EVIDENCE_TYPES: set[EvidenceSourceType] = {
    "original_text",
    "processed_material",
    "knowledge_card",
    "graph_relation",
}
REQUIRED_LIST_FIELDS = {
    "expected_subjects",
    "expected_chapters",
    "preferred_evidence_types",
    "required_evidence_terms",
    "must_not_focus_on",
}


class AskQualityDatasetError(ValueError):
    pass


@dataclass(frozen=True)
class AskQualityReport:
    total: int
    category_counts: dict[str, int]
    status_counts: dict[str, int]
    issues: list[str]


def load_ask_quality_dataset(path: Path) -> list[dict[str, Any]]:
    samples = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(samples, list):
        raise ValueError("Ask quality dataset must be a list")
    return samples


def ask_quality_categories(samples: list[dict[str, Any]]) -> set[str]:
    return {str(sample["category"]) for sample in samples}


def validate_ask_quality_dataset(samples: list[dict[str, Any]]) -> AskQualityReport:
    issues: list[str] = []
    category_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    seen_ids: set[str] = set()

    for index, sample in enumerate(samples, start=1):
        sample_id = str(sample.get("id", f"ask-sample-{index}"))
        if sample_id in seen_ids:
            issues.append(f"{sample_id}: duplicate id")
        seen_ids.add(sample_id)

        if not isinstance(sample.get("id"), str) or not sample["id"]:
            issues.append(f"{sample_id}: id must be a non-empty string")
        if not isinstance(sample.get("category"), str) or not sample["category"]:
            issues.append(f"{sample_id}: category must be a non-empty string")
        else:
            category_counts[str(sample["category"])] += 1
        if not isinstance(sample.get("question"), str) or not sample["question"].strip():
            issues.append(f"{sample_id}: question must be a non-empty string")
        if not isinstance(sample.get("quality_notes"), str) or not sample["quality_notes"].strip():
            issues.append(f"{sample_id}: quality_notes must be a non-empty string")

        for field in sorted(FORBIDDEN_ASK_QUALITY_FIELDS):
            if field in sample:
                issues.append(f"{sample_id}: forbidden answer-like field present: {field}")

        expected_status = sample.get("expected_status")
        if expected_status not in ALLOWED_ASK_STATUSES:
            issues.append(f"{sample_id}: expected_status must be one of {sorted(ALLOWED_ASK_STATUSES)}")
        else:
            status_counts[str(expected_status)] += 1

        for field in sorted(REQUIRED_LIST_FIELDS):
            if not isinstance(sample.get(field), list):
                issues.append(f"{sample_id}: {field} must be a list")

        evidence_types = sample.get("preferred_evidence_types")
        if isinstance(evidence_types, list):
            invalid_types = [item for item in evidence_types if item not in ALLOWED_EVIDENCE_TYPES]
            if invalid_types:
                issues.append(f"{sample_id}: preferred_evidence_types contains invalid values: {invalid_types}")

        chapters = sample.get("expected_chapters")
        if isinstance(chapters, list):
            invalid_chapters = [chapter for chapter in chapters if not isinstance(chapter, int) or chapter < 1 or chapter > 120]
            if invalid_chapters:
                issues.append(f"{sample_id}: expected_chapters contains invalid values: {invalid_chapters}")

    if issues:
        raise AskQualityDatasetError("\n".join(issues))

    return AskQualityReport(
        total=len(samples),
        category_counts=dict(sorted(category_counts.items())),
        status_counts=dict(sorted(status_counts.items())),
        issues=[],
    )


def render_ask_quality_report(report: AskQualityReport) -> str:
    lines = ["问一问质量数据集验证报告", f"总样例数: {report.total}", "分类覆盖:"]
    lines.extend(f"- {category}: {count}" for category, count in report.category_counts.items())
    lines.append("期望状态:")
    lines.extend(f"- {status}: {count}" for status, count in report.status_counts.items())
    if report.issues:
        lines.append("发现问题:")
        lines.extend(f"- {issue}" for issue in report.issues)
    else:
        lines.append("未发现问题")
    return "\n".join(lines)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/eval/ask_quality_dataset.json")
    samples = load_ask_quality_dataset(path)
    try:
        report = validate_ask_quality_dataset(samples)
    except AskQualityDatasetError as exc:
        print("问一问质量数据集验证报告")
        print("发现问题:")
        print(str(exc))
        raise SystemExit(1) from exc
    print(render_ask_quality_report(report))


if __name__ == "__main__":
    main()
