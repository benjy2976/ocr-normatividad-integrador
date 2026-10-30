"""La documentación versionada no depende de los planes de trabajo.

Los planes viven fuera de git (ver "Planes de trabajo y bitácoras" en
AGENTS.md). Estas pruebas recorren el repo completo, no solo `adapter/`, y
fallan si un archivo versionado cita un plan concreto, si algún plan quedó
versionado o si `planes/` deja de estar ignorado.
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve().relative_to(REPOSITORY).as_posix()
WALK_SKIPPED_DIRS = {".git", ".venv", "__pycache__", "planes", "node_modules"}

PLAN_CITATIONS = (
    re.compile(r"\b[A-Z][A-Z0-9_]*_(?:PLAN|ROADMAP)\.md\b"),
    re.compile(
        r"\b(?:MARKDOWN_ARTIFACT_PLAN|REORGANIZACION_ROADMAP|"
        r"PREOCR_CORE_PROMOTION_(?:PLAN|MANIFEST)|PDF_OCR_PARALLEL_PIPELINE_ROADMAP|"
        r"MEJORA_OCR_ROADMAP|OCR_MCP_PLAN|TEST_OFICIAL_2_REPOS)\b"
    ),
    # Una carpeta de plan concreta; la política genérica `planes/<AAAA-MM>-<slug>/` sí se permite.
    re.compile(r"planes/\d{4}-\d{2}-"),
    re.compile(r"(?<![\w/])bitacoras/"),
)


def _git_tracked_files():
    try:
        output = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPOSITORY,
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [name for name in output.decode("utf-8").split("\0") if name]


def _versioned_files():
    tracked = _git_tracked_files()
    if tracked is not None:
        return tracked
    files = []
    for root, dirs, names in os.walk(REPOSITORY):
        dirs[:] = [name for name in dirs if name not in WALK_SKIPPED_DIRS]
        files.extend(
            (Path(root) / name).relative_to(REPOSITORY).as_posix() for name in names
        )
    return files


def _text(relative):
    path = REPOSITORY / relative
    if not path.is_file():
        return None
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


class DocumentationIndependenceTest(unittest.TestCase):
    def test_versioned_files_do_not_cite_work_plans(self):
        citations = []
        for relative in _versioned_files():
            if relative == SELF:
                continue
            text = _text(relative)
            if text is None:
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                for pattern in PLAN_CITATIONS:
                    match = pattern.search(line)
                    if match:
                        citations.append(f"{relative}:{number}: {match.group(0)}")
        self.assertEqual(
            citations,
            [],
            "La documentación versionada no puede citar planes de trabajo. Cosechar "
            "ese contenido (decisión, documento vigente o iniciativa) y citar eso.",
        )

    def test_no_work_plan_is_versioned(self):
        tracked = _git_tracked_files()
        if tracked is None:
            self.skipTest("git no está disponible")
        self.assertEqual([name for name in tracked if name.startswith("planes/")], [])

    def test_plans_folder_is_git_ignored(self):
        lines = (REPOSITORY / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/planes/", lines)


if __name__ == "__main__":
    unittest.main()
