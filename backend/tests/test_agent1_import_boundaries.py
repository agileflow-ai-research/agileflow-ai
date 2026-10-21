"""Fresh-process regression coverage for Agent 1 package import boundaries."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
IMPORTS = (
    "app.modules.agents.requirements.discovery.classification.transformer",
    "app.modules.agents.requirements.discovery.classification.service",
    "app.modules.agents.requirements.discovery.input",
    "app.modules.agents.requirements.workflow.orchestration.n3_runner",
    "app.main",
)

LEGACY_EXPORTS = (
    "RequirementN2OrchestrationService",
    "RequirementN3OrchestrationService",
)


@pytest.mark.parametrize("module_name", IMPORTS)
def test_agent1_module_imports_in_a_fresh_process(module_name):
    environment = os.environ.copy()
    environment["MONGODB_URI"] = "mongodb://localhost:27017"
    command = (
        "import importlib, sys; "
        f"importlib.import_module({module_name!r}); "
        "assert 'transformers' not in sys.modules"
    )

    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("export_name", LEGACY_EXPORTS)
def test_legacy_orchestration_service_export_remains_available(export_name):
    environment = os.environ.copy()
    environment["MONGODB_URI"] = "mongodb://localhost:27017"
    command = (
        "from app.modules.agents.requirements import workflow; "
        "from app.modules.agents.requirements.workflow import orchestration; "
        f"assert orchestration.{export_name}.__name__ == {export_name!r}"
    )

    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
