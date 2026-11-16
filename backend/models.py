from typing import Any, Literal

from pydantic import BaseModel, Field


class ExperimentRequest(BaseModel):
    controller: Literal["baseline", "reactive", "fast_failover", "adaptive"] = "reactive"
    topology: Literal["diamond", "multipath_mesh"] = "diamond"
    failure_link: str | None = Field(default=None, pattern=r"^s\d+-s\d+$")


class Experiment(BaseModel):
    id: int
    controller: str
    topology: str
    failure_link: str | None
    status: str
    started_at: str
    finished_at: str | None
    summary: dict[str, Any]


class Event(BaseModel):
    id: int
    event_type: str
    severity: str
    message: str
    created_at: str
    metadata: dict[str, Any]


class Health(BaseModel):
    status: str
    database: str
    telemetry_file: str

