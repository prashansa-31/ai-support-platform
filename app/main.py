from fastapi import FastAPI
from app.routers.auth import router as auth_router

app = FastAPI(title="AI Support Platform")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
