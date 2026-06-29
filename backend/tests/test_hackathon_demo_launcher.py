from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_hackathon_demo.py"

spec = importlib.util.spec_from_file_location("run_hackathon_demo", SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
launcher = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = launcher
spec.loader.exec_module(launcher)


def _copy_demo_bundle(root: Path) -> None:
    for relative in [
        "docker/docker-compose.hackathon-demo.yaml",
        "docker/hackathon-demo.env.example",
        "docs/split-ui-deployment.md",
        "config.example.yaml",
    ]:
        source = REPO_ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (root / "frontend").mkdir(exist_ok=True)


def test_hackathon_demo_launcher_prepares_env_and_urls(tmp_path: Path) -> None:
    _copy_demo_bundle(tmp_path)

    result = launcher.run_hackathon_demo(
        tmp_path,
        check_compose=False,
        start=False,
    )

    env_text = (tmp_path / "docker" / "hackathon-demo.env").read_text(encoding="utf-8")
    assert "BETTER_AUTH_SECRET=replace-with-a-long-random-demo-secret" not in env_text
    assert "config.yaml" in {item.relative_path for item in result.bootstrap_results}
    assert result.started is False
    assert result.ui_url == "http://localhost:3000"
    assert result.gateway_docs_url == "http://localhost:8001/api/docs"
    assert "--env-file" in result.command
    assert str(tmp_path / "docker" / "hackathon-demo.env") in result.command


def test_hackathon_demo_launcher_preserves_existing_env(tmp_path: Path) -> None:
    _copy_demo_bundle(tmp_path)
    env_path = tmp_path / "docker" / "hackathon-demo.env"
    env_path.write_text(
        "HACKATHON_FRONTEND_PORT=3100\nHACKATHON_GATEWAY_PORT=8101\nBETTER_AUTH_SECRET=kept\n",
        encoding="utf-8",
    )

    result = launcher.run_hackathon_demo(
        tmp_path,
        check_compose=False,
        start=False,
    )

    assert env_path.read_text(encoding="utf-8").endswith("BETTER_AUTH_SECRET=kept\n")
    assert result.ui_url == "http://localhost:3100"
    assert result.gateway_docs_url == "http://localhost:8101/api/docs"
