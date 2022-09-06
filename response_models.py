from pydantic import BaseModel
from datetime import datetime


class BaseResponse(BaseModel):
    success: bool


class BalanceCheckResponse(BaseModel):
    balance: int
    username: str


class TargetCheckResponse(BaseModel):
    target_account: str
    target_name: str


class InstantTransferResponse(BaseModel):
    target_account: str
    target_name: str
    time: str


class ScheduledTransferResponse(BaseModel):
    target_account: str
    target_name: str
    request_time: str
    transfer_time: str


class MessageResponse(BaseResponse):
    message: str
