import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

@app.on_event("startup")
async def startup_event():
    """Auto-build ChromaDB if it doesn't exist on startup."""
    chroma_path = "./chroma_db"
    if not os.path.exists(chroma_path):
        print("ChromaDB not found — building from competitors.json...")
        from rag.embedder import build_vector_db
        build_vector_db()
        print("ChromaDB build complete!")
    else:
        print("ChromaDB found — skipping rebuild.")

app.include_router(analyze_router.router, prefix="/api/v1")
app.include_router(benchmark_router.router, prefix="/api/v1")
app.include_router(strategies_router.router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AdCopilot API", "version": "1.0.0"}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")