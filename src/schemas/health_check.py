from pydantic import BaseModel


class HealthCheck(BaseModel):
    status: str
    version: str
    db_status: str
    uptime: str
