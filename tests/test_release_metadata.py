from __future__ import annotations

import os
import re
import tomllib

from pathlib import Path

from simulator_api.version import VERSION


ROOT = Path(__file__).resolve().parents[1]


def _project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as source:
        return tomllib.load(source)["project"]["version"]


def test_release_version_is_consistent_across_user_facing_files() -> None:
    version = _project_version()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_windows_release.ps1").read_text(
        encoding="utf-8"
    )
    packaged_readme = (ROOT / "packaging" / "README.txt").read_text(encoding="utf-8")

    assert VERSION == version
    assert f'[string]$Version = "{version}"' in build_script
    assert f"v{version}" in packaged_readme

    linked_versions = set(
        re.findall(r"releases/(?:download|tag)/v(\d+\.\d+\.\d+)", readme)
    )
    assert linked_versions == {version}


def test_release_tag_matches_project_version_when_ci_runs_on_a_tag() -> None:
    if os.getenv("GITHUB_REF_TYPE") != "tag":
        return

    assert os.environ["GITHUB_REF_NAME"] == f"v{_project_version()}"


def test_readme_relative_links_resolve_inside_repository() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme)
    missing: list[str] = []

    for raw_target in targets:
        target = raw_target.strip().split("#", 1)[0]
        if not target or re.match(r"^(?:https?://|mailto:)", target):
            continue
        if not (ROOT / target).exists():
            missing.append(raw_target)

    assert not missing, f"README links point to missing repository files: {missing}"
