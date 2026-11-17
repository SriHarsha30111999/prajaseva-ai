"""SQLAlchemy models: users, applications, documents, tasks, reports, AI logs, audit history."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Roles
VRO, RI, TAHSILDAR, ADMIN = "VRO", "REVENUE_INSPECTOR", "TAHSILDAR", "ADMIN"
ROLES = [VRO, RI, TAHSILDAR, ADMIN]

# Statuses
SUBMITTED = "SUBMITTED"
UNDER_SCRUTINY = "UNDER_SCRUTINY"
RETURNED = "RETURNED_FOR_CORRECTION"
AWAITING_FIELD = "AWAITING_FIELD_VERIFICATION"
AWAITING_FINAL = "AWAITING_FINAL_REVIEW"
APPROVED = "APPROVED"
REJECTED = "REJECTED"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    full_name_te: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[str] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    app_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    applicant_name: Mapped[str] = mapped_column(String(100))
    guardian_name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(10))
    village: Mapped[str] = mapped_column(String(80))
    mandal: Mapped[str] = mapped_column(String(80))
    district: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(String(250))
    occupation: Mapped[str] = mapped_column(String(100))
    household_members: Mapped[int] = mapped_column(Integer, default=1)
    declared_income: Mapped[float] = mapped_column(Float)  # annual, INR
    purpose: Mapped[str] = mapped_column(String(150))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(40), default=SUBMITTED, index=True)
    # Stage owner: VRO / REVENUE_INSPECTOR / TAHSILDAR / APPLICANT / COMPLETED
    current_stage: Mapped[str] = mapped_column(String(30), default=VRO)
    # None = not decided yet. Field verification is conditional, not mandatory.
    field_verification_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Admin "delete" archives the record; audit history is never erased through the API.
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    documents = relationship("Document", cascade="all, delete-orphan", order_by="Document.id")
    tasks = relationship("WorkflowTask", cascade="all, delete-orphan", order_by="WorkflowTask.id")
    reports = relationship("VerificationReport", cascade="all, delete-orphan", order_by="VerificationReport.id")
    ai_logs = relationship("AILog", cascade="all, delete-orphan", order_by="AILog.id")
    history = relationship("AuditLog", cascade="all, delete-orphan", order_by="AuditLog.id")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    doc_type: Mapped[str] = mapped_column(String(40))  # AADHAAR, RATION_CARD, INCOME_DECLARATION, SALARY_SLIP, ...
    filename: Mapped[str] = mapped_column(String(200))
    stored_path: Mapped[str] = mapped_column(String(300))
    # DEMO DATA: text that stands in for the scanned document's content (no OCR in this prototype).
    content_text: Mapped[str] = mapped_column(Text, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    stage: Mapped[str] = mapped_column(String(30))  # role that must act
    status: Mapped[str] = mapped_column(String(10), default="OPEN")  # OPEN / DONE
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class VerificationReport(Base):
    __tablename__ = "verification_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    observations: Mapped[dict] = mapped_column(JSON, default=dict)
    report_text: Mapped[str] = mapped_column(Text, default="")
    ai_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)  # live / demo / None (written manually)
    submitted_by: Mapped[str] = mapped_column(String(100))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AILog(Base):
    __tablename__ = "ai_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    kind: Mapped[str] = mapped_column(String(30))  # ANALYSIS / FIELD_REPORT / CASE_SUMMARY
    mode: Mapped[str] = mapped_column(String(10))  # live / demo
    model: Mapped[str] = mapped_column(String(60), default="")
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    action: Mapped[str] = mapped_column(String(60))
    user_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(30))
    remarks: Mapped[str] = mapped_column(Text, default="")
    previous_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
