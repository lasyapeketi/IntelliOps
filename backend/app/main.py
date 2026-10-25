"""IntelliOps Backend Application Entrypoint.

Central FastAPI application hosting operational decision-support modules.
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure workspace root is in sys.path for cross-module imports
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Delivery Delay Prediction Router
from modules.delivery_delay.router import router as delivery_delay_router

app = FastAPI(
    title="IntelliOps API",
    description="Intelligent Business Operations and Resource Optimization Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for React frontend integration (avoiding wildcard origin with credentials)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:[0-9]+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint to verify backend service status."""
    return {"status": "healthy", "service": "IntelliOps API"}


# --- Delivery Delay Prediction Router Registration ---
app.include_router(delivery_delay_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
