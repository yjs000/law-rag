import json
import tomllib
from pathlib import Path

API_ROOT = Path(__file__).parents[1]


def test_vercel_uses_fastapi_entrypoint_without_path_rewrite() -> None:
    vercel_config = json.loads((API_ROOT / "vercel.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((API_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "rewrites" not in vercel_config
    assert pyproject["tool"]["vercel"]["entrypoint"] == "app.main:app"
    assert "app/main.py" in vercel_config["functions"]


def test_vercel_api_runs_next_to_the_seoul_database() -> None:
    vercel_config = json.loads((API_ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert vercel_config["regions"] == ["icn1"]
