from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.spend import router as spend_router
from src.db.init_db import init_db

app = FastAPI(title="Spend Management API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(spend_router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Spend Management API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
