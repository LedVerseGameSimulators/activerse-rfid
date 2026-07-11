"""Pydantic request/response schemas."""
from typing import Optional
from pydantic import BaseModel, Field


class PlayerCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    age: Optional[int] = None
    public: bool = True
    notes: Optional[str] = None


class PlayerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    public: Optional[bool] = None
    notes: Optional[str] = None


class BindCardRequest(BaseModel):
    card_id: str


class SessionCreate(BaseModel):
    player_id: int
    duration_min: int = Field(default=60, ge=1)
    notes: Optional[str] = ""


class SessionAdjust(BaseModel):
    delta_min: int
    reason: str = ""
    adjusted_by: str = ""


class ValidateResponse(BaseModel):
    valid: bool
    player_name: Optional[str] = None
    session_id: Optional[int] = None
    minutes_remaining: Optional[float] = None
    reason: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    username: str
    password: str
