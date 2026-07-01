from pathlib import Path

from hlm_kg.lightrag_app import BuildConfig, plan_build


def test_dry_run_plan_detects_placeholder_credentials(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "HOST=127.0.0.1",
                "PORT=9621",
                "WORKING_DIR=./data/rag_storage",
                "INPUT_DIR=./data/inputs",
                "WORKSPACE=hongloumeng",
                "LLM_BINDING=openai",
                "LLM_MODEL=replace-me",
                "LLM_BINDING_HOST=https://api.openai.com/v1",
                "LLM_BINDING_API_KEY=replace-with-your-llm-api-key",
                "EMBEDDING_BINDING=openai",
                "EMBEDDING_MODEL=replace-me",
                "EMBEDDING_DIM=1024",
                "EMBEDDING_BINDING_HOST=https://api.openai.com/v1",
                "EMBEDDING_BINDING_API_KEY=replace-with-your-embedding-api-key",
            ]
        ),
        encoding="utf-8",
    )

    plan = plan_build(
        BuildConfig(
            env_path=env_path,
            chapters_dir=Path("book/chapters"),
            input_dir=tmp_path / "inputs",
            dry_run=True,
        )
    )

    assert plan.dry_run is True
    assert plan.server_url == "http://127.0.0.1:9621"
    assert plan.has_placeholder_credentials is True
    assert any("dry-run" in step.lower() for step in plan.steps)
