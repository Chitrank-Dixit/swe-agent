from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.state.db import init_db
from src.api.routes import router as api_router

app = FastAPI(
    title="Software Engineering Workflow Coach API",
    description="Multi-agent developer coaching platform powered by AutoGen, FastAPI, and SQLite.",
    version="0.1.0"
)

# Enable CORS for local developer use
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Database tables on startup
@app.on_event("startup")
def on_startup():
    init_db()

# Mount API router
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "service": "Software Engineering Workflow Coach API",
        "version": "0.1.0"
    }
