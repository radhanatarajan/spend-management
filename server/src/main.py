from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.activities import router as activities_router
from src.api.accounts import router as accounts_router
from src.api.auth import router as auth_router
from src.api.budget import router as budget_router
from src.api.contracts import router as contracts_router
from src.api.departments import router as departments_router
from src.api.projects import router as projects_router
from src.api.reference_audit import router as reference_audit_router
from src.api.spend import router as spend_router
from src.db.init_db import init_db

app = FastAPI(title="Spend Management API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(auth_router)
app.include_router(spend_router)
app.include_router(contracts_router)
app.include_router(budget_router)
app.include_router(departments_router)
app.include_router(accounts_router)
app.include_router(projects_router)
app.include_router(activities_router)
app.include_router(reference_audit_router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Spend Management API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
