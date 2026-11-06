from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import router as auth_router
from app.routers.conversations import router as conversations_router
from app.routers.admin import router as admin_router
from app.config import settings

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if settings.frontend_url and settings.frontend_url not in origins:
    origins.append(settings.frontend_url)
app = FastAPI(title="AI Support Platform")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
