"""Where pilot runs live.

`pilot run --work-dir` is free-form: `.coord/pilot` (AGENTS.md), `.work/pilot_P08` (P08) or `.coord` (the CLI
default). Readers that looked only at `.coord/pilot` missed real runs, so they look at every candidate.
"""

from __future__ import annotations

from pathlib import Path


def discover(project: Path) -> list[Path]:
    project = Path(project)
    candidates = [project / ".coord" / "pilot", project / ".coord"]
    work = project / ".work"
    if work.is_dir():
        candidates += sorted(child for child in work.iterdir() if child.is_dir())
    return [directory for directory in candidates if (directory / "runs").is_dir()]
