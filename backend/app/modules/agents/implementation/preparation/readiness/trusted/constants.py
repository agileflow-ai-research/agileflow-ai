from app.modules.agents.implementation.contracts.enums import ImplementationOutputCode
from app.modules.agents.implementation.preparation.schemas import ArtifactDetectionLabel


TRUSTED_READINESS_POLICY_VERSION = "1"
TRUSTED_READINESS_SCHEMA_VERSION = "1"

F = ArtifactDetectionLabel
O = ImplementationOutputCode

# Required groups are alternatives: at least one category in every group must
# be present. Recommended categories create warnings only.
OUTPUT_POLICY = {
    O.PROJECT_STRUCTURE: {
        "required": ((F.FUNCTIONAL_REQUIREMENTS, F.USER_STORIES,
                      F.IMPLEMENTATION_TASKS),),
        "recommended": (F.SYSTEM_ARCHITECTURE, F.TECHNOLOGY_STACK,
                        F.TECHNICAL_CONSTRAINTS),
    },
    O.FRONTEND_CODE: {
        "required": ((F.FUNCTIONAL_REQUIREMENTS, F.USER_STORIES,
                      F.ACCEPTANCE_CRITERIA),),
        "recommended": (F.UI_FLOW, F.ACCEPTANCE_CRITERIA, F.TEST_CASES),
    },
    O.BACKEND_CODE: {
        "required": ((F.FUNCTIONAL_REQUIREMENTS, F.USER_STORIES,
                      F.API_SPECIFICATION),),
        "recommended": (F.API_SPECIFICATION, F.ACCEPTANCE_CRITERIA,
                        F.NON_FUNCTIONAL_REQUIREMENTS, F.TEST_CASES),
    },
    O.DATABASE_IMPLEMENTATION: {
        "required": ((F.FUNCTIONAL_REQUIREMENTS, F.USER_STORIES,
                      F.IMPLEMENTATION_TASKS), (F.DATABASE_SCHEMA,)),
        "recommended": (F.TECHNICAL_CONSTRAINTS, F.ACCEPTANCE_CRITERIA,
                        F.TEST_CASES),
    },
    O.API_IMPLEMENTATION: {
        "required": ((F.FUNCTIONAL_REQUIREMENTS, F.USER_STORIES,
                      F.IMPLEMENTATION_TASKS), (F.API_SPECIFICATION,)),
        "recommended": (F.ACCEPTANCE_CRITERIA, F.NON_FUNCTIONAL_REQUIREMENTS,
                        F.TEST_CASES),
    },
    O.CONFIGURATION_FILES: {
        "required": ((F.FUNCTIONAL_REQUIREMENTS, F.USER_STORIES,
                      F.IMPLEMENTATION_TASKS),),
        "recommended": (F.TECHNOLOGY_STACK, F.TECHNICAL_CONSTRAINTS),
    },
    O.CONTAINER_CONFIGURATION: {
        "required": ((F.FUNCTIONAL_REQUIREMENTS, F.USER_STORIES,
                      F.IMPLEMENTATION_TASKS),),
        "recommended": (F.TECHNOLOGY_STACK, F.TECHNICAL_CONSTRAINTS),
    },
    # Delivery configuration is intentionally absent. GitHub is a later node.
    O.GIT_SUMMARY: {
        "required": ((F.FUNCTIONAL_REQUIREMENTS, F.USER_STORIES,
                      F.IMPLEMENTATION_TASKS),),
        "recommended": (),
    },
}

EFFECTIVE_STACK = {
    "frontend": "React + Vite",
    "styling": "Plain CSS",
    "backend": "Node.js + Express.js",
    "database": "MySQL",
    "language": "JavaScript",
    "api_style": "REST",
}
