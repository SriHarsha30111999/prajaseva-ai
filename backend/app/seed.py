"""Seed the database with dummy users and applications.

DEMO DATA:
Sample application records are used because original government
datasets are not available for this assignment.
No real citizen information is stored here. All names, numbers and addresses are fictional.
"""
from datetime import timedelta

from sqlalchemy.orm import Session

from . import models as m
from .auth import hash_password
from .database import Base, UPLOAD_DIR, engine

# DEMO IMPLEMENTATION: predefined demo users (see auth.py).
DEMO_USERS = [
    ("vro", "Ravi Kumar (VRO)", "రవి కుమార్ (VRO)", m.VRO, "vro123"),
    ("inspector", "Sunitha Rao (Revenue Inspector)", "సునీత రావు (రెవెన్యూ ఇన్‌స్పెక్టర్)", m.RI, "inspector123"),
    ("tahsildar", "Prasad Varma (Tahsildar)", "ప్రసాద్ వర్మ (తహసీల్దార్)", m.TAHSILDAR, "tahsildar123"),
    ("admin", "System Admin", "సిస్టమ్ అడ్మిన్", m.ADMIN, "admin123"),
]

ACTORS = {  # (name, role) used in seeded history
    "applicant": ("Applicant (online submission)", "APPLICANT"),
    m.VRO: ("Ravi Kumar (VRO)", m.VRO),
    m.RI: ("Sunitha Rao (Revenue Inspector)", m.RI),
    m.TAHSILDAR: ("Prasad Varma (Tahsildar)", m.TAHSILDAR),
}

GOOD_FIELD_OBS = {
    "visit_date": "2026-11-05", "persons_met": "Applicant and spouse",
    "residence_type": "Single-room tiled house, rented", "livelihood": "Daily-wage agricultural labour",
    "assets": "No vehicle, no agricultural land", "neighbour_statement": "Neighbours confirmed seasonal wage work",
    "notes": "Household appears consistent with declared income.",
}

# (name, guardian, age, gender, village, mandal, income, occupation, members, purpose, status, flags)
APPS = [
    ("Lakshmi Devi", "Venkataiah", 41, "Female", "Kothapalli", "Huzurabad", 90000, "Agricultural labourer", 4, "Scholarship for daughter", m.SUBMITTED, {}),
    ("Ramesh Naik", "Balu Naik", 35, "Male", "Gundlapally", "Narsampet", 110000, "Small shop keeper", 5, "Fee reimbursement", m.SUBMITTED, {"skip": "RATION_CARD"}),
    ("Suresh Goud", "Mallaiah Goud", 38, "Male", "Ankushapur", "Jangaon", 120000, "Private employee", 4, "Bank loan subsidy", m.UNDER_SCRUTINY, {"salary": 280000}),
    ("Anitha Reddy", "Narayana Reddy", 29, "Female", "Peddapuram", "Shamirpet", 150000, "Tailor", 3, "Higher education scholarship", m.UNDER_SCRUTINY, {}),
    ("Venkat Rao", "Appa Rao", 47, "Male", "Chinthakani", "Khammam Rural", 135000, "Tenant farmer", 6, "Housing scheme", m.AWAITING_FIELD, {"fv": True}),
    ("Padma Kumari", "Seshagiri", 33, "Female", "Rampur", "Karimnagar", 80000, "Home-based work", 3, "Pension scheme", m.AWAITING_FIELD, {"fv": True, "salary": 80000}),
    ("Mohammed Irfan", "Abdul Rahim", 42, "Male", "Bholakpur", "Nampally", 100000, "Auto driver", 5, "Scholarship for son", m.AWAITING_FINAL, {"fv": True, "report": True}),
    ("Sita Mahalakshmi", "Krishna Murthy", 52, "Female", "Madhira", "Madhira", 70000, "Anganwadi helper", 2, "Pension scheme", m.AWAITING_FINAL, {"fv": False}),
    ("Narsimha Chary", "Ramulu Chary", 45, "Male", "Bheemaram", "Mancherial", 95000, "Carpenter", 4, "Fee reimbursement", m.APPROVED, {"fv": False}),
    ("Kavitha Yadav", "Kondal Yadav", 31, "Female", "Sircilla", "Sircilla", 60000, "Dairy farming", 4, "Loan subsidy", m.REJECTED, {"fv": True, "report": True, "salary": 410000}),
    ("Bhaskar Rao", "Sambaiah", 56, "Male", "Kodad", "Kodad", 140000, "Retired helper", 2, "Pension scheme", m.RETURNED, {"skip": "INCOME_DECLARATION"}),
]


def _doc_text(kind, a, income, last_aadhaar):
    base = f"Name: {a['name']}\nVillage: {a['village']}\n"
    if kind == "AADHAAR":
        return base + f"Aadhaar No: XXXX XXXX {last_aadhaar}\nAge: {a['age']}\nGender: {a['gender']}\n(Dummy demo document)"
    if kind == "RATION_CARD":
        return base + f"Card No: WAP{last_aadhaar}00\nFamily members: {a['members']}\n(Dummy demo document)"
    if kind == "INCOME_DECLARATION":
        return base + f"Annual income declared: Rs. {int(income):,}\nOccupation: {a['occupation']}\n(Dummy demo document)"
    return base + f"Employer: Demo Enterprises Pvt Ltd\nAnnual salary (from payslips): Rs. {int(income):,}\n(Dummy demo document)"


def seed(db: Session) -> None:
    """Drop and recreate all tables, then insert demo data."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    for f in UPLOAD_DIR.glob("*"):
        if f.is_file() and f.name != ".gitkeep":
            f.unlink()

    for username, name, name_te, role, pwd in DEMO_USERS:
        db.add(m.User(username=username, full_name=name, full_name_te=name_te, role=role, password_hash=hash_password(pwd)))

    base = m.now()
    for i, (name, guardian, age, gender, village, mandal, income, occ, members, purpose, status, fl) in enumerate(APPS, 1):
        submitted = base - timedelta(days=22 - i * 2, hours=i)
        a_dict = dict(name=name, village=village, age=age, gender=gender, members=members, occupation=occ)
        app = m.Application(
            app_no=f"TS-IC-2026-{i:04d}", applicant_name=name, guardian_name=guardian, age=age, gender=gender,
            village=village, mandal=mandal, district="Demo District", address=f"H.No {10 + i}-{i}, {village} Village, {mandal} Mandal",
            occupation=occ, household_members=members, declared_income=income, purpose=purpose,
            submitted_at=submitted, status=status, field_verification_required=fl.get("fv"),
        )
        db.add(app)
        db.flush()

        kinds = [k for k in ("AADHAAR", "RATION_CARD", "INCOME_DECLARATION") if k != fl.get("skip")]
        if "salary" in fl:
            kinds.append("SALARY_SLIP")
        for k in kinds:
            text = _doc_text(k, a_dict, fl["salary"] if k == "SALARY_SLIP" else income, f"{1000 + i * 37}")
            fname = f"{k.lower()}_{app.app_no}.txt"
            (UPLOAD_DIR / fname).write_text(text, encoding="utf-8")
            db.add(m.Document(application_id=app.id, doc_type=k, filename=fname, stored_path=str(UPLOAD_DIR / fname),
                              content_text=text, uploaded_at=submitted))

        # Build seeded history + tasks consistent with the status.
        t = submitted
        log = lambda action, actor, remarks, prev, new: db.add(m.AuditLog(
            application_id=app.id, action=action, user_name=ACTORS[actor][0], role=ACTORS[actor][1],
            remarks=remarks, previous_status=prev, new_status=new, created_at=t))
        log("SUBMITTED", "applicant", "Application submitted online (demo data)", None, m.SUBMITTED)
        stage = {m.SUBMITTED: m.VRO, m.UNDER_SCRUTINY: m.VRO, m.RETURNED: "APPLICANT", m.AWAITING_FIELD: m.RI,
                 m.AWAITING_FINAL: m.TAHSILDAR, m.APPROVED: "COMPLETED", m.REJECTED: "COMPLETED"}[status]
        app.current_stage = stage

        def task(stg, done_by=None):
            db.add(m.WorkflowTask(application_id=app.id, stage=stg, status="DONE" if done_by else "OPEN",
                                  created_at=t, completed_at=t if done_by else None, completed_by=done_by))

        if status == m.SUBMITTED:
            task(m.VRO)
            continue
        t += timedelta(hours=5)
        log("SCRUTINY_STARTED", m.VRO, "Initial scrutiny started", m.SUBMITTED, m.UNDER_SCRUTINY)
        if status == m.UNDER_SCRUTINY:
            task(m.VRO)
            continue
        if status == m.RETURNED:
            task(m.VRO, ACTORS[m.VRO][0])
            t += timedelta(hours=3)
            log("RETURNED_FOR_CORRECTION", m.VRO, "Income self-declaration is missing. Please upload and resubmit.", m.UNDER_SCRUTINY, m.RETURNED)
            continue
        task(m.VRO, ACTORS[m.VRO][0])
        t += timedelta(hours=4)
        if fl.get("fv"):
            log("FORWARDED_FOR_FIELD_VERIFICATION", m.VRO, "Documents reviewed; field inspection needed to confirm income and residence.", m.UNDER_SCRUTINY, m.AWAITING_FIELD)
            if status == m.AWAITING_FIELD:
                task(m.RI)
                continue
            task(m.RI, ACTORS[m.RI][0])
            t += timedelta(days=2)
            db.add(m.VerificationReport(application_id=app.id, observations=GOOD_FIELD_OBS, ai_mode=None,
                                        report_text="Visited the residence on 2026-11-05 and met the applicant and spouse. "
                                        "Single-room rented house; livelihood is daily-wage labour; no vehicle or land observed. "
                                        "Neighbours confirmed the seasonal nature of income. Observations appear consistent with the declaration.",
                                        submitted_by=ACTORS[m.RI][0], submitted_at=t))
            log("FIELD_REPORT_SUBMITTED", m.RI, "Field report submitted to Tahsildar", m.AWAITING_FIELD, m.AWAITING_FINAL)
        else:
            log("FORWARDED_TO_TAHSILDAR", m.VRO, "Documents are consistent; field verification not required.", m.UNDER_SCRUTINY, m.AWAITING_FINAL)
        if status == m.AWAITING_FINAL:
            task(m.TAHSILDAR)
            continue
        task(m.TAHSILDAR, ACTORS[m.TAHSILDAR][0])
        t += timedelta(days=1)
        if status == m.APPROVED:
            log("APPROVED", m.TAHSILDAR, "Verified and approved.", m.AWAITING_FINAL, m.APPROVED)
        else:
            log("REJECTED", m.TAHSILDAR, "Salary slip shows income above the eligibility limit.", m.AWAITING_FINAL, m.REJECTED)
    db.commit()
