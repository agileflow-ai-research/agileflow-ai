"""Deterministic structural file catalog for the frozen Agent 3 PP1 stack."""

from dataclasses import dataclass

from app.modules.agents.implementation.contracts.enums import (
    ImplementationOutputCode as Output,
)

from .schemas import PlannedFileCategory


@dataclass(frozen=True)
class StructuralFileRule:
    relative_path: str
    responsibility: str
    output_triggers: frozenset[Output]
    file_category: PlannedFileCategory
    dependency_paths: tuple[str, ...] = ()


STRUCTURAL_FILE_RULES = (
    StructuralFileRule(
        "README.md",
        "Describe the approved project structure and future generated application.",
        frozenset({Output.PROJECT_STRUCTURE}),
        PlannedFileCategory.PROJECT_STRUCTURE,
    ),
    StructuralFileRule(
        "frontend/package.json",
        "Declare the React and Vite frontend package boundary.",
        frozenset({Output.FRONTEND_CODE}),
        PlannedFileCategory.FRONTEND,
    ),
    StructuralFileRule(
        "frontend/index.html",
        "Provide the Vite frontend HTML entry point.",
        frozenset({Output.FRONTEND_CODE}),
        PlannedFileCategory.FRONTEND,
        ("frontend/package.json",),
    ),
    StructuralFileRule(
        "frontend/src/styles.css",
        "Provide the approved plain-CSS styling entry point.",
        frozenset({Output.FRONTEND_CODE}),
        PlannedFileCategory.FRONTEND,
        ("frontend/package.json",),
    ),
    StructuralFileRule(
        "frontend/src/App.jsx",
        "Compose the verified frontend page modules.",
        frozenset({Output.FRONTEND_CODE}),
        PlannedFileCategory.FRONTEND,
        ("frontend/package.json",),
    ),
    StructuralFileRule(
        "frontend/src/main.jsx",
        "Bootstrap the React application through Vite.",
        frozenset({Output.FRONTEND_CODE}),
        PlannedFileCategory.FRONTEND,
        (
            "frontend/package.json",
            "frontend/src/App.jsx",
            "frontend/src/styles.css",
        ),
    ),
    StructuralFileRule(
        "backend/package.json",
        "Declare the Node.js and Express.js backend package boundary.",
        frozenset({Output.BACKEND_CODE, Output.API_IMPLEMENTATION}),
        PlannedFileCategory.BACKEND,
    ),
    StructuralFileRule(
        "backend/src/app.js",
        "Compose and configure the Express.js REST application.",
        frozenset({Output.BACKEND_CODE, Output.API_IMPLEMENTATION}),
        PlannedFileCategory.BACKEND,
        ("backend/package.json",),
    ),
    StructuralFileRule(
        "database/schema.sql",
        "Define the verified MySQL database entities and fields.",
        frozenset({Output.DATABASE_IMPLEMENTATION}),
        PlannedFileCategory.DATABASE,
    ),
    StructuralFileRule(
        ".gitignore",
        "Define generated-project exclusions without changing repository state.",
        frozenset({Output.CONFIGURATION_FILES}),
        PlannedFileCategory.CONFIGURATION,
    ),
    StructuralFileRule(
        ".env.example",
        "Document placeholder configuration keys without credentials.",
        frozenset({Output.CONFIGURATION_FILES}),
        PlannedFileCategory.CONFIGURATION,
    ),
    StructuralFileRule(
        "docker-compose.yml",
        "Describe future isolated services for the approved PP1 stack.",
        frozenset({Output.CONTAINER_CONFIGURATION}),
        PlannedFileCategory.CONTAINER,
    ),
)


GIT_SUMMARY_RESPONSIBILITY = (
    "Summarize future Git delivery results without representing a source file."
)
