"""PrajaSeva AI - FastAPI entry point. Run: uvicorn app.main:app --reload --port 8000"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import SECRET_KEY
from .database import Base, SessionLocal, engine
from .models import User
from .routes import router
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    if SECRET_KEY.startswith("prajaseva-demo-secret"):
        print("WARNING: using the built-in DEMO JWT secret. Set JWT_SECRET for anything beyond a local demo.")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(User).count() == 0:  # first run: load dummy users + applications
            seed(db)
    yield


app = FastAPI(title="PrajaSeva AI (demo prototype)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
