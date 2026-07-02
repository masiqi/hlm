from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hlm_kg.domain import EvidenceSourceType


FORBIDDEN_SAMPLE_FIELDS = {"standard_answer", "answer", "score"}
ALLOWED_EVIDENCE_TYPES: set[EvidenceSourceType] = {
    "original_text",
    "processed_material",
    "knowledge_card",
    "graph_relation",
}


class ValidationSampleError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationReport:
    total: int
    category_counts: dict[str, int]
    issues: list[str]


def load_validation_samples(path: Path) -> list[dict[str, Any]]:
    samples = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(samples, list):
        raise ValueError("validation samples must be a list")
    return samples


def sample_categories(samples: list[dict[str, Any]]) -> set[str]:
    return {str(sample["category"]) for sample in samples}


def validate_validation_samples(samples: list[dict[str, Any]]) -> ValidationReport:
    issues: list[str] = []
    category_counts: Counter[str] = Counter()
    for index, sample in enumerate(samples, start=1):
        sample_id = str(sample.get("id", f"sample-{index}"))
        if not isinstance(sample.get("category"), str) or not sample["category"]:
            issues.append(f"{sample_id}: category must be a non-empty string")
        else:
            category_counts[str(sample["category"])] += 1
        for field in sorted(FORBIDDEN_SAMPLE_FIELDS):
            if field in sample:
                issues.append(f"{sample_id}: forbidden answer-like field present: {field}")
        if not isinstance(sample.get("expected_objects"), list):
            issues.append(f"{sample_id}: expected_objects must be a list")
        evidence_types = sample.get("expected_evidence_types")
        if not isinstance(evidence_types, list):
            issues.append(f"{sample_id}: expected_evidence_types must be a list")
        else:
            invalid_types = [item for item in evidence_types if item not in ALLOWED_EVIDENCE_TYPES]
            if invalid_types:
                issues.append(f"{sample_id}: expected_evidence_types contains invalid values: {invalid_types}")
        if not isinstance(sample.get("should_refuse"), bool):
            issues.append(f"{sample_id}: should_refuse must be a boolean")
    if issues:
        raise ValidationSampleError("\n".join(issues))
    return ValidationReport(total=len(samples), category_counts=dict(sorted(category_counts.items())), issues=[])


def render_validation_report(report: ValidationReport) -> str:
    lines = ["校准样例验证报告", f"总样例数: {report.total}", "分类覆盖:"]
    lines.extend(f"- {category}: {count}" for category, count in report.category_counts.items())
    if report.issues:
        lines.append("发现问题:")
        lines.extend(f"- {issue}" for issue in report.issues)
    else:
        lines.append("未发现问题")
    return "\n".join(lines)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/app/validation_samples.json")
    samples = load_validation_samples(path)
    try:
        report = validate_validation_samples(samples)
    except ValidationSampleError as exc:
        print("校准样例验证报告")
        print("发现问题:")
        print(str(exc))
        raise SystemExit(1) from exc
    print(render_validation_report(report))


if __name__ == "__main__":
    main()
