from pydantic import BaseModel


class TargetCheckRequest(BaseModel):
    target_account: str


class InstantTransferRequest(BaseModel):
    target_account: str
    nominal: int


class ScheduledTransferRequest(BaseModel):
    target_account: str
    nominal: str
    schedule: str
