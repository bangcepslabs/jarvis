from pydantic import BaseModel, ConfigDict, Field


class ListContainersArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    all: bool = True


class ContainerArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    container: str = Field(min_length=1, max_length=256)


class ContainerLogsArguments(ContainerArguments):
    tail: int = Field(default=100, ge=1, le=500)
