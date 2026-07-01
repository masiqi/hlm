from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hlm_kg.chapters import split_chapters


PLACEHOLDER_MARKERS = (
    "replace-with",
    "replace-me",
    "your_",
    "your-",
    "sk-...",
    "changeme",
)


@dataclass(frozen=True)
class BuildConfig:
    env_path: Path = Path(".env")
    env_example_path: Path = Path(".env.example")
    source_path: Path = Path("book/红楼梦.txt")
    chapters_dir: Path = Path("book/chapters")
    manifest_path: Path = Path("book/chapters_manifest.json")
    input_dir: Path = Path("data/inputs")
    dry_run: bool = True
    start_server: bool = False
    poll_interval_seconds: float = 5.0
    poll_timeout_seconds: float = 3600.0


@dataclass(frozen=True)
class BuildPlan:
    dry_run: bool
    server_url: str
    webui_url: str
    input_dir: Path
    chapters_dir: Path
    chapter_count: int
    has_placeholder_credentials: bool
    steps: list[str]


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        env[key.strip()] = value
    return env


def ensure_env_file(env_path: Path, env_example_path: Path) -> None:
    if env_path.exists():
        return
    if not env_example_path.exists():
        raise FileNotFoundError(f"{env_example_path} does not exist")
    shutil.copyfile(env_example_path, env_path)
    print(f"Created {env_path} from {env_example_path}; fill in LLM and embedding settings before real indexing.")


def plan_build(config: BuildConfig) -> BuildPlan:
    env = parse_env_file(config.env_path)
    host = env.get("HOST", "127.0.0.1")
    if host == "0.0.0.0":
        host_for_client = "127.0.0.1"
    else:
        host_for_client = host
    port = env.get("PORT", "9621")
    server_url = f"http://{host_for_client}:{port}"
    chapter_count = len(list(config.chapters_dir.glob("*.txt"))) if config.chapters_dir.exists() else 0
    has_placeholder_credentials = _has_placeholder_credentials(env)
    steps = [
        "Check .env and required LightRAG settings",
        f"Split {config.source_path} into 120 chapter files and write {config.manifest_path}",
        f"Copy 120 chapter files into LightRAG input dir: {config.input_dir}",
        f"Check LightRAG server health at {server_url}/health",
        "POST /documents/scan to enqueue files for parsing and indexing",
        "Poll /documents/track_status/{track_id} and /documents/pipeline_status until processing finishes",
        f"Open WebUI at {server_url}/webui",
    ]
    if config.dry_run:
        steps.insert(0, "dry-run: print checks and planned actions without server calls or LLM/embedding usage")
    return BuildPlan(
        dry_run=config.dry_run,
        server_url=server_url,
        webui_url=f"{server_url}/webui",
        input_dir=config.input_dir,
        chapters_dir=config.chapters_dir,
        chapter_count=chapter_count,
        has_placeholder_credentials=has_placeholder_credentials,
        steps=steps,
    )


def run_build(config: BuildConfig) -> int:
    ensure_env_file(config.env_path, config.env_example_path)
    env = parse_env_file(config.env_path)
    _validate_required_env(env, dry_run=config.dry_run)
    input_dir = _resolve_env_path(env.get("INPUT_DIR"), config.input_dir)

    manifest = split_chapters(config.source_path, config.chapters_dir, config.manifest_path)
    chapters = [Path(chapter["file_path"]) for chapter in manifest["chapters"]]
    config = BuildConfig(
        env_path=config.env_path,
        env_example_path=config.env_example_path,
        source_path=config.source_path,
        chapters_dir=config.chapters_dir,
        manifest_path=config.manifest_path,
        input_dir=input_dir,
        dry_run=config.dry_run,
        start_server=config.start_server,
        poll_interval_seconds=config.poll_interval_seconds,
        poll_timeout_seconds=config.poll_timeout_seconds,
    )
    plan = plan_build(config)
    _print_plan(plan)

    if config.dry_run:
        _print_dry_run_details(config, env, manifest)
        return 0

    if plan.has_placeholder_credentials:
        raise RuntimeError("Refusing real build because .env still contains placeholder LLM or embedding credentials.")

    _sync_chapters_to_input_dir(chapters, config.input_dir)
    if config.start_server:
        _start_server()
    _wait_for_server(plan.server_url, timeout_seconds=60)
    track_id = _post_json(plan.server_url, "/documents/scan", env).get("track_id")
    if not track_id:
        raise RuntimeError("LightRAG /documents/scan did not return a track_id")
    _poll_processing(plan.server_url, str(track_id), env, config.poll_interval_seconds, config.poll_timeout_seconds)
    print(f"LightRAG indexing submitted. WebUI: {plan.webui_url}")
    return 0


def _validate_required_env(env: dict[str, str], *, dry_run: bool) -> None:
    required = [
        "HOST",
        "PORT",
        "WORKING_DIR",
        "INPUT_DIR",
        "WORKSPACE",
        "LLM_BINDING",
        "LLM_BINDING_HOST",
        "LLM_BINDING_API_KEY",
        "LLM_MODEL",
        "EMBEDDING_BINDING",
        "EMBEDDING_BINDING_HOST",
        "EMBEDDING_BINDING_API_KEY",
        "EMBEDDING_MODEL",
        "EMBEDDING_DIM",
        "SUMMARY_LANGUAGE",
        "ENTITY_EXTRACTION_USE_JSON",
        "ENTITY_TYPE_PROMPT_FILE",
        "PROMPT_DIR",
    ]
    missing = [key for key in required if not env.get(key)]
    if missing:
        mode = "Dry-run" if dry_run else "Real build"
        raise RuntimeError(f"{mode} requires .env keys: {', '.join(missing)}")


def _has_placeholder_credentials(env: dict[str, str]) -> bool:
    keys = [
        "LLM_BINDING_API_KEY",
        "EMBEDDING_BINDING_API_KEY",
        "EXTRACT_LLM_BINDING_API_KEY",
        "KEYWORD_LLM_BINDING_API_KEY",
        "QUERY_LLM_BINDING_API_KEY",
    ]
    for key in keys:
        value = env.get(key, "").lower()
        if value and any(marker in value for marker in PLACEHOLDER_MARKERS):
            return True
    return False


def _resolve_env_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _print_plan(plan: BuildPlan) -> None:
    print("Build plan")
    print(f"- dry_run: {plan.dry_run}")
    print(f"- server_url: {plan.server_url}")
    print(f"- webui_url: {plan.webui_url}")
    print(f"- chapters_dir: {plan.chapters_dir}")
    print(f"- detected chapter files before split: {plan.chapter_count}")
    print(f"- placeholder credentials detected: {plan.has_placeholder_credentials}")
    for step in plan.steps:
        print(f"- {step}")


def _print_dry_run_details(config: BuildConfig, env: dict[str, str], manifest: dict[str, Any]) -> None:
    chapter_files = list(Path(manifest["chapters_dir"]).glob("*.txt"))
    print("Dry-run details")
    print(f"- manifest chapter_count: {manifest['chapter_count']}")
    print(f"- chapter input files found: {len(chapter_files)}")
    print(f"- first chapter: {manifest['chapters'][0]['file_path']}")
    print(f"- last chapter: {manifest['chapters'][-1]['file_path']}")
    print(f"- target input dir: {config.input_dir}")
    print(f"- LightRAG workspace: {env.get('WORKSPACE')}")
    print(f"- LLM: {env.get('LLM_BINDING')} / {env.get('LLM_MODEL')} @ {env.get('LLM_BINDING_HOST')}")
    print(
        f"- Embedding: {env.get('EMBEDDING_BINDING')} / {env.get('EMBEDDING_MODEL')} "
        f"dim={env.get('EMBEDDING_DIM')} @ {env.get('EMBEDDING_BINDING_HOST')}"
    )
    print("- No files copied to LightRAG input dir and no server/API calls were made.")


def _sync_chapters_to_input_dir(chapters: list[Path], input_dir: Path) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    for stale in input_dir.glob("*.txt"):
        stale.unlink()
    for chapter in chapters:
        shutil.copy2(chapter, input_dir / chapter.name)
    print(f"Copied {len(chapters)} chapter files to {input_dir}")


def _start_server() -> None:
    subprocess.run(["docker", "compose", "up", "-d", "lightrag"], check=True)


def _wait_for_server(server_url: str, *, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            _get_json(server_url, "/health", {})
            return
        except Exception as exc:  # noqa: BLE001 - surface last network failure below
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"LightRAG server did not become healthy at {server_url}/health: {last_error}")


def _poll_processing(
    server_url: str,
    track_id: str,
    env: dict[str, str],
    poll_interval_seconds: float,
    poll_timeout_seconds: float,
) -> None:
    deadline = time.time() + poll_timeout_seconds
    while time.time() < deadline:
        track = _get_json(server_url, f"/documents/track_status/{urllib.parse.quote(track_id)}", env)
        pipeline = _get_json(server_url, "/documents/pipeline_status", env)
        print(json.dumps({"track": track, "pipeline": pipeline}, ensure_ascii=False)[:2000])
        if _looks_finished(track, pipeline):
            return
        time.sleep(poll_interval_seconds)
    raise TimeoutError(f"Timed out waiting for LightRAG processing track_id={track_id}")


def _looks_finished(track: Any, pipeline: Any) -> bool:
    blob = json.dumps({"track": track, "pipeline": pipeline}, ensure_ascii=False).lower()
    if any(status in blob for status in ("failed", "error", "cancel")):
        raise RuntimeError(f"LightRAG processing reported failure: {blob[:2000]}")
    busy = False
    if isinstance(pipeline, dict):
        busy = bool(pipeline.get("busy") or pipeline.get("pipeline_busy") or pipeline.get("scanning"))
    return not busy and any(status in blob for status in ("processed", "completed", "finished", "done"))


def _headers(env: dict[str, str]) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = env.get("LIGHTRAG_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _get_json(server_url: str, path: str, env: dict[str, str]) -> Any:
    request = urllib.request.Request(server_url.rstrip("/") + path, headers=_headers(env), method="GET")
    return _request_json(request)


def _post_json(server_url: str, path: str, env: dict[str, str]) -> Any:
    data = json.dumps({}).encode("utf-8")
    request = urllib.request.Request(
        server_url.rstrip("/") + path,
        data=data,
        headers=_headers(env),
        method="POST",
    )
    return _request_json(request)


def _request_json(request: urllib.request.Request) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {request.full_url}: {details}") from exc
    if not payload:
        return {}
    return json.loads(payload.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Hongloumeng LightRAG knowledge graph.")
    parser.add_argument("--real", action="store_true", help="Run real LightRAG scan/indexing. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="Validate local flow without LightRAG API calls.")
    parser.add_argument("--start-server", action="store_true", help="Run docker compose up -d lightrag before scanning.")
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--input-dir", type=Path, default=Path("data/inputs"))
    args = parser.parse_args(argv)

    dry_run = True
    if args.real:
        dry_run = False
    if args.dry_run:
        dry_run = True

    config = BuildConfig(
        env_path=args.env,
        input_dir=args.input_dir,
        dry_run=dry_run,
        start_server=args.start_server,
    )
    try:
        return run_build(config)
    except Exception as exc:  # noqa: BLE001 - CLI should print actionable error
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
