"""API routes + workflow state machine.

Workflow:
  SUBMITTED -> UNDER_SCRUTINY (VRO)
  UNDER_SCRUTINY -> AWAITING_FIELD_VERIFICATION (VRO, if field check is needed)
                 -> AWAITING_FINAL_REVIEW        (VRO, if not needed)
                 -> RETURNED_FOR_CORRECTION      (VRO)
  AWAITING_FIELD_VERIFICATION -> AWAITING_FINAL_REVIEW (Revenue Inspector submits report)
  AWAITING_FINAL_REVIEW -> APPROVED | REJECTED (Tahsildar) | UNDER_SCRUTINY (Tahsildar returns to VRO)
  RETURNED_FOR_CORRECTION -> SUBMITTED (admin simulates applicant resubmission - demo only)

Every endpoint is protected with JWT; every action checks BOTH the caller's role and the
application's current status, so direct API calls cannot bypass the workflow.
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import ai_service
from . import models as m
from .auth import create_token, hash_password, require_roles, get_current_user, verify_password
from .database import UPLOAD_DIR, SessionLocal, get_db
from .schemas import DecisionIn, FieldReportIn, ForwardIn, LangIn, LoginIn, ObservationsIn, RemarksIn, UserIn

router = APIRouter(prefix="/api")
ALL = (m.VRO, m.RI, m.TAHSILDAR, m.ADMIN)

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".png", ".jpg", ".jpeg"}
DOC_TYPES = {"AADHAAR", "RATION_CARD", "INCOME_DECLARATION", "SALARY_SLIP", "OTHER"}


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


# ------------------------------------------------------------------ helpers


def get_app(db: Session, app_id: int) -> m.Application:
    app = db.get(m.Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return app


def expect_status(app: m.Application, *statuses: str):
    if app.archived:
        raise HTTPException(409, "Application is archived")
    if app.status not in statuses:
        raise HTTPException(409, f"Action not allowed while application is '{app.status}'")


def transition(db, app, user, action, new_status, remarks="", stage=None):
    """Move an application to a new status; closes the open task, opens the next one, writes audit history."""
    prev = app.status
    for task in app.tasks:
        if task.status == "OPEN":
            task.status, task.completed_at, task.completed_by = "DONE", m.now(), user.full_name
    app.status = new_status
    app.current_stage = stage or {
        m.SUBMITTED: m.VRO, m.UNDER_SCRUTINY: m.VRO, m.RETURNED: "APPLICANT", m.AWAITING_FIELD: m.RI,
        m.AWAITING_FINAL: m.TAHSILDAR, m.APPROVED: "COMPLETED", m.REJECTED: "COMPLETED"}[new_status]
    if app.current_stage in (m.VRO, m.RI, m.TAHSILDAR):
        db.add(m.WorkflowTask(application_id=app.id, stage=app.current_stage))
    db.add(m.AuditLog(application_id=app.id, action=action, user_name=user.full_name, role=user.role,
                      remarks=remarks, previous_status=prev, new_status=new_status))


def audit_only(db, app, user, action, remarks=""):
    db.add(m.AuditLog(application_id=app.id, action=action, user_name=user.full_name, role=user.role,
                      remarks=remarks, previous_status=app.status, new_status=app.status))


def need_remarks(text: str, what: str):
    if len(text.strip()) < 5:
        raise HTTPException(422, f"Remarks are required to {what}")


def available_actions(app: m.Application, user: m.User) -> list[str]:
    r, s, acts = user.role, app.status, []
    if app.archived:
        return []
    if r == m.VRO:
        if s == m.SUBMITTED:
            acts = ["start_scrutiny"]
        elif s == m.UNDER_SCRUTINY:
            acts = ["ai_analyze", "forward", "return", "upload_document"]
    elif r == m.RI and s == m.AWAITING_FIELD:
        acts = ["ai_field_report", "submit_field_report"]
    elif r == m.TAHSILDAR and s == m.AWAITING_FINAL:
        acts = ["ai_summary", "decide"]
    elif r == m.ADMIN:
        acts = ["archive"]
        if s == m.RETURNED:
            acts.append("resubmit")
        if s not in (m.APPROVED, m.REJECTED):
            acts.append("upload_document")
    return acts


def app_row(a: m.Application) -> dict:
    return {"id": a.id, "app_no": a.app_no, "applicant_name": a.applicant_name, "village": a.village,
            "mandal": a.mandal, "purpose": a.purpose, "declared_income": a.declared_income,
            "submitted_at": iso(a.submitted_at), "status": a.status, "current_stage": a.current_stage,
            "archived": a.archived}


def ai_out(log: m.AILog | None):
    if not log:
        return None
    return {"id": log.id, "kind": log.kind, "mode": log.mode, "model": log.model, "output": log.output,
            "requested_by": log.requested_by, "created_at": iso(log.created_at)}


def latest_log(app, kind):
    return next((l for l in reversed(app.ai_logs) if l.kind == kind), None)


def app_detail(a: m.Application, user: m.User) -> dict:
    d = app_row(a)
    d.update({
        "guardian_name": a.guardian_name, "age": a.age, "gender": a.gender, "district": a.district,
        "address": a.address, "occupation": a.occupation, "household_members": a.household_members,
        "field_verification_required": a.field_verification_required,
        "documents": [{"id": x.id, "doc_type": x.doc_type, "filename": x.filename, "content_text": x.content_text,
                       "uploaded_at": iso(x.uploaded_at)} for x in a.documents],
        "reports": [{"id": r.id, "observations": r.observations, "report_text": r.report_text, "ai_mode": r.ai_mode,
                     "submitted_by": r.submitted_by, "submitted_at": iso(r.submitted_at)} for r in a.reports],
        "history": [{"id": h.id, "action": h.action, "user_name": h.user_name, "role": h.role, "remarks": h.remarks,
                     "previous_status": h.previous_status, "new_status": h.new_status, "created_at": iso(h.created_at)}
                    for h in a.history],
        "tasks": [{"id": t.id, "stage": t.stage, "status": t.status, "created_at": iso(t.created_at),
                   "completed_at": iso(t.completed_at), "completed_by": t.completed_by} for t in a.tasks],
        "analysis": ai_out(latest_log(a, "ANALYSIS")),
        "summary": ai_out(latest_log(a, "CASE_SUMMARY")),
        "required_documents": list(ai_service.REQUIRED_DOCS),
        "available_actions": available_actions(a, user),
    })
    return d


def ai_payload(a: m.Application) -> dict:
    vro = next((h.remarks for h in reversed(a.history)
                if h.role == m.VRO and h.action.startswith(("FORWARDED", "RETURNED"))), "")
    return {
        "application": {k: getattr(a, k) for k in ("applicant_name", "guardian_name", "age", "gender", "village", "mandal",
                                                    "district", "occupation", "household_members", "declared_income", "purpose")},
        "documents": [{"id": d.id, "doc_type": d.doc_type, "content_text": d.content_text} for d in a.documents],
        "vro_remarks": vro,
        "field_reports": [r.report_text for r in a.reports],
        "analysis": (latest_log(a, "ANALYSIS").output if latest_log(a, "ANALYSIS") else None),
    }


def run_ai(db, a, user, kind, payload, lang):
    try:
        res = ai_service.run(kind, payload, lang)
    except ai_service.AIError as e:
        raise HTTPException(502, str(e))
    log = m.AILog(application_id=a.id, kind=kind, mode=res["mode"], model=res["model"], output=res["output"],
                  requested_by=user.full_name)
    db.add(log)
    audit_only(db, a, user, f"AI_{kind}", f"mode={res['mode']}")
    db.commit()
    return ai_out(log)


# ------------------------------------------------------------------ auth + meta


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(m.User).filter(m.User.username == body.username).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    return {"access_token": create_token(user), "token_type": "bearer", "user": user_out(user)}


def user_out(u: m.User) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "full_name_te": u.full_name_te,
            "role": u.role, "is_active": u.is_active}


@router.get("/auth/me")
def me(user: m.User = Depends(get_current_user)):
    return user_out(user)


@router.get("/ai/status")
def ai_status(user: m.User = Depends(get_current_user)):
    return ai_service.status()


@router.get("/meta/demo-users")
def demo_users(db: Session = Depends(get_db)):
    """DEMO ONLY: lists demo credentials on the login screen. Never do this in production."""
    from .seed import DEMO_USERS
    if os.environ.get("SHOW_DEMO_CREDENTIALS", "true").lower() != "true":
        return []
    return [{"username": u[0], "role": u[3], "password": u[4]} for u in DEMO_USERS]


# ------------------------------------------------------------------ dashboard + lists


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    live = ~m.Application.archived
    counts = dict(db.query(m.Application.status, func.count()).filter(live).group_by(m.Application.status).all())
    c = lambda s: counts.get(s, 0)
    recent = db.query(m.Application).filter(live).order_by(m.Application.submitted_at.desc()).limit(8).all()
    my_stage = {m.VRO: m.VRO, m.RI: m.RI, m.TAHSILDAR: m.TAHSILDAR}.get(user.role)
    return {
        "stats": {"total": sum(counts.values()), "pending": c(m.SUBMITTED), "under_scrutiny": c(m.UNDER_SCRUTINY),
                  "returned": c(m.RETURNED), "awaiting_field": c(m.AWAITING_FIELD),
                  "awaiting_final": c(m.AWAITING_FINAL), "approved": c(m.APPROVED), "rejected": c(m.REJECTED)},
        "my_queue": db.query(m.Application).filter(live, m.Application.current_stage == my_stage).count() if my_stage else None,
        "recent": [app_row(a) for a in recent],
    }


@router.get("/applications")
def list_applications(status: str | None = None, q: str | None = None, mine: bool = False,
                      db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    query = db.query(m.Application).filter(~m.Application.archived)
    if status:
        query = query.filter(m.Application.status == status)
    if mine and user.role != m.ADMIN:
        query = query.filter(m.Application.current_stage == user.role)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(m.Application.applicant_name.ilike(like) | m.Application.app_no.ilike(like)
                             | m.Application.village.ilike(like))
    return [app_row(a) for a in query.order_by(m.Application.submitted_at.desc()).all()]


@router.get("/applications/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    return app_detail(get_app(db, app_id), user)


@router.get("/history")
def global_history(limit: int = 200, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    rows = (db.query(m.AuditLog, m.Application.app_no, m.Application.applicant_name).join(m.Application)
            .order_by(m.AuditLog.id.desc()).limit(min(limit, 500)).all())
    return [{"id": h.id, "app_id": h.application_id, "app_no": no, "applicant_name": nm, "action": h.action,
             "user_name": h.user_name, "role": h.role, "remarks": h.remarks, "previous_status": h.previous_status,
             "new_status": h.new_status, "created_at": iso(h.created_at)} for h, no, nm in rows]


# ------------------------------------------------------------------ Stage 1: VRO


@router.post("/applications/{app_id}/start-scrutiny")
def start_scrutiny(app_id: int, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.VRO))):
    app = get_app(db, app_id)
    expect_status(app, m.SUBMITTED)
    transition(db, app, user, "SCRUTINY_STARTED", m.UNDER_SCRUTINY, "Initial scrutiny started")
    db.commit()
    return app_detail(app, user)


@router.post("/applications/{app_id}/ai/analyze")
def ai_analyze(app_id: int, body: LangIn, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.VRO))):
    app = get_app(db, app_id)
    expect_status(app, m.UNDER_SCRUTINY)
    return run_ai(db, app, user, "ANALYSIS", ai_payload(app), body.lang)


@router.post("/applications/{app_id}/forward")
def vro_forward(app_id: int, body: ForwardIn, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.VRO))):
    app = get_app(db, app_id)
    expect_status(app, m.UNDER_SCRUTINY)
    need_remarks(body.remarks, "forward an application")
    app.field_verification_required = body.field_verification_required
    if body.field_verification_required:
        transition(db, app, user, "FORWARDED_FOR_FIELD_VERIFICATION", m.AWAITING_FIELD, body.remarks)
    else:
        transition(db, app, user, "FORWARDED_TO_TAHSILDAR", m.AWAITING_FINAL, body.remarks)
    db.commit()
    return app_detail(app, user)


@router.post("/applications/{app_id}/return")
def vro_return(app_id: int, body: RemarksIn, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.VRO))):
    app = get_app(db, app_id)
    expect_status(app, m.UNDER_SCRUTINY)
    need_remarks(body.remarks, "return an application")
    transition(db, app, user, "RETURNED_FOR_CORRECTION", m.RETURNED, body.remarks)
    db.commit()
    return app_detail(app, user)


@router.post("/applications/{app_id}/documents")
def upload_document(app_id: int, doc_type: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db),
                    user: m.User = Depends(require_roles(m.VRO, m.ADMIN))):
    app = get_app(db, app_id)
    if "upload_document" not in available_actions(app, user):
        raise HTTPException(409, f"Documents cannot be added while application is '{app.status}'")
    dtype = doc_type.strip().upper()
    if dtype not in DOC_TYPES:
        raise HTTPException(422, f"Unknown document type. Allowed: {', '.join(sorted(DOC_TYPES))}")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is too large (maximum 2 MB)")
    if not data:
        raise HTTPException(422, "File is empty")
    name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename or 'document').name}"
    (UPLOAD_DIR / name).write_bytes(data)
    try:  # DEMO: no OCR. Text files are read directly so the AI demo has content to analyse.
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    db.add(m.Document(application_id=app.id, doc_type=dtype, filename=name,
                      stored_path=str(UPLOAD_DIR / name), content_text=text))
    audit_only(db, app, user, "DOCUMENT_UPLOADED", f"{dtype}: {Path(file.filename or '').name}")
    db.commit()
    return app_detail(app, user)


@router.get("/documents/{doc_id}/file")
def download_document(doc_id: int, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    doc = db.get(m.Document, doc_id)
    if not doc or not Path(doc.stored_path).exists():
        raise HTTPException(404, "Document file not found")
    return FileResponse(doc.stored_path, filename=doc.filename)


# ------------------------------------------------------------------ Stage 2: Revenue Inspector


@router.post("/applications/{app_id}/ai/field-report")
def ai_field_report(app_id: int, body: ObservationsIn, lang: str = "te", db: Session = Depends(get_db),
                    user: m.User = Depends(require_roles(m.RI))):
    app = get_app(db, app_id)
    expect_status(app, m.AWAITING_FIELD)
    if not any(v.strip() for v in body.model_dump().values()):
        raise HTTPException(422, "Enter at least one observation first")
    payload = {"application": ai_payload(app)["application"], "observations": body.model_dump()}
    return run_ai(db, app, user, "FIELD_REPORT", payload, lang)


@router.post("/applications/{app_id}/field-report")
def submit_field_report(app_id: int, body: FieldReportIn, db: Session = Depends(get_db),
                        user: m.User = Depends(require_roles(m.RI))):
    app = get_app(db, app_id)
    expect_status(app, m.AWAITING_FIELD)
    db.add(m.VerificationReport(application_id=app.id, observations=body.observations.model_dump(),
                                report_text=body.report_text.strip(), ai_mode=body.ai_mode, submitted_by=user.full_name))
    transition(db, app, user, "FIELD_REPORT_SUBMITTED", m.AWAITING_FINAL, "Field report submitted to Tahsildar")
    db.commit()
    return app_detail(app, user)


# ------------------------------------------------------------------ Stage 3: Tahsildar


@router.post("/applications/{app_id}/ai/summary")
def ai_summary(app_id: int, body: LangIn, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.TAHSILDAR))):
    app = get_app(db, app_id)
    expect_status(app, m.AWAITING_FINAL)
    return run_ai(db, app, user, "CASE_SUMMARY", ai_payload(app), body.lang)


@router.post("/applications/{app_id}/decision")
def decide(app_id: int, body: DecisionIn, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.TAHSILDAR))):
    app = get_app(db, app_id)
    expect_status(app, m.AWAITING_FINAL)
    if body.decision == "APPROVE":
        transition(db, app, user, "APPROVED", m.APPROVED, body.remarks)
    elif body.decision == "REJECT":
        need_remarks(body.remarks, "reject an application")
        transition(db, app, user, "REJECTED", m.REJECTED, body.remarks)
    else:
        need_remarks(body.remarks, "return an application")
        transition(db, app, user, "RETURNED_TO_VRO", m.UNDER_SCRUTINY, body.remarks)
    db.commit()
    return app_detail(app, user)


# ------------------------------------------------------------------ Admin


@router.post("/applications/{app_id}/resubmit")
def resubmit(app_id: int, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.ADMIN))):
    """DEMO ONLY: stands in for the citizen correcting and resubmitting online."""
    app = get_app(db, app_id)
    expect_status(app, m.RETURNED)
    transition(db, app, user, "RESUBMITTED", m.SUBMITTED, "Applicant resubmission simulated by admin (demo)")
    db.commit()
    return app_detail(app, user)


@router.delete("/admin/applications/{app_id}")
def archive_application(app_id: int, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.ADMIN))):
    """Soft delete: hides the record from lists/statistics but keeps its audit history intact."""
    app = get_app(db, app_id)
    if app.archived:
        raise HTTPException(409, "Application is already archived")
    audit_only(db, app, user, "ARCHIVED", "Record archived by admin")
    app.archived = True
    db.commit()
    return {"ok": True}


@router.get("/admin/users")
def list_users(db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.ADMIN))):
    return [user_out(u) for u in db.query(m.User).order_by(m.User.id).all()]


@router.post("/admin/users")
def create_user(body: UserIn, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.ADMIN))):
    if db.query(m.User).filter(m.User.username == body.username).first():
        raise HTTPException(409, "Username already exists")
    u = m.User(username=body.username, full_name=body.full_name, full_name_te=body.full_name_te or body.full_name,
               role=body.role, password_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    return user_out(u)


@router.post("/admin/users/{user_id}/toggle-active")
def toggle_user(user_id: int, db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.ADMIN))):
    u = db.get(m.User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == user.id:
        raise HTTPException(409, "You cannot deactivate your own account")
    u.is_active = not u.is_active
    db.commit()
    return user_out(u)


@router.post("/admin/reset-demo-data")
def reset_demo(db: Session = Depends(get_db), user: m.User = Depends(require_roles(m.ADMIN))):
    from .seed import seed
    db.close()
    with SessionLocal() as fresh:
        seed(fresh)
    return {"ok": True}
