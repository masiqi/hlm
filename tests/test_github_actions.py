from pathlib import Path


def test_github_actions_ci_workflow_runs_project_quality_checks():
    workflow = Path(".github/workflows/ci.yml")

    assert workflow.exists()
    content = workflow.read_text(encoding="utf-8")
    assert "pull_request:" in content
    assert "push:" in content
    assert "branches: [main]" in content
    assert "python-version: '3.13'" in content
    assert "python -m pytest -q" in content
    assert "python -m hlm_kg.validation_samples" in content
