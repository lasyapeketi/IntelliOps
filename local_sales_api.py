"""Temporary local test runner for the Sales & Revenue Forecasting module.

This file is provided for local browser testing and interactive API exploration.
Do NOT stage or commit this file.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from modules.sales_revenue_forecasting.router import router as sales_revenue_router

_FRONTEND_DIR = Path(__file__).resolve().parent / "frontend" / "sales_revenue_forecasting"

app = FastAPI(
    title="IntelliOps — Sales & Revenue Forecasting API",
    description="Interactive local test server for the sales_revenue_forecasting use-case module.",
    version="1.0.0",
)

# Mount the sales revenue forecasting API router
app.include_router(sales_revenue_router)

# Serve frontend static assets (CSS, JS) at /static/*
app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")


@app.get("/", response_class=FileResponse)
def root() -> FileResponse:
    """Serve the standalone Sales & Revenue Forecasting dashboard."""
    return FileResponse(str(_FRONTEND_DIR / "index.html"), media_type="text/html")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "module": "sales_revenue_forecasting"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("local_sales_api:app", host="127.0.0.1", port=8000, reload=True)
