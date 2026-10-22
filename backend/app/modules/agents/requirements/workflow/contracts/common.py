from pydantic import BaseModel, ConfigDict


class StrictWorkflowContract(BaseModel):
    """Common validation policy without defining persisted fields."""

    model_config = ConfigDict(extra="forbid")
