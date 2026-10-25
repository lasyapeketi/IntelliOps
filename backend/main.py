
from fastapi import FastAPI

from backend.customer_churn.api import router as customer_churn_router

app = FastAPI(
    title="IntelliOps API",
    description="Unified API for IntelliOps machine learning use cases.",
    version="1.0.0",
)

app.include_router(customer_churn_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "intelliops-api",
    }
