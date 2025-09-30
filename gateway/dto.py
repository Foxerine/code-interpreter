from enum import StrEnum
from pydantic import BaseModel, Field
import time

class WorkerStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    CREATING = "creating"
    ERROR = "error"

class Worker(BaseModel):
    """Represents the internal state of a Worker container in the Gateway."""
    container_id: str
    container_name: str
    internal_url: str
    status: WorkerStatus = WorkerStatus.CREATING
    user_uuid: str | None = None
    last_active_timestamp: float = Field(default_factory=time.time)

class ExecuteRequest(BaseModel):
    user_uuid: str
    code: str

class ExecuteResponse(BaseModel):
    result_text: str | None = None
    result_base64: str | None = None

class ReleaseRequest(BaseModel):
    user_uuid: str

class ReleaseResponse(BaseModel):
    status: str
    detail: str

class ErrorDetail(BaseModel):
    detail: str
