"""Pydantic request schemas (responses are plain dicts built in routes.py)."""
from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class RemarksIn(BaseModel):
    remarks: str = ""


class ForwardIn(BaseModel):
    field_verification_required: bool
    remarks: str = ""


class ObservationsIn(BaseModel):
    visit_date: str = ""
    persons_met: str = ""
    residence_type: str = ""
    livelihood: str = ""
    assets: str = ""
    neighbour_statement: str = ""
    notes: str = ""


class FieldReportIn(BaseModel):
    observations: ObservationsIn
    report_text: str = Field(min_length=10)
    ai_mode: Literal["live", "demo"] | None = None  # set if the text was drafted by AI, else None


class DecisionIn(BaseModel):
    decision: Literal["APPROVE", "REJECT", "RETURN"]
    remarks: str = ""


class LangIn(BaseModel):
    lang: str = "te"


class UserIn(BaseModel):
    username: str = Field(min_length=3)
    full_name: str
    full_name_te: str = ""
    role: Literal["VRO", "REVENUE_INSPECTOR", "TAHSILDAR", "ADMIN"]
    password: str = Field(min_length=6)
