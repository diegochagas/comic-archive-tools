"""Shared helpers: project discovery and config loading."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"


def list_projects() -> list[str]:
    return sorted(
        p.name for p in PROJECTS.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "project.json").exists()
    )


def resolve_project(arg: str | None) -> tuple[str, dict, Path]:
    """Return (name, config, project_dir). With no arg, use the only project."""
    names = list_projects()
    if not names:
        sys.exit("No projects found under projects/ (need a project.json)")
    if arg is None:
        if len(names) == 1:
            arg = names[0]
        else:
            sys.exit(f"Multiple projects exist — specify one of: {', '.join(names)}")
    if arg not in names:
        sys.exit(f"Unknown project '{arg}'. Available: {', '.join(names)}")
    pdir = PROJECTS / arg
    config = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
    return arg, config, pdir
