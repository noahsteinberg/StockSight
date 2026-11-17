"""Vercel reads pyproject first; keep its runtime dependencies complete."""

import tomllib
from pathlib import Path


def test_hosted_and_local_runtime_dependencies_match():
    backend = Path(__file__).parents[1]
    project = tomllib.loads((backend / "pyproject.toml").read_text())["project"]
    requirements = {
        line.strip()
        for line in (backend / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert requirements
    assert set(project["dependencies"]) == requirements
