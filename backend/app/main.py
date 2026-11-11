from fastapi import FastAPI

from backend.app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Research and decision-support API for NSE swing-trading strategies. "
        "This service does not place live trades."
    ),
    version="0.1.0",
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "running",
        "environment": settings.app_env,
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
