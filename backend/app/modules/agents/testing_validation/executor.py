"""
LEGACY standalone validation executor: runs project validation commands in a Docker sandbox.

Not part of the N1-N4 Test Generation pipeline. The N4.3 feasibility stage never
runs tests and never calls this module. This module does two things:
  - resolves the requested project files inside a workspace, rejecting path escapes
    and reparse points, and
  - runs the fixed validation profile in a Docker runtime with CPU, memory, process-count,
    temporary-storage, and timeout limits (SandboxLimits). Command logs are redacted
    before they are returned.
"""

import ntpath
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Protocol


MAX_LOG_CHARS = 20_000
MAX_PROJECT_FILES = 200
MAX_FILE_BYTES = 1_000_000
MAX_PROJECT_BYTES = 10_000_000
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class SandboxLimits:
    cpu_count: float = 1.0
    memory: str = "512m"
    pids: int = 128
    execution_timeout_seconds: int = 30
    docker_operation_timeout_seconds: int = 10
    temporary_storage: str = "64m"


DEFAULT_SANDBOX_LIMITS = SandboxLimits()


class ValidationProfile(StrEnum):
    PYTHON_PYTEST = "PYTHON_PYTEST"
    NODE_NPM_TEST = "NODE_NPM_TEST"


@dataclass(frozen=True)
class ValidationProfileConfig:
    image: str
    build_command: tuple[str, ...]
    test_command: tuple[str, ...]
    legacy_build_command: str | None
    legacy_run_command: str


VALIDATION_PROFILES = {
    ValidationProfile.PYTHON_PYTEST: ValidationProfileConfig(
        image="agileflow/agent4-python-pytest:1.0",
        build_command=("python", "-m", "compileall", "-q", "."),
        test_command=(
            "python", "-m", "pytest", "-q", "--disable-warnings", "--cov=."
        ),
        legacy_build_command="python -m compileall -q .",
        legacy_run_command="python -m pytest",
    ),
    ValidationProfile.NODE_NPM_TEST: ValidationProfileConfig(
        image="agileflow/agent4-node-test:1.0",
        build_command=("npm", "run", "build", "--if-present"),
        test_command=("npm", "test"),
        legacy_build_command="npm run build --if-present",
        legacy_run_command="npm test",
    ),
}


class CommandPolicyError(ValueError):
    """A request attempted to depart from a server-controlled command profile."""


class ToolExecutionError(RuntimeError):
    """Secure validation could not be prepared, executed, or cleaned up."""


def resolve_validation_profile(
    profile: ValidationProfile | str | None,
    build_command: str | None,
    run_command: str | None,
) -> ValidationProfile | None:
    selected = ValidationProfile(profile) if profile else None
    supplied_build = build_command.strip() if build_command else None
    supplied_run = run_command.strip() if run_command else None

    if selected is None and supplied_build is None and supplied_run is None:
        return None

    if selected is None:
        matches = [
            candidate
            for candidate, config in VALIDATION_PROFILES.items()
            if supplied_run == config.legacy_run_command
            and supplied_build in {None, config.legacy_build_command}
        ]
        if len(matches) != 1:
            raise CommandPolicyError(
                "Validation commands must use a supported server-controlled profile"
            )
        selected = matches[0]

    config = VALIDATION_PROFILES[selected]
    if supplied_build not in {None, config.legacy_build_command}:
        raise CommandPolicyError(
            "build_command cannot override the selected validation profile"
        )
    if supplied_run not in {None, config.legacy_run_command}:
        raise CommandPolicyError(
            "run_command cannot override the selected validation profile"
        )
    return selected


@dataclass(frozen=True)
class ValidationExecutionRequest:
    source: str | dict[str, str]
    profile: ValidationProfile | None


@dataclass(frozen=True)
class ValidationCommandResult:
    command: list[str]
    tool: str
    exit_code: int | None
    execution_status: str
    stdout: str
    stderr: str
    duration_seconds: float | None = None
    timed_out: bool = False
    reason: str | None = None
    evidence_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def outcome(self) -> str:
        return self.execution_status

    def as_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "tool": self.tool,
            "exit_code": self.exit_code,
            "outcome": self.execution_status,
            "execution_status": self.execution_status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "timed_out": self.timed_out,
            "reason": self.reason,
            "evidence_type": (
                "ACTUAL_SANDBOX_EXECUTION"
                if self.exit_code is not None
                else "NOT_EXECUTED"
            ),
            "evidence_metadata": self.evidence_metadata,
        }


@dataclass(frozen=True)
class ValidationExecutionResult:
    build: ValidationCommandResult
    tests: ValidationCommandResult
    sandbox: dict[str, Any]


class ValidationExecutor(Protocol):
    def execute(self, request: ValidationExecutionRequest) -> ValidationExecutionResult: ...


def _redact(value: str | bytes | None) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    pattern = re.compile(
        r"(?i)(api[_-]?key|token|password|secret)(\s*[:=]\s*)([^\s,;]+)"
    )
    return pattern.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text
    )[:MAX_LOG_CHARS]


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = path.stat(follow_symlinks=False).st_file_attributes
    except (AttributeError, FileNotFoundError, OSError):
        return False
    return bool(attributes & 0x400)


def resolve_workspace_path(workspace_root: Path, raw_path: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
        raise ToolExecutionError("Project file path must be a non-empty text path")

    candidate = raw_path.strip()
    drive, _ = ntpath.splitdrive(candidate)
    if drive or ntpath.isabs(candidate) or candidate.startswith(("/", "\\")):
        raise ToolExecutionError("Unsafe project file path")

    normalized = candidate.replace("\\", "/")
    relative = PurePosixPath(normalized)
    invalid_windows_part = any(
        ":" in part
        or part.endswith((".", " "))
        or part.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES
        for part in relative.parts
    )
    if (
        relative.is_absolute()
        or not relative.name
        or any(part in {"", ".", ".."} for part in relative.parts)
        or invalid_windows_part
    ):
        raise ToolExecutionError("Unsafe project file path")

    root = workspace_root.resolve(strict=True)
    target = root.joinpath(*relative.parts).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ToolExecutionError("Unsafe project file path") from exc

    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.exists() and _is_reparse_point(current):
            raise ToolExecutionError("Unsafe project file path")
    if target.exists() and _is_reparse_point(target):
        raise ToolExecutionError("Unsafe project file path")
    return target


def materialize_project(workspace_root: Path, source: str | dict[str, str]) -> list[Path]:
    files = {"source.py": source} if isinstance(source, str) else source
    if not files or len(files) > MAX_PROJECT_FILES:
        raise ToolExecutionError("Project file count exceeds the secure validation limit")

    encoded: list[tuple[str, bytes]] = []
    total_bytes = 0
    for raw_path, content in files.items():
        if not isinstance(content, str):
            raise ToolExecutionError("Project files must contain text content")
        payload = content.encode("utf-8")
        if len(payload) > MAX_FILE_BYTES:
            raise ToolExecutionError("A project file exceeds the secure validation size limit")
        total_bytes += len(payload)
        if total_bytes > MAX_PROJECT_BYTES:
            raise ToolExecutionError("Project content exceeds the secure validation size limit")
        encoded.append((raw_path, payload))

    written: list[Path] = []
    for raw_path, payload in encoded:
        target = resolve_workspace_path(workspace_root, raw_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if _is_reparse_point(target.parent):
            raise ToolExecutionError("Unsafe project file path")
        resolved_after_create = target.resolve(strict=False)
        try:
            resolved_after_create.relative_to(workspace_root.resolve(strict=True))
        except ValueError as exc:
            raise ToolExecutionError("Unsafe project file path") from exc

        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(target, flags, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
        except (FileExistsError, OSError) as exc:
            raise ToolExecutionError("Project file could not be staged safely") from exc
        written.append(target)
    return written


class DockerRuntime(Protocol):
    def run(
        self,
        arguments: list[str],
        *,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]: ...


class SubprocessDockerRuntime:
    def run(
        self,
        arguments: list[str],
        *,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", *arguments],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
            env={"PATH": os.environ.get("PATH", "")},
        )


class SandboxedValidationExecutor:
    """
    Runs fixed validation profiles only inside a resource-bounded Docker container.

    The project is first staged into a temporary workspace. A failed build marks
    the tests as skipped. A timeout raises ToolExecutionError. The DockerRuntime is
    injected, so tests can replace the real docker subprocess.
    """

    def __init__(
        self,
        *,
        limits: SandboxLimits = DEFAULT_SANDBOX_LIMITS,
        runtime: DockerRuntime | None = None,
    ) -> None:
        self._limits = limits
        self._runtime = runtime or SubprocessDockerRuntime()
        self._container_user = self._select_container_user()

    def execute(self, request: ValidationExecutionRequest) -> ValidationExecutionResult:
        with tempfile.TemporaryDirectory(prefix="agileflow-agent4-") as temporary:
            workspace = Path(temporary).resolve()
            staged_files = materialize_project(workspace, request.source)
            self._prepare_workspace_permissions(workspace, staged_files)

            sandbox = self._sandbox_metadata(request.profile)
            if request.profile is None:
                skipped = self._skipped(
                    "No validation profile was selected; executable validation was not requested",
                    sandbox,
                )
                return ValidationExecutionResult(build=skipped, tests=skipped, sandbox=sandbox)

            self._require_docker()
            config = VALIDATION_PROFILES[request.profile]
            build = self._run_container(workspace, request.profile, config, config.build_command)
            if build.timed_out:
                raise ToolExecutionError("Secure validation exceeded the execution time limit")
            if build.execution_status == "FAILED":
                tests = self._skipped(
                    "Test execution was skipped because the sandboxed build failed", sandbox
                )
            else:
                tests = self._run_container(
                    workspace, request.profile, config, config.test_command
                )
                if tests.timed_out:
                    raise ToolExecutionError("Secure validation exceeded the execution time limit")
            return ValidationExecutionResult(build=build, tests=tests, sandbox=sandbox)

    def _require_docker(self) -> None:
        if isinstance(self._runtime, SubprocessDockerRuntime) and shutil.which("docker") is None:
            raise ToolExecutionError("Secure validation sandbox is unavailable")
        try:
            result = self._runtime.run(
                ["version", "--format", "{{.Server.Version}}"],
                timeout_seconds=self._limits.docker_operation_timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ToolExecutionError("Secure validation sandbox is unavailable") from exc
        if result.returncode != 0 or not result.stdout.strip():
            raise ToolExecutionError("Secure validation sandbox is unavailable")

    def _run_container(
        self,
        workspace: Path,
        profile: ValidationProfile,
        config: ValidationProfileConfig,
        command: tuple[str, ...],
    ) -> ValidationCommandResult:
        container_name = f"agileflow-agent4-{uuid.uuid4().hex}"
        metadata = self._sandbox_metadata(profile)
        create_arguments = self._container_arguments(
            container_name, workspace, config.image, command
        )
        try:
            created = self._runtime.run(
                create_arguments,
                timeout_seconds=self._limits.docker_operation_timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ToolExecutionError("Secure validation sandbox could not be created") from exc
        if created.returncode != 0:
            raise ToolExecutionError(
                "Secure validation sandbox image is unavailable or could not be created"
            )

        started_at = time.monotonic()
        timed_out = False
        exit_code: int | None = None
        stdout = ""
        stderr = ""
        try:
            started = self._runtime.run(
                ["start", container_name],
                timeout_seconds=self._limits.docker_operation_timeout_seconds,
            )
            if started.returncode != 0:
                raise ToolExecutionError("Secure validation sandbox could not be started")
            try:
                waited = self._runtime.run(
                    ["wait", container_name],
                    timeout_seconds=self._limits.execution_timeout_seconds,
                )
                if waited.returncode != 0:
                    raise ToolExecutionError("Secure validation sandbox did not return evidence")
                exit_code = int(waited.stdout.strip())
            except subprocess.TimeoutExpired:
                timed_out = True

            logs = self._runtime.run(
                ["logs", container_name],
                timeout_seconds=self._limits.docker_operation_timeout_seconds,
            )
            stdout = _redact(logs.stdout)
            stderr = _redact(logs.stderr)
        except ToolExecutionError:
            raise
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ToolExecutionError(
                "Secure validation sandbox did not return evidence"
            ) from exc
        finally:
            try:
                removed = self._runtime.run(
                    ["rm", "--force", "--volumes", container_name],
                    timeout_seconds=self._limits.docker_operation_timeout_seconds,
                )
                if removed.returncode != 0:
                    raise ToolExecutionError(
                        "Secure validation sandbox cleanup could not be confirmed"
                    )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ToolExecutionError(
                    "Secure validation sandbox cleanup could not be confirmed"
                ) from exc

        duration = round(time.monotonic() - started_at, 3)
        status = "TIMED_OUT" if timed_out else ("PASSED" if exit_code == 0 else "FAILED")
        return ValidationCommandResult(
            command=list(command),
            tool=profile.value,
            exit_code=exit_code,
            execution_status=status,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timed_out=timed_out,
            reason=(
                f"Exceeded {self._limits.execution_timeout_seconds} second limit"
                if timed_out
                else None
            ),
            evidence_metadata=metadata,
        )

    def _container_arguments(
        self,
        container_name: str,
        workspace: Path,
        image: str,
        command: tuple[str, ...],
    ) -> list[str]:
        limits = self._limits
        return [
            "create",
            "--name", container_name,
            "--pull", "never",
            "--network", "none",
            "--memory", limits.memory,
            "--cpus", str(limits.cpu_count),
            "--pids-limit", str(limits.pids),
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", self._container_user,
            "--env", "HOME=/tmp",
            "--env", "CI=true",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--tmpfs", f"/tmp:rw,nosuid,nodev,size={limits.temporary_storage}",
            "--mount", f"type=bind,source={workspace},target=/workspace",
            "--workdir", "/workspace",
            "--label", "agileflow.component=agent4-validation",
            image,
            *command,
        ]

    def _sandbox_metadata(self, profile: ValidationProfile | None) -> dict[str, Any]:
        limits = self._limits
        return {
            "executor": "DOCKER",
            "profile": profile.value if profile else None,
            "network": "NONE",
            "cpu_count": limits.cpu_count,
            "memory_limit": limits.memory,
            "pid_limit": limits.pids,
            "timeout_seconds": limits.execution_timeout_seconds,
            "temporary_storage": limits.temporary_storage,
            "read_only_root": True,
            "non_root_user": self._container_user,
            "capabilities_dropped": "ALL",
            "no_new_privileges": True,
            "image_pull": "NEVER",
        }

    @staticmethod
    def _select_container_user() -> str:
        if os.name == "nt" or not hasattr(os, "getuid"):
            return "65532:65532"
        uid, gid = os.getuid(), os.getgid()
        return "65532:65532" if uid == 0 else f"{uid}:{gid}"

    def _prepare_workspace_permissions(
        self, workspace: Path, staged_files: list[Path]
    ) -> None:
        if os.name == "nt" or not hasattr(os, "getuid"):
            return
        uid_text, gid_text = self._container_user.split(":", 1)
        uid, gid = int(uid_text), int(gid_text)
        directories = {workspace}
        for staged_file in staged_files:
            parent = staged_file.parent
            while parent != workspace:
                directories.add(parent)
                parent = parent.parent
        for path in sorted(directories, key=lambda item: len(item.parts)):
            if os.getuid() == 0:
                os.chown(path, uid, gid, follow_symlinks=False)
            path.chmod(0o700)
        for path in staged_files:
            if os.getuid() == 0:
                os.chown(path, uid, gid, follow_symlinks=False)
            path.chmod(0o600)

    @staticmethod
    def _skipped(reason: str, metadata: dict[str, Any]) -> ValidationCommandResult:
        return ValidationCommandResult(
            command=[],
            tool="NONE",
            exit_code=None,
            execution_status="SKIPPED",
            stdout="",
            stderr="",
            reason=reason,
            evidence_metadata=metadata,
        )
