from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.status import AgentRunMode, AgentRunStatus, AgentType
from app.modules.standalone.schemas import AgentRunMessage


class DesignPlanningOutputCode(StrEnum):
    SYSTEM_ARCHITECTURE = "SYSTEM_ARCHITECTURE"
    UML_DIAGRAMS = "UML_DIAGRAMS"
    DATABASE_SCHEMA = "DATABASE_SCHEMA"
    API_SPECIFICATION = "API_SPECIFICATION"
    WIREFRAMES = "WIREFRAMES"
    UI_FLOW = "UI_FLOW"
    PRODUCT_BACKLOG = "PRODUCT_BACKLOG"
    EPICS = "EPICS"
    FEATURES = "FEATURES"
    USER_STORIES = "USER_STORIES"
    TASKS = "TASKS"
    SPRINT_PLAN = "SPRINT_PLAN"
    TASK_ASSIGNMENT = "TASK_ASSIGNMENT"
    JIRA_PLAN = "JIRA_PLAN"


CAPACITY_OUTPUTS = {
    DesignPlanningOutputCode.SPRINT_PLAN,
    DesignPlanningOutputCode.TASK_ASSIGNMENT,
    DesignPlanningOutputCode.JIRA_PLAN,
}


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class Agent2RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    requirements: str | None = None
    srs: str | None = Field(default=None, alias="SRS")
    user_stories: str | None = None
    acceptance_criteria: str | None = None
    technical_constraints: str | None = None
    preferred_technology_stack: str | None = None
    deployment_preference: str | None = None
    database_preference: str | None = None
    ui_ux_constraints: str | None = None
    architecture_notes: str | None = None
    development_team_count: int | None = Field(default=None, gt=0)
    sprint_duration: int | None = Field(default=None, gt=0)
    expected_project_duration: str | None = None
    developer_roles: str | None = None
    developer_skills: str | None = None
    team_composition: str | None = None
    selected_outputs: list[DesignPlanningOutputCode] = Field(min_length=1)

    @field_validator(
        "requirements", "srs", "user_stories", "acceptance_criteria",
        "technical_constraints", "preferred_technology_stack",
        "deployment_preference", "database_preference", "ui_ux_constraints",
        "architecture_notes", "expected_project_duration", "developer_roles",
        "developer_skills", "team_composition",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("selected_outputs")
    @classmethod
    def reject_duplicate_outputs(
        cls, values: list[DesignPlanningOutputCode]
    ) -> list[DesignPlanningOutputCode]:
        if len(values) != len(set(values)):
            raise ValueError("selected_outputs must not contain duplicates")
        return values

    @model_validator(mode="after")
    def validate_conditional_inputs(self) -> "Agent2RunRequest":
        if not any((self.requirements, self.srs, self.user_stories, self.acceptance_criteria)):
            raise ValueError(
                "at least one usable specification source is required: requirements, SRS, user_stories, or acceptance_criteria"
            )
        selected = set(self.selected_outputs)
        if selected & CAPACITY_OUTPUTS and self.development_team_count is None:
            raise ValueError(
                "development_team_count is required for SPRINT_PLAN, TASK_ASSIGNMENT, and JIRA_PLAN"
            )
        if DesignPlanningOutputCode.SPRINT_PLAN in selected and self.sprint_duration is None:
            raise ValueError("sprint_duration is required for SPRINT_PLAN")
        return self


class SpecificationSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(pattern=r"^SPEC-\d{3,}$")
    source_type: Literal["REQUIREMENTS", "SRS", "USER_STORIES", "ACCEPTANCE_CRITERIA"]
    content: str = Field(min_length=1)


class Agent2InputContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    specification_sources: list[SpecificationSource] = Field(min_length=1)
    technical_constraints: str | None = None
    preferred_technology_stack: str | None = None
    deployment_preference: str | None = None
    database_preference: str | None = None
    ui_ux_constraints: str | None = None
    architecture_notes: str | None = None
    development_team_count: int | None = Field(default=None, gt=0)
    sprint_duration: int | None = Field(default=None, gt=0)
    expected_project_duration: str | None = None
    developer_roles: str | None = None
    developer_skills: str | None = None
    team_composition: str | None = None


class ArchitectureComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^COMP-\d{3,}$")
    name: str
    responsibility: str
    dependencies: list[str]
    source_refs: list[str] = Field(min_length=1)


class SystemArchitecture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: str
    components: list[ArchitectureComponent] = Field(min_length=1)
    boundaries: list[str]
    interactions: list[str]
    constraints: list[str]
    assumptions: list[str]


class Diagram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^UML-\d{3,}$")
    title: str
    diagram_type: str
    notation: Literal["MERMAID", "PLANTUML"]
    source: str
    source_refs: list[str] = Field(min_length=1)


class UmlDiagrams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diagrams: list[Diagram] = Field(min_length=1)
    assumptions: list[str]


class DatabaseField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    data_type: str
    required: bool
    constraints: list[str]


class DatabaseRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_entity_id: str = Field(pattern=r"^ENTITY-\d{3,}$")
    relationship_type: str
    description: str


class DatabaseEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^ENTITY-\d{3,}$")
    name: str
    fields: list[DatabaseField] = Field(min_length=1)
    relationships: list[DatabaseRelationship]
    source_refs: list[str] = Field(min_length=1)


class DatabaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    technology: str
    entities: list[DatabaseEntity] = Field(min_length=1)
    assumptions: list[str]


class ApiOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^API-\d{3,}$")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    summary: str
    request: str | None
    response: str
    errors: list[str]
    authentication: str
    source_refs: list[str] = Field(min_length=1)
    component_refs: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)


class ApiSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_path: str
    operations: list[ApiOperation] = Field(min_length=1)
    assumptions: list[str]


class WireframeScreen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^WF-\d{3,}$")
    name: str
    purpose: str
    regions: list[str] = Field(min_length=1)
    interactions: list[str]
    source_refs: list[str] = Field(min_length=1)
    components: list[str] = Field(default_factory=list)


class Wireframes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fidelity: Literal["STRUCTURED_LOW_FIDELITY"]
    screens: list[WireframeScreen] = Field(min_length=1)
    assumptions: list[str]


class UiFlowItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^FLOW-\d{3,}$")
    actor: str
    goal: str
    steps: list[str] = Field(min_length=1)
    alternate_paths: list[str]
    source_refs: list[str] = Field(min_length=1)
    screen_refs: list[str] = Field(default_factory=list)


class UiFlow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flows: list[UiFlowItem] = Field(min_length=1)


class Epic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^EPIC-\d{3,}$")
    title: str
    outcome: str
    priority: Literal["HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST"]
    source_refs: list[str] = Field(min_length=1)


class Feature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^FEATURE-\d{3,}$")
    epic_id: str = Field(pattern=r"^EPIC-\d{3,}$")
    title: str
    description: str
    source_refs: list[str] = Field(min_length=1)


class PlanningStory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^STORY-\d{3,}$")
    epic_id: str = Field(pattern=r"^EPIC-\d{3,}$")
    feature_id: str = Field(pattern=r"^FEATURE-\d{3,}$")
    actor: str
    goal: str
    benefit: str
    acceptance_criteria: list[str] = Field(min_length=1)
    priority: Literal["HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST"]
    estimate_points: int = Field(gt=0)
    source_refs: list[str] = Field(min_length=1)


class PlanningTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^TASK-\d{3,}$")
    epic_id: str = Field(pattern=r"^EPIC-\d{3,}$")
    feature_id: str = Field(pattern=r"^FEATURE-\d{3,}$")
    story_id: str = Field(pattern=r"^STORY-\d{3,}$")
    title: str
    description: str
    required_skills: list[str]
    estimate_points: int = Field(gt=0)
    depends_on: list[str]
    source_refs: list[str] = Field(min_length=1)


class BacklogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str
    item_type: Literal["EPIC", "FEATURE", "STORY", "TASK"]
    title: str
    priority: Literal["HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST"]
    parent_id: str | None
    source_refs: list[str] = Field(min_length=1)


class Sprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^SPRINT-\d{3,}$")
    name: str
    duration_days: int = Field(gt=0)
    capacity_points: int = Field(gt=0)
    item_refs: list[str] = Field(min_length=1)
    dependency_notes: list[str]
    planned_points: int = Field(default=0, ge=0)
    utilization_percent: float = Field(default=0, ge=0)
    planning_warnings: list[str] = Field(default_factory=list)
    estimate_basis: str = "Estimated capacity uses team count × sprint duration in days."


class TaskAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(pattern=r"^TASK-\d{3,}$")
    team_slot: str
    role: str
    rationale: str
    sprint_id: str | None = Field(default=None, pattern=r"^SPRINT-\d{3,}$")
    matching_reasons: list[str] = Field(default_factory=list)
    role_match: bool = False
    skill_matches: list[str] = Field(default_factory=list)
    workload_points_before: int = Field(default=0, ge=0)
    confidence_score: int = Field(default=0, ge=0, le=100)


class JiraPriority(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str
    priority: Literal["HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST"]


class JiraPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    epics: list[Epic] = Field(min_length=1)
    stories: list[PlanningStory] = Field(min_length=1)
    tasks: list[PlanningTask] = Field(min_length=1)
    sprints: list[Sprint]
    assignments: list[TaskAssignment]
    priorities: list[JiraPriority] = Field(min_length=1)
    synchronization: Literal["NOT_PERFORMED"]


OUTPUT_MODELS: dict[DesignPlanningOutputCode, Any] = {
    DesignPlanningOutputCode.SYSTEM_ARCHITECTURE: SystemArchitecture,
    DesignPlanningOutputCode.UML_DIAGRAMS: UmlDiagrams,
    DesignPlanningOutputCode.DATABASE_SCHEMA: DatabaseSchema,
    DesignPlanningOutputCode.API_SPECIFICATION: ApiSpecification,
    DesignPlanningOutputCode.WIREFRAMES: Wireframes,
    DesignPlanningOutputCode.UI_FLOW: UiFlow,
    DesignPlanningOutputCode.PRODUCT_BACKLOG: list[BacklogItem],
    DesignPlanningOutputCode.EPICS: list[Epic],
    DesignPlanningOutputCode.FEATURES: list[Feature],
    DesignPlanningOutputCode.USER_STORIES: list[PlanningStory],
    DesignPlanningOutputCode.TASKS: list[PlanningTask],
    DesignPlanningOutputCode.SPRINT_PLAN: list[Sprint],
    DesignPlanningOutputCode.TASK_ASSIGNMENT: list[TaskAssignment],
    DesignPlanningOutputCode.JIRA_PLAN: JiraPlan,
}


class Agent2RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    agent_project_id: str
    agent_type: AgentType
    run_mode: AgentRunMode
    status: AgentRunStatus
    selected_outputs: list[str]
    started_at: datetime | None
    completed_at: datetime | None
    outputs: dict[str, Any]
    warnings: list[AgentRunMessage]
    errors: list[AgentRunMessage]
    correction_attempts: int = 0


class DocumentExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: Literal["REQUIREMENTS", "SRS", "USER_STORIES", "ACCEPTANCE_CRITERIA"]
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    character_count: int
    extracted_text: str
    extraction_status: Literal["COMPLETED"] = "COMPLETED"
