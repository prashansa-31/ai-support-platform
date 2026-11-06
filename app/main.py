from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import router as auth_router
from app.routers.conversations import router as conversations_router
from app.routers.admin import router as admin_router
from app.config import settings

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://ai-support-platform-gamma.vercel.app",
    "https://ai-support-platform.vercel.app",
]
frontend_origin = (
    settings.frontend_url.rstrip("/") if getattr(settings, "frontend_url", None) else ""
)
if frontend_origin and frontend_origin not in origins:
    origins.append(frontend_origin)
app = FastAPI(title="AI Support Platform")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
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
