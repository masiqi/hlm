from pathlib import Path


def test_python_runtime_dependencies_are_declared():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "pytest" in requirements
    assert "psycopg[binary]" in requirements
