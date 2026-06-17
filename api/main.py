from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import analyze as analyze_router
from api.routers import benchmark as benchmark_router
from api.routers import strategies as strategies_router

app = FastAPI(
    title="AdCopilot API",
    description="AI-powered ad copy optimization API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(
    analyze_router.router,
    prefix="/api/v1"
)

app.include_router(
    benchmark_router.router,
    prefix="/api/v1"
)

app.include_router(
    strategies_router.router,
    prefix="/api/v1"
)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AdCopilot API", "version": "1.0.0"}

@app.get("/")
def root():
    return {"message": "AdCopilot API is running", "docs": "/docs", "health": "/health"}
