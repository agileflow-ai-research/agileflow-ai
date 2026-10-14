import subprocess
from pathlib import Path

import pytest

from app.modules.testing.executor import (
    DEFAULT_SANDBOX_LIMITS,
    CommandPolicyError,
    SandboxedValidationExecutor,
    ToolExecutionError,
    ValidationExecutionRequest,
    ValidationProfile,
    materialize_project,
    resolve_validation_profile,
    resolve_workspace_path,
)


class FakeDockerRuntime:
    def __init__(self, *, exit_code=0, exit_codes=None, unavailable=False, timeout=False, cleanup_failure=False):
        self.exit_code = exit_code
        self.exit_codes = list(exit_codes or [])
        self.unavailable = unavailable
        self.timeout = timeout
        self.cleanup_failure = cleanup_failure
        self.calls = []

    def run(self, arguments, *, timeout_seconds):
        self.calls.append((list(arguments), timeout_seconds))
        operation = arguments[0]
        if operation == "version":
            return subprocess.CompletedProcess(arguments, 1 if self.unavailable else 0, "" if self.unavailable else "29.0", "")
        if operation == "create":
            return subprocess.CompletedProcess(arguments, 0, "container-id", "")
        if operation == "start":
            return subprocess.CompletedProcess(arguments, 0, "container-id", "")
        if operation == "wait":
            if self.timeout:
                raise subprocess.TimeoutExpired(arguments, timeout_seconds)
            exit_code = self.exit_codes.pop(0) if self.exit_codes else self.exit_code
            return subprocess.CompletedProcess(arguments, 0, str(exit_code), "")
        if operation == "logs":
            return subprocess.CompletedProcess(arguments, 0, "sandbox output", "")
        if operation == "rm":
            return subprocess.CompletedProcess(arguments, 1 if self.cleanup_failure else 0, "", "")
        raise AssertionError(f"Unexpected Docker operation: {operation}")


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.py",
        "/absolute/path.py",
        r"C:\outside.py",
        "C:/outside.py",
        "C:outside.py",
        r"folder\..\outside.py",
    ],
)
def test_unsafe_project_paths_are_rejected(tmp_path, unsafe_path):
    with pytest.raises(ToolExecutionError, match="Unsafe project file path"):
        resolve_workspace_path(tmp_path, unsafe_path)


def test_nested_safe_path_is_materialized_beneath_workspace(tmp_path):
    paths = materialize_project(tmp_path, {"src/package/module.py": "VALUE = 1"})
    assert paths == [tmp_path / "src" / "package" / "module.py"]
    assert paths[0].resolve().is_relative_to(tmp_path.resolve())
    assert paths[0].read_text(encoding="utf-8") == "VALUE = 1"


def test_symlink_escape_is_rejected_when_supported(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating a symlink is not permitted on this test platform")
    with pytest.raises(ToolExecutionError, match="Unsafe project file path"):
        resolve_workspace_path(tmp_path, "linked/file.py")


@pytest.mark.parametrize(
    ("build_command", "run_command"),
    [
        (None, "python -c print('unsafe')"),
        (None, "npx arbitrary-package"),
        (None, "cmd /c whoami"),
        (None, "python -m pytest --capture=no"),
        ("curl https://example.test", "python -m pytest"),
    ],
)
def test_arbitrary_commands_and_arguments_are_rejected(build_command, run_command):
    with pytest.raises(CommandPolicyError):
        resolve_validation_profile(None, build_command, run_command)


def test_profile_cannot_be_used_to_override_executable_or_arguments():
    with pytest.raises(CommandPolicyError, match="run_command cannot override"):
        resolve_validation_profile(
            ValidationProfile.PYTHON_PYTEST,
            None,
            "python -m pytest -k selected",
        )


def test_exact_legacy_command_maps_to_server_controlled_profile():
    assert resolve_validation_profile(None, None, "python -m pytest") is ValidationProfile.PYTHON_PYTEST
    assert resolve_validation_profile(None, None, "npm test") is ValidationProfile.NODE_NPM_TEST


def test_sandbox_configuration_has_network_and_resource_controls():
    runtime = FakeDockerRuntime()
    executor = SandboxedValidationExecutor(runtime=runtime)
    result = executor.execute(ValidationExecutionRequest(
        source={"test_example.py": "def test_ok(): assert True"},
        profile=ValidationProfile.PYTHON_PYTEST,
    ))
    assert result.tests.execution_status == "PASSED"
    create = next(arguments for arguments, _ in runtime.calls if arguments[0] == "create")
    expected_pairs = {
        "--network": "none",
        "--memory": DEFAULT_SANDBOX_LIMITS.memory,
        "--cpus": str(DEFAULT_SANDBOX_LIMITS.cpu_count),
        "--pids-limit": str(DEFAULT_SANDBOX_LIMITS.pids),
        "--cap-drop": "ALL",
        "--pull": "never",
    }
    for option, expected in expected_pairs.items():
        assert create[create.index(option) + 1] == expected
    assert "--read-only" in create
    assert "no-new-privileges" in create
    assert create[create.index("--user") + 1] != "0:0"
    assert all("agileflow-ai" not in argument for argument in create if argument.startswith("type=bind"))
    assert sum(arguments[0] == "rm" for arguments, _ in runtime.calls) == 2


def test_cleanup_runs_after_sandboxed_test_failure():
    runtime = FakeDockerRuntime(exit_codes=[0, 1])
    result = SandboxedValidationExecutor(runtime=runtime).execute(
        ValidationExecutionRequest("def broken(): return False", ValidationProfile.PYTHON_PYTEST)
    )
    assert result.tests.execution_status == "FAILED"
    assert sum(arguments[0] == "rm" for arguments, _ in runtime.calls) == 2


def test_timeout_is_reported_as_failure_and_container_is_removed():
    runtime = FakeDockerRuntime(timeout=True)
    with pytest.raises(ToolExecutionError, match="execution time limit"):
        SandboxedValidationExecutor(runtime=runtime).execute(
            ValidationExecutionRequest("while True: pass", ValidationProfile.PYTHON_PYTEST)
        )
    assert any(arguments[:3] == ["rm", "--force", "--volumes"] for arguments, _ in runtime.calls)


def test_cleanup_failure_fails_closed():
    runtime = FakeDockerRuntime(cleanup_failure=True)
    with pytest.raises(ToolExecutionError, match="cleanup could not be confirmed"):
        SandboxedValidationExecutor(runtime=runtime).execute(
            ValidationExecutionRequest("print('ok')", ValidationProfile.PYTHON_PYTEST)
        )


def test_unavailable_sandbox_fails_without_host_execution():
    runtime = FakeDockerRuntime(unavailable=True)
    with pytest.raises(ToolExecutionError, match="sandbox is unavailable"):
        SandboxedValidationExecutor(runtime=runtime).execute(
            ValidationExecutionRequest("print('ok')", ValidationProfile.PYTHON_PYTEST)
        )
    assert [arguments[0] for arguments, _ in runtime.calls] == ["version"]


def test_static_analysis_only_stages_safely_without_starting_docker():
    runtime = FakeDockerRuntime(unavailable=True)
    result = SandboxedValidationExecutor(runtime=runtime).execute(
        ValidationExecutionRequest({"src/app.py": "print('ok')"}, None)
    )
    assert result.tests.execution_status == "SKIPPED"
    assert runtime.calls == []
